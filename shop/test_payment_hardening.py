"""Payment regression tests use signed fixtures and local PostgreSQL, never real money."""
import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier, Lock
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import AuditEntry, DomainOrder, ManagedDomain, PaymentEvent, RegistrantContact, TLDPrice
from .payments import PaymentError, verify_webhook
from .services import OrderError, create_checkout_order, receive_razorpay_webhook


PAYMENT_SETTINGS = {
    "RAZORPAY_WEBHOOK_SECRET": "local-payment-webhook-secret",
    "RAZORPAY_KEY_ID": "rzp_test_local",
    "RAZORPAY_KEY_SECRET": "local-payment-api-secret",
    "OPENPROVIDER_USERNAME": "local-sandbox-user",
    "OPENPROVIDER_PASSWORD": "local-sandbox-password",
    "OPENPROVIDER_BASE_URL": "https://api.sandbox.openprovider.nl/v1beta",
    "SALES_ENABLED": True,
    "FULFILLMENT_ENABLED": False,
}


def signed_body(message):
    body = json.dumps(message).encode()
    signature = hmac.new(PAYMENT_SETTINGS["RAZORPAY_WEBHOOK_SECRET"].encode(), body, hashlib.sha256).hexdigest()
    return body, signature


def capture_message(order_id="order_local_1", payment_id="pay_local_1", amount=129900,
                    currency="INR", status="captured", event="payment.captured"):
    return {"event": event, "payload": {"payment": {"entity": {
        "id": payment_id, "order_id": order_id, "amount": amount,
        "currency": currency, "status": status,
    }}}}


class PaymentFixtures:
    def make_customer(self, username):
        user = get_user_model().objects.create_user(username, f"{username}@example.test")
        RegistrantContact.objects.create(
            owner=user, first_name="Local", last_name="Customer", email=user.email,
            phone_area_code="11", phone_subscriber_number="12345678",
            street="Fixture Road", street_number="1", city="Delhi", state="Delhi", postal_code="110001",
        )
        return user

    def setUp(self):
        super().setUp()
        self.user = self.make_customer("buyer")
        self.other = self.make_customer("other")
        TLDPrice.objects.create(extension="com", registration_paise=129900, renewal_paise=139900, enabled=True)

    def make_order(self, domain="localexample.com", **changes):
        values = {
            "owner": self.user, "domain": domain, "operation": DomainOrder.REGISTER,
            "amount_paise": 129900, "idempotency_key": domain,
            "razorpay_order_id": "order_local_1",
        }
        values.update(changes)
        return DomainOrder.objects.create(**values)

    def receive(self, message=None, event_id="evt_local_1"):
        body, signature = signed_body(message or capture_message())
        return receive_razorpay_webhook(body, signature, event_id)


@override_settings(**PAYMENT_SETTINGS)
class CapturedPaymentHardeningTests(PaymentFixtures, TestCase):
    def test_early_capture_can_be_replayed_after_local_gateway_binding(self):
        order = self.make_order(razorpay_order_id=None)
        message = capture_message()
        self.assertEqual(self.receive(message), "waiting_order")
        event = PaymentEvent.objects.get()
        self.assertEqual(event.gateway_order_id, "order_local_1")
        self.assertEqual(event.payment_id, "pay_local_1")
        self.assertEqual(event.amount_paise, 129900)
        self.assertEqual(event.currency, "INR")
        self.assertEqual(event.payment_status, "captured")
        order.razorpay_order_id = "order_local_1"
        order.save(update_fields=["razorpay_order_id"])
        self.assertEqual(self.receive(message), "paid")
        self.assertEqual(self.receive(message), "duplicate")
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.PAID)
        self.assertEqual(order.razorpay_payment_id, "pay_local_1")
        self.assertEqual(AuditEntry.objects.filter(order=order, action="payment_captured").count(), 1)

    def test_replay_command_recovers_locally_stored_signed_evidence_without_network(self):
        order = self.make_order(razorpay_order_id=None)
        self.receive()
        order.razorpay_order_id = "order_local_1"
        order.save(update_fields=["razorpay_order_id"])
        with patch("shop.payments.requests.Session.request") as network:
            call_command("reconcile_payment_events", stdout=StringIO())
            call_command("reconcile_payment_events", stdout=StringIO())
        network.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.PAID)
        self.assertEqual(AuditEntry.objects.filter(order=order, action="payment_captured").count(), 1)

    def test_legacy_digest_only_event_requires_fresh_signed_redelivery_to_recover(self):
        order = self.make_order()
        body, signature = signed_body(capture_message())
        event = PaymentEvent.objects.create(
            event_id="evt_legacy", event_type="payment.captured",
            payload_sha256=hashlib.sha256(body).hexdigest(), outcome="ignored",
        )
        call_command("reconcile_payment_events", stdout=StringIO())
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.AWAITING)
        with self.assertRaises(OrderError):
            receive_razorpay_webhook(body, "wrong", "evt_legacy")
        event.refresh_from_db()
        self.assertEqual(event.payment_id, "")
        self.assertEqual(receive_razorpay_webhook(body, signature, "evt_legacy"), "paid")
        event.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(event.payment_id, "pay_local_1")
        self.assertEqual(order.status, DomainOrder.PAID)
        self.assertEqual(PaymentEvent.objects.count(), 1)

    def test_failed_and_authorized_events_do_not_pay_or_downgrade_captured_order(self):
        order = self.make_order()
        for event_id, event, status in (
            ("evt_failed_first", "payment.failed", "failed"),
            ("evt_authorized", "payment.authorized", "authorized"),
        ):
            self.receive(capture_message(event=event, status=status), event_id)
            order.refresh_from_db()
            self.assertEqual(order.status, DomainOrder.AWAITING)
        self.receive(event_id="evt_captured")
        self.receive(capture_message(event="payment.failed", status="failed"), "evt_failed_late")
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.PAID)
        self.assertEqual(order.razorpay_payment_id, "pay_local_1")

    def test_different_event_ids_for_one_capture_never_repeat_the_payment_transition(self):
        order = self.make_order()
        self.receive(event_id="evt_first")
        self.receive(event_id="evt_second")
        self.assertEqual(PaymentEvent.objects.count(), 2)
        self.assertEqual(AuditEntry.objects.filter(order=order, action="payment_captured").count(), 1)

    def test_reused_event_id_with_different_body_is_rejected_without_mutation(self):
        order = self.make_order()
        self.receive()
        with self.assertRaises(OrderError):
            self.receive(capture_message(payment_id="pay_conflicting"))
        order.refresh_from_db()
        self.assertEqual(order.razorpay_payment_id, "pay_local_1")
        self.assertEqual(PaymentEvent.objects.count(), 1)

    def test_payment_cannot_be_attached_to_a_second_customers_order(self):
        original = self.make_order(status=DomainOrder.PAID, razorpay_payment_id="pay_local_1")
        second = self.make_order(
            "secondexample.com", owner=self.other, razorpay_order_id="order_other_1",
        )
        self.receive(capture_message(order_id="order_other_1"), "evt_conflicting_payment")
        second.refresh_from_db()
        original.refresh_from_db()
        self.assertEqual(second.status, DomainOrder.AWAITING)
        self.assertIsNone(second.razorpay_payment_id)
        self.assertEqual(original.owner, self.user)
        self.assertEqual(original.razorpay_payment_id, "pay_local_1")

    def test_mismatched_amount_currency_or_capture_status_never_pays(self):
        order = self.make_order()
        for index, changes in enumerate(({"amount": 1}, {"currency": "USD"})):
            with self.subTest(changes=changes):
                self.receive(capture_message(**changes), f"evt_mismatch_{index}")
                order.refresh_from_db()
                self.assertEqual(order.status, DomainOrder.AWAITING)
                self.assertIsNone(order.razorpay_payment_id)
        with self.assertRaises(OrderError):
            self.receive(capture_message(status="authorized"), "evt_bad_capture_status")

    def test_signed_payload_does_not_store_contact_or_card_details(self):
        self.make_order()
        message = capture_message()
        message["payload"]["payment"]["entity"].update({
            "email": "private-recipient@example.test", "contact": "private-phone",
            "notes": {"sensitive": "private-customer-note"},
        })
        self.receive(message)
        stored = str(PaymentEvent.objects.get().__dict__)
        for sensitive in ("private-recipient", "private-phone", "private-customer-note"):
            self.assertNotIn(sensitive, stored)

    def test_malformed_signed_envelopes_return_400_without_marking_paid(self):
        order = self.make_order()
        malformed = (
            [], None, "not-an-object", {"event": []},
            {"event": "payment.captured", "payload": []},
            {"event": "payment.captured", "payload": {"payment": []}},
            {"event": "payment.captured", "payload": {"payment": {"entity": []}}},
            capture_message(amount=True), capture_message(amount="129900"), capture_message(amount=-1),
            capture_message(order_id="order_../../other"), capture_message(payment_id="pay_" + "x" * 100),
        )
        for index, message in enumerate(malformed):
            with self.subTest(message=message):
                body, signature = signed_body(message)
                response = self.client.post(
                    reverse("razorpay_webhook"), data=body, content_type="application/json",
                    HTTP_X_RAZORPAY_SIGNATURE=signature, HTTP_X_RAZORPAY_EVENT_ID=f"evt_bad_{index}",
                )
                self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.AWAITING)

    def test_non_ascii_or_invalid_signatures_fail_without_server_error(self):
        order = self.make_order()
        body, _ = signed_body(capture_message())
        for signature in ("é" * 64, "0" * 63, "g" * 64, "", "0" * 64):
            with self.subTest(signature=signature):
                self.assertFalse(verify_webhook(body, signature, PAYMENT_SETTINGS["RAZORPAY_WEBHOOK_SECRET"]))
                response = self.client.post(
                    reverse("razorpay_webhook"), data=body, content_type="application/json",
                    HTTP_X_RAZORPAY_SIGNATURE=signature, HTTP_X_RAZORPAY_EVENT_ID="evt_bad_signature",
                )
                self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.AWAITING)
        self.assertFalse(PaymentEvent.objects.exists())

    def test_browser_callback_cannot_change_payment_state(self):
        order = self.make_order()
        self.client.force_login(self.user)
        response = self.client.post(reverse("order_detail", args=[order.pk]), {
            "status": "paid", "razorpay_payment_id": "pay_browser_claim",
        })
        self.assertEqual(response.status_code, 405)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.AWAITING)
        self.assertIsNone(order.razorpay_payment_id)

    def test_order_page_hides_payment_button_and_gateway_script_when_sales_disabled(self):
        order = self.make_order()
        self.client.force_login(self.user)
        url = reverse("order_detail", args=[order.pk])
        enabled = self.client.get(url)
        self.assertContains(enabled, 'id="pay-btn"')
        self.assertContains(enabled, "https://checkout.razorpay.com/v1/checkout.js")
        with override_settings(SALES_ENABLED=False):
            disabled = self.client.get(url)
        self.assertNotContains(disabled, 'id="pay-btn"')
        self.assertNotContains(disabled, "https://checkout.razorpay.com/v1/checkout.js")
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.AWAITING)


@override_settings(**PAYMENT_SETTINGS)
class CheckoutHardeningTests(PaymentFixtures, TestCase):
    def checkout(self, **changes):
        values = {"owner": self.user, "domain": "localexample.com", "operation": DomainOrder.REGISTER,
                  "price": 129900, "key": "local-checkout-request"}
        values.update(changes)
        return create_checkout_order(**values)

    def gateway_order(self, local):
        return {"id": "order_created_1", "amount": local.amount_paise, "currency": "INR"}

    def test_normalized_domain_and_same_key_return_one_original_checkout(self):
        with patch("shop.services.Razorpay") as gateway:
            gateway.return_value.create_order.side_effect = self.gateway_order
            first = self.checkout(domain="LocalExample.COM")
            second = self.checkout()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.domain, "localexample.com")
        self.assertEqual(gateway.return_value.create_order.call_count, 1)

    def test_same_key_cannot_be_reused_for_another_domain_or_operation(self):
        with patch("shop.services.Razorpay") as gateway:
            gateway.return_value.create_order.side_effect = self.gateway_order
            self.checkout()
            for changes in ({"domain": "differentexample.com"}, {"operation": DomainOrder.RENEW}):
                with self.subTest(changes=changes), self.assertRaises(OrderError):
                    self.checkout(**changes)
        self.assertEqual(gateway.return_value.create_order.call_count, 1)

    def test_completed_registration_retry_returns_original_after_domain_link_is_populated(self):
        managed = ManagedDomain.objects.create(
            owner=self.user, name="localexample.com", provider_id=98765, status="active",
        )
        original = self.make_order(
            status=DomainOrder.ACTIVE, managed_domain=managed, idempotency_key="local-checkout-request",
        )
        with patch("shop.services.Razorpay") as gateway:
            repeated = self.checkout()
        gateway.assert_not_called()
        self.assertEqual(repeated.pk, original.pk)
        self.assertEqual(repeated.managed_domain_id, managed.pk)

    def test_duplicate_registration_cannot_take_another_payment_or_cross_customer(self):
        self.make_order()
        with patch("shop.services.Razorpay") as gateway:
            for owner in (self.user, self.other):
                with self.subTest(owner=owner.pk), self.assertRaises(OrderError):
                    self.checkout(owner=owner, key=f"second-{owner.pk}")
        gateway.assert_not_called()

    def test_invalid_operation_price_or_domain_never_calls_gateway(self):
        with patch("shop.services.Razorpay") as gateway:
            for changes in (
                {"operation": "transfer"}, {"price": 0}, {"price": -1}, {"price": True},
                {"price": "129900"}, {"domain": "bad..com"}, {"domain": "a.b.com"},
                {"key": ""}, {"key": "x" * 65},
            ):
                with self.subTest(changes=changes), self.assertRaises(OrderError):
                    self.checkout(**changes)
        gateway.assert_not_called()
        self.assertFalse(DomainOrder.objects.exists())

    def test_renewal_requires_owner_and_matching_active_domain(self):
        managed = ManagedDomain.objects.create(
            owner=self.other, name="ownedexample.com", provider_id=12345, status="active",
        )
        with patch("shop.services.Razorpay") as gateway:
            for changes in (
                {"owner": self.user, "domain": managed.name},
                {"owner": self.other, "domain": "unrelatedexample.com"},
            ):
                with self.subTest(changes=changes), self.assertRaises(OrderError):
                    self.checkout(operation=DomainOrder.RENEW, price=139900, managed_domain=managed, **changes)
            managed.status = "pending"
            managed.save(update_fields=["status"])
            with self.assertRaises(OrderError):
                self.checkout(owner=self.other, domain=managed.name, operation=DomainOrder.RENEW,
                              price=139900, managed_domain=managed)
        gateway.assert_not_called()

    def test_renewal_reloads_domain_ownership_and_status_instead_of_trusting_stale_instance(self):
        managed = ManagedDomain.objects.create(
            owner=self.user, name="ownedexample.com", provider_id=54321, status="active",
        )
        with patch("shop.services.Razorpay") as gateway:
            ManagedDomain.objects.filter(pk=managed.pk).update(owner=self.other)
            with self.assertRaises(OrderError):
                self.checkout(domain=managed.name, operation=DomainOrder.RENEW,
                              price=139900, managed_domain=managed)
            ManagedDomain.objects.filter(pk=managed.pk).update(owner=self.user, status="pending")
            with self.assertRaises(OrderError):
                self.checkout(domain=managed.name, operation=DomainOrder.RENEW,
                              price=139900, managed_domain=managed)
        gateway.assert_not_called()
        self.assertFalse(DomainOrder.objects.exists())

    def test_gateway_timeout_preserves_one_review_order_and_retry_does_not_repost(self):
        with patch("shop.services.Razorpay") as gateway:
            gateway.return_value.create_order.side_effect = PaymentError("private gateway timeout")
            with self.assertRaises(OrderError):
                self.checkout()
            original = DomainOrder.objects.get()
            self.assertEqual(original.status, DomainOrder.REVIEW)
            repeated = self.checkout()
        self.assertEqual(repeated.pk, original.pk)
        self.assertEqual(gateway.return_value.create_order.call_count, 1)
        self.assertNotIn("private", original.provider_message)

    def test_bad_gateway_amount_or_currency_or_identifier_stops_for_review(self):
        for response in (
            {"id": "order_local_1", "amount": 1, "currency": "INR"},
            {"id": "order_local_1", "amount": 129900, "currency": "USD"},
            {"id": "wrong", "amount": 129900, "currency": "INR"},
        ):
            with self.subTest(response=response):
                DomainOrder.objects.all().delete()
                with patch("shop.services.Razorpay") as gateway:
                    gateway.return_value.create_order.return_value = response
                    with self.assertRaises(OrderError):
                        self.checkout()
                self.assertEqual(DomainOrder.objects.get().status, DomainOrder.REVIEW)


@override_settings(**PAYMENT_SETTINGS)
class PaymentReconciliationTests(PaymentFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.order = self.make_order(razorpay_order_id=None, status=DomainOrder.REVIEW)

    def remote_order(self, **changes):
        remote = {"id": "order_local_1", "receipt": str(self.order.pk), "amount": 129900,
                  "currency": "INR", "status": "paid"}
        remote.update(changes)
        return remote

    def reconcile(self, **options):
        return call_command("reconcile_payment", str(self.order.pk),
                            gateway_order_id="order_local_1", stdout=StringIO(), **options)

    def test_gateway_get_can_recover_order_identity_but_cannot_invent_signed_payment(self):
        with patch("shop.management.commands.reconcile_payment.Razorpay") as gateway:
            gateway.return_value.fetch_order.return_value = self.remote_order()
            self.reconcile()
        gateway.return_value.fetch_order.assert_called_once_with("order_local_1")
        gateway.return_value.create_order.assert_not_called()
        gateway.return_value.refund_payment.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.razorpay_order_id, "order_local_1")
        self.assertEqual(self.order.status, DomainOrder.AWAITING)
        self.assertIsNone(self.order.razorpay_payment_id)
        self.assertFalse(PaymentEvent.objects.exists())

    def test_gateway_identity_recovery_replays_only_existing_signed_capture(self):
        self.assertEqual(self.receive(), "waiting_order")
        with patch("shop.management.commands.reconcile_payment.Razorpay") as gateway:
            gateway.return_value.fetch_order.return_value = self.remote_order()
            self.reconcile()
            self.reconcile()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, DomainOrder.PAID)
        self.assertEqual(self.order.razorpay_payment_id, "pay_local_1")
        self.assertEqual(AuditEntry.objects.filter(order=self.order, action="payment_captured").count(), 1)

    def test_mismatched_gateway_identity_receipt_amount_currency_or_status_does_not_bind(self):
        for response in (
            self.remote_order(receipt="another-customers-local-order"),
            self.remote_order(amount=1), self.remote_order(currency="USD"),
            self.remote_order(id="order_other"), self.remote_order(status="refunded"),
            self.remote_order(amount=True), [],
        ):
            with self.subTest(response=response):
                with patch("shop.management.commands.reconcile_payment.Razorpay") as gateway:
                    gateway.return_value.fetch_order.return_value = response
                    with self.assertRaises(CommandError):
                        self.reconcile()
                self.order.refresh_from_db()
                self.assertIsNone(self.order.razorpay_order_id)
                self.assertEqual(self.order.status, DomainOrder.REVIEW)

    def test_gateway_timeout_is_safe_and_never_retries_creation(self):
        with patch("shop.management.commands.reconcile_payment.Razorpay") as gateway:
            gateway.return_value.fetch_order.side_effect = PaymentError("private gateway detail")
            with self.assertRaises(CommandError) as raised:
                self.reconcile()
        self.assertNotIn("private", str(raised.exception))
        gateway.return_value.create_order.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, DomainOrder.REVIEW)
        self.assertIsNone(self.order.razorpay_order_id)

    def test_gateway_reconciliation_cannot_clear_registrar_or_refund_review(self):
        for changes in (
            {"provider_result_id": 123},
            {"razorpay_payment_id": "pay_existing"},
            {"refund_attempted_at": timezone.now()},
        ):
            with self.subTest(changes=changes):
                DomainOrder.objects.filter(pk=self.order.pk).update(**changes)
                with patch("shop.management.commands.reconcile_payment.Razorpay") as gateway:
                    gateway.return_value.fetch_order.return_value = self.remote_order()
                    with self.assertRaises(CommandError):
                        self.reconcile()
                self.order.refresh_from_db()
                self.assertEqual(self.order.status, DomainOrder.REVIEW)
                self.assertIsNone(self.order.razorpay_order_id)
                DomainOrder.objects.filter(pk=self.order.pk).update(
                    provider_result_id=None, razorpay_payment_id=None, refund_attempted_at=None,
                )

    def test_gateway_identifier_cannot_be_rebound_from_another_customer(self):
        self.make_order("anotherexample.com", owner=self.other)
        with patch("shop.management.commands.reconcile_payment.Razorpay") as gateway:
            gateway.return_value.fetch_order.return_value = self.remote_order()
            with self.assertRaises(CommandError):
                self.reconcile()
        self.order.refresh_from_db()
        self.assertIsNone(self.order.razorpay_order_id)
        self.assertEqual(self.order.status, DomainOrder.REVIEW)

    def test_live_lookup_requires_explicit_operator_option(self):
        with override_settings(RAZORPAY_KEY_ID="rzp_live_local_fixture"):
            with patch("shop.management.commands.reconcile_payment.Razorpay") as gateway:
                with self.assertRaises(CommandError):
                    self.reconcile()
                gateway.assert_not_called()
                gateway.return_value.fetch_order.return_value = self.remote_order()
                self.reconcile(allow_live=True)
                gateway.return_value.create_order.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, DomainOrder.AWAITING)

    def test_reconciliation_commands_reject_unknown_local_orders_cleanly(self):
        for command, arguments in (
            ("reconcile_payment", ["not-a-uuid"]),
            ("reconcile_payment_events", ["--order-id", "not-a-uuid"]),
        ):
            with self.subTest(command=command), self.assertRaises(CommandError):
                call_command(command, *arguments, stdout=StringIO())


@skipUnless(connection.vendor == "postgresql", "Payment race guarantees require PostgreSQL")
@override_settings(**PAYMENT_SETTINGS)
class PaymentConcurrencyTests(PaymentFixtures, TransactionTestCase):
    def concurrent(self, operation, workers=4):
        barrier = Barrier(workers)

        def invoke(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation(index)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            return list(executor.map(invoke, range(workers)))

    def test_simultaneous_same_checkout_key_creates_gateway_order_once(self):
        lock = Lock()
        calls = []

        def create_remote(local):
            with lock:
                calls.append(local.pk)
            return {"id": "order_once", "amount": local.amount_paise, "currency": "INR"}

        def create(_):
            return create_checkout_order(owner=self.user, domain="raceexample.com",
                                         operation=DomainOrder.REGISTER, price=129900, key="same-key").pk

        with patch("shop.services.Razorpay") as gateway:
            gateway.return_value.create_order.side_effect = create_remote
            outcomes = self.concurrent(create)
        self.assertEqual(len(set(outcomes)), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(DomainOrder.objects.count(), 1)

    def test_simultaneous_different_keys_and_owners_cannot_create_two_registrations(self):
        def create(index):
            try:
                return create_checkout_order(
                    owner=self.user if index % 2 == 0 else self.other, domain="raceexample.com",
                    operation=DomainOrder.REGISTER, price=129900, key=f"request-{index}",
                ).pk
            except OrderError:
                return None

        with patch("shop.services.Razorpay") as gateway:
            gateway.return_value.create_order.side_effect = lambda local: {
                "id": "order_once", "amount": local.amount_paise, "currency": "INR",
            }
            outcomes = self.concurrent(create)
        self.assertEqual(sum(result is not None for result in outcomes), 1)
        self.assertEqual(gateway.return_value.create_order.call_count, 1)
        self.assertEqual(DomainOrder.objects.count(), 1)

    def test_simultaneous_capture_replays_transition_and_audit_once(self):
        order = self.make_order()
        outcomes = self.concurrent(lambda index: self.receive(event_id=f"evt_parallel_{index}"))
        self.assertEqual(outcomes.count("paid"), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.PAID)
        self.assertEqual(AuditEntry.objects.filter(order=order, action="payment_captured").count(), 1)

    def test_simultaneous_renewals_for_one_domain_create_one_payment_order(self):
        managed = ManagedDomain.objects.create(
            owner=self.user, name="renewexample.com", provider_id=6789, status="active",
        )

        def create(index):
            try:
                return create_checkout_order(
                    owner=self.user, domain=managed.name, operation=DomainOrder.RENEW,
                    price=139900, key=f"renewal-{index}", managed_domain=managed,
                ).pk
            except OrderError:
                return None

        with patch("shop.services.Razorpay") as gateway:
            gateway.return_value.create_order.side_effect = lambda local: {
                "id": "order_renew_once", "amount": local.amount_paise, "currency": "INR",
            }
            outcomes = self.concurrent(create)
        self.assertEqual(sum(result is not None for result in outcomes), 1)
        self.assertEqual(gateway.return_value.create_order.call_count, 1)
        self.assertEqual(DomainOrder.objects.count(), 1)
