"""Refund side-effect safety tests; gateways are local fakes, never live calls."""
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, connections, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings
import requests

from .models import AuditEntry, DomainOrder, ManagedDomain
from .payments import PaymentError, Razorpay, verify_webhook
from .refunds import RefundError, reconcile_refund, request_refund


@override_settings(RAZORPAY_KEY_ID="rzp_test_unit", RAZORPAY_KEY_SECRET="unit-only")
class RefundTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("buyer", "buyer@example.test")
        self.other = get_user_model().objects.create_user("other", "other@example.test")
        self.index = 0

    def order(self, **overrides):
        self.index += 1
        data = dict(owner=self.user, domain=f"refund{self.index}.com", operation=DomainOrder.REGISTER,
                    amount_paise=50000, status=DomainOrder.REVIEW, idempotency_key=f"refund-{self.index}",
                    razorpay_order_id=f"order_{self.index}", razorpay_payment_id=f"pay_{self.index}")
        data.update(overrides)
        return DomainOrder.objects.create(**data)

    def gateway(self, order, **refund_overrides):
        gateway = Mock()
        gateway.fetch_payment.return_value = {
            "id": order.razorpay_payment_id, "entity": "payment", "order_id": order.razorpay_order_id,
            "status": "captured", "captured": True, "amount": order.amount_paise,
            "currency": order.currency, "amount_refunded": 0, "refund_status": None,
        }
        result = {"id": f"rfnd_{self.index}", "entity": "refund", "payment_id": order.razorpay_payment_id,
                  "amount": order.amount_paise, "currency": order.currency, "status": "processed"}
        result.update(refund_overrides)
        gateway.refund_payment.return_value = result
        gateway.fetch_refund.return_value = result
        return gateway

    def request(self, order, gateway, **options):
        return request_refund(order.pk, confirmed_not_registered=True, gateway=gateway, **options)

    def test_confirmation_is_required_before_network_or_claim(self):
        order = self.order()
        gateway = self.gateway(order)
        with self.assertRaises(RefundError):
            request_refund(order.pk, gateway=gateway)
        gateway.fetch_payment.assert_not_called()
        gateway.refund_payment.assert_not_called()
        order.refresh_from_db()
        self.assertIsNone(order.refund_attempted_at)

    def test_full_processed_refund_is_verified_and_duplicate_is_blocked(self):
        order = self.order()
        gateway = self.gateway(order)
        self.request(order, gateway)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REFUNDED)
        self.assertEqual(order.refund_id, gateway.refund_payment.return_value["id"])
        self.assertIsNotNone(order.refund_attempted_at)
        with self.assertRaises(RefundError):
            self.request(order, gateway)
        gateway.refund_payment.assert_called_once_with(order.razorpay_payment_id, order.amount_paise)
        self.assertTrue(AuditEntry.objects.filter(order=order, action__startswith="refund").exists())

    def test_pending_response_does_not_claim_completed_refund(self):
        order = self.order()
        gateway = self.gateway(order, status="pending")
        self.request(order, gateway)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REFUND_PENDING)
        self.assertEqual(order.refund_id, gateway.refund_payment.return_value["id"])

    def test_timeout_persists_uncertainty_and_never_retries_post(self):
        order = self.order()
        gateway = self.gateway(order)
        gateway.refund_payment.side_effect = PaymentError("private gateway credential")
        with self.assertRaises(RefundError) as caught:
            self.request(order, gateway)
        self.assertNotIn("private", str(caught.exception))
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REFUND_REVIEW)
        self.assertIsNotNone(order.refund_attempted_at)
        with self.assertRaises(RefundError):
            self.request(order, gateway)
        self.assertEqual(gateway.refund_payment.call_count, 1)

    def test_gateway_payment_must_be_captured_matching_and_unrefunded(self):
        invalid = ({"status": "authorized"}, {"order_id": "order_other"}, {"id": "pay_other"},
                   {"amount": 1}, {"amount": True}, {"currency": "USD"},
                   {"amount_refunded": 1}, {"refund_status": "partial"})
        for changes in invalid:
            with self.subTest(changes=changes):
                order = self.order()
                gateway = self.gateway(order)
                gateway.fetch_payment.return_value.update(changes)
                with self.assertRaises(RefundError):
                    self.request(order, gateway)
                gateway.refund_payment.assert_not_called()
                order.refresh_from_db()
                self.assertNotEqual(order.status, DomainOrder.REFUNDED)

    def test_mismatched_and_malformed_refund_responses_never_mark_refunded(self):
        invalid = ({"id": "rfnd_/unsafe"}, {"id": ""}, {"payment_id": "pay_other"},
                   {"amount": 1}, {"amount": True}, {"currency": "USD"}, {"status": "unknown"})
        for changes in invalid:
            with self.subTest(changes=changes):
                order = self.order()
                gateway = self.gateway(order, **changes)
                with self.assertRaises(RefundError):
                    self.request(order, gateway)
                order.refresh_from_db()
                self.assertEqual(order.status, DomainOrder.REFUND_REVIEW)
                self.assertIsNotNone(order.refund_attempted_at)

    def test_ineligible_order_states_and_previous_attempts_reject_before_post(self):
        for status in (DomainOrder.AWAITING, DomainOrder.PAID, DomainOrder.PROCESSING, DomainOrder.ACTIVE,
                       DomainOrder.REFUNDED, DomainOrder.REFUND_PENDING, DomainOrder.REFUND_REVIEW):
            with self.subTest(status=status):
                order = self.order(status=status)
                gateway = self.gateway(order)
                with self.assertRaises(RefundError):
                    self.request(order, gateway)
                gateway.refund_payment.assert_not_called()

    def test_registration_with_domain_or_provider_result_is_not_refundable(self):
        domain = ManagedDomain.objects.create(owner=self.user, name="registered.com", provider_id=100, status="active")
        for values in ({"managed_domain": domain}, {"provider_result_id": 100}):
            order = self.order(**values)
            gateway = self.gateway(order)
            with self.assertRaises(RefundError):
                self.request(order, gateway)
            gateway.refund_payment.assert_not_called()

    def test_renewal_must_reference_customers_own_domain(self):
        foreign = ManagedDomain.objects.create(owner=self.other, name="foreign.com", provider_id=200, status="active")
        order = self.order(operation=DomainOrder.RENEW, managed_domain=foreign, domain=foreign.name)
        gateway = self.gateway(order)
        with self.assertRaises(RefundError):
            self.request(order, gateway)
        gateway.refund_payment.assert_not_called()

    def test_outer_transaction_cannot_undo_a_claim_after_external_effect(self):
        order = self.order()
        gateway = self.gateway(order)
        with transaction.atomic(), self.assertRaises(RefundError):
            self.request(order, gateway)
        gateway.refund_payment.assert_not_called()

    @skipUnless(connection.vendor == "postgresql", "Independent claim visibility requires PostgreSQL")
    def test_refund_claim_is_committed_before_external_post(self):
        order = self.order()
        gateway = self.gateway(order)

        def observe_claim():
            close_old_connections()
            try:
                claimed = DomainOrder.objects.get(pk=order.pk)
                return claimed.status, claimed.refund_attempted_at
            finally:
                connections.close_all()

        def post(*args):
            with ThreadPoolExecutor(max_workers=1) as pool:
                status, attempted_at = pool.submit(observe_claim).result(timeout=10)
            self.assertEqual(status, DomainOrder.REFUND_PENDING)
            self.assertIsNotNone(attempted_at)
            return gateway.fetch_refund.return_value

        gateway.refund_payment.side_effect = post
        self.request(order, gateway)

    def test_live_key_requires_explicit_allowance_but_sales_switch_is_not_required(self):
        with override_settings(RAZORPAY_KEY_ID="rzp_live_unit", SALES_ENABLED=False):
            order = self.order()
            gateway = self.gateway(order)
            with self.assertRaises(RefundError):
                self.request(order, gateway)
            gateway.refund_payment.assert_not_called()
            self.request(order, gateway, allow_live=True)
            gateway.refund_payment.assert_called_once()

    def test_reconciliation_reads_pending_refund_and_completes_without_post(self):
        order = self.order()
        gateway = self.gateway(order, status="pending")
        self.request(order, gateway)
        gateway.fetch_refund.return_value = dict(gateway.fetch_refund.return_value, status="processed")
        reconcile_refund(order.pk, gateway=gateway)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REFUNDED)
        gateway.fetch_refund.assert_called_once_with(order.refund_id)
        self.assertEqual(gateway.refund_payment.call_count, 1)

    def test_uncertain_post_can_be_reconciled_using_operator_supplied_refund_id(self):
        order = self.order()
        gateway = self.gateway(order)
        gateway.refund_payment.side_effect = PaymentError("uncertain")
        with self.assertRaises(RefundError):
            self.request(order, gateway)
        reconcile_refund(order.pk, gateway=gateway, refund_id=gateway.fetch_refund.return_value["id"])
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REFUNDED)
        self.assertEqual(gateway.refund_payment.call_count, 1)

    def test_reconciliation_rejects_other_payments_refunds_and_identity_changes(self):
        order = self.order()
        gateway = self.gateway(order, status="pending")
        self.request(order, gateway)
        original_id = gateway.fetch_refund.return_value["id"]
        with self.assertRaises(RefundError):
            reconcile_refund(order.pk, gateway=gateway, refund_id="rfnd_other")
        for changes in ({"id": "rfnd_other"}, {"payment_id": "pay_other"}, {"amount": 1}, {"currency": "USD"}):
            with self.subTest(changes=changes):
                gateway.fetch_refund.return_value = dict(gateway.refund_payment.return_value, **changes)
                with self.assertRaises(RefundError):
                    reconcile_refund(order.pk, gateway=gateway)
                order.refresh_from_db()
                self.assertNotEqual(order.status, DomainOrder.REFUNDED)
                self.assertEqual(order.refund_id, original_id)
        self.assertEqual(gateway.refund_payment.call_count, 1)

    def test_reconciliation_network_failure_is_safe_and_does_not_repeat_post(self):
        order = self.order()
        gateway = self.gateway(order, status="pending")
        self.request(order, gateway)
        gateway.fetch_refund.side_effect = PaymentError("private credentials")
        with self.assertRaises(RefundError) as caught:
            reconcile_refund(order.pk, gateway=gateway)
        self.assertNotIn("private", str(caught.exception))
        order.refresh_from_db()
        self.assertNotEqual(order.status, DomainOrder.REFUNDED)
        self.assertEqual(gateway.refund_payment.call_count, 1)

    def test_command_requires_confirmation_and_redacts_service_errors(self):
        order = self.order()
        with self.assertRaises(CommandError):
            call_command("refund_order", str(order.pk), stdout=StringIO())
        with patch("shop.management.commands.refund_order.request_refund", side_effect=RefundError("safe failure")):
            with self.assertRaises(CommandError):
                call_command("refund_order", str(order.pk), confirmed_not_registered=True, stdout=StringIO())

    def test_invalid_order_identifiers_raise_safe_domain_errors(self):
        gateway = Mock()
        with self.assertRaises(RefundError):
            request_refund("not-a-uuid", confirmed_not_registered=True, gateway=gateway)
        with self.assertRaises(RefundError):
            reconcile_refund("not-a-uuid", gateway=gateway)
        gateway.fetch_payment.assert_not_called()
        gateway.fetch_refund.assert_not_called()

    def test_refund_identifier_already_bound_elsewhere_is_not_rebound(self):
        first = self.order()
        first_gateway = self.gateway(first)
        self.request(first, first_gateway)
        first.refresh_from_db()
        second = self.order()
        second_gateway = self.gateway(second, id=first.refund_id)
        with self.assertRaises(RefundError):
            self.request(second, second_gateway)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, DomainOrder.REFUNDED)
        self.assertEqual(second.status, DomainOrder.REFUND_REVIEW)
        self.assertIsNone(second.refund_id)
        self.assertEqual(second_gateway.refund_payment.call_count, 1)

@skipUnless(connection.vendor == "postgresql", "Refund serialization requires PostgreSQL row locks")
@override_settings(RAZORPAY_KEY_ID="rzp_test_unit", RAZORPAY_KEY_SECRET="unit-only")
class RefundConcurrencyTests(TransactionTestCase):
    def test_simultaneous_refund_requests_can_post_only_once(self):
        user = get_user_model().objects.create_user("buyer", "buyer@example.test")
        order = DomainOrder.objects.create(owner=user, domain="concurrent-refund.com",
            operation=DomainOrder.REGISTER, amount_paise=50000, status=DomainOrder.REVIEW,
            idempotency_key="refund-race", razorpay_order_id="order_race", razorpay_payment_id="pay_race")
        gateway = Mock()
        gateway.fetch_payment.return_value = {"id": "pay_race", "order_id": "order_race", "status": "captured",
            "captured": True, "amount": 50000, "currency": "INR", "amount_refunded": 0, "refund_status": None}
        gateway.refund_payment.return_value = {"id": "rfnd_race", "payment_id": "pay_race", "amount": 50000,
            "currency": "INR", "status": "processed"}
        barrier = Barrier(3)

        def invoke(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    request_refund(order.pk, confirmed_not_registered=True, gateway=gateway)
                    return "requested"
                except RefundError:
                    return "blocked"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=3) as pool:
            outcomes = list(pool.map(invoke, range(3)))
        self.assertEqual(outcomes.count("requested"), 1)
        self.assertEqual(gateway.refund_payment.call_count, 1)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REFUNDED)


@override_settings(RAZORPAY_KEY_ID="rzp_test_unit", RAZORPAY_KEY_SECRET="unit-only")
class PaymentAdapterTests(SimpleTestCase):
    def test_read_methods_use_expected_get_paths(self):
        session = Mock()
        session.request.return_value.status_code = 200
        session.request.return_value.json.return_value = {"id": "valid"}
        gateway = Razorpay(session=session)
        cases = ((gateway.fetch_payment, "pay_123", "/payments/pay_123"),
                 (gateway.fetch_order, "order_123", "/orders/order_123"),
                 (gateway.fetch_order_payments, "order_123", "/orders/order_123/payments"),
                 (gateway.fetch_refund, "rfnd_123", "/refunds/rfnd_123"))
        for method, identifier, suffix in cases:
            with self.subTest(suffix=suffix):
                method(identifier)
                self.assertEqual(session.request.call_args.args, ("GET", Razorpay.ROOT + suffix))
                self.assertEqual(session.request.call_args.kwargs["timeout"], 20)
                self.assertFalse(session.request.call_args.kwargs["allow_redirects"])

    def test_path_injection_and_nonstring_identifiers_are_rejected_before_network(self):
        gateway = Razorpay(session=Mock())
        for method in (gateway.fetch_payment, gateway.fetch_order, gateway.fetch_order_payments, gateway.fetch_refund):
            for value in ("../unsafe", "pay_unsafe/route", None, 123, "pay_" + "a" * 100):
                with self.subTest(method=method.__name__, value=value), self.assertRaises(PaymentError):
                    method(value)
        gateway.session.request.assert_not_called()

    def test_non_mapping_gateway_json_is_rejected(self):
        gateway = Razorpay(session=Mock())
        gateway.session.request.return_value.status_code = 200
        for value in ([], None, "invalid", 123):
            gateway.session.request.return_value.json.return_value = value
            with self.subTest(value=value), self.assertRaises(PaymentError):
                gateway.fetch_payment("pay_valid")

    def test_non_success_and_redirect_responses_are_rejected_without_reading_json(self):
        gateway = Razorpay(session=Mock())
        for status in (301, 302, 307, 400, 500):
            gateway.session.request.return_value.status_code = status
            with self.subTest(status=status), self.assertRaises(PaymentError):
                gateway.fetch_payment("pay_valid")
        gateway.session.request.return_value.json.assert_not_called()

    def test_transport_timeout_is_sanitized(self):
        gateway = Razorpay(session=Mock())
        gateway.session.request.side_effect = requests.Timeout("private token and customer data")
        with self.assertRaises(PaymentError) as caught:
            gateway.fetch_payment("pay_valid")
        self.assertNotIn("private", str(caught.exception))

    def test_malformed_signatures_do_not_raise(self):
        for signature in ("é" * 64, None, b"a" * 64, [], "a" * 63, "g" * 64):
            with self.subTest(signature=signature):
                self.assertFalse(verify_webhook(b"{}", signature, "test-only"))

    def test_refund_amount_must_be_positive_integer(self):
        gateway = Razorpay(session=Mock())
        for amount in (True, False, 0, -1, "100", None):
            with self.subTest(amount=amount), self.assertRaises(PaymentError):
                gateway.refund_payment("pay_valid", amount)
        gateway.session.request.assert_not_called()
