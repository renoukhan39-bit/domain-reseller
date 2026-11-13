"""Registrar safety tests use deterministic provider doubles, never real registrations."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from io import StringIO
from threading import Barrier, Lock
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .models import AuditEntry, DomainOrder, ManagedDomain, RegistrantContact
from .providers import ProviderError
from .services import OrderError, fulfill_one


FULFILLMENT_SETTINGS = {
    "RAZORPAY_WEBHOOK_SECRET": "local-fulfillment-signing-secret",
    "RAZORPAY_KEY_ID": "rzp_test_local",
    "RAZORPAY_KEY_SECRET": "local-fulfillment-payment-secret",
    "OPENPROVIDER_USERNAME": "local-sandbox-user",
    "OPENPROVIDER_PASSWORD": "local-sandbox-password",
    "OPENPROVIDER_BASE_URL": "https://api.sandbox.openprovider.nl/v1beta",
    "SALES_ENABLED": True,
    "FULFILLMENT_ENABLED": True,
}


class RegistrarDouble:
    def __init__(self, domain="localexample.com", owner_handle="LOCAL-OWNER", provider_id=1001):
        name, extension = domain.split(".", 1)
        self.details = {
            "id": provider_id, "domain": {"name": name, "extension": extension},
            "owner_handle": owner_handle, "status": "ACT", "expiration_date": "2029-03-01 00:00:00",
        }
        self.register_result = deepcopy(self.details)
        self.renew_result = deepcopy(self.details)
        self.get_responses = []
        self.calls = {"create_contact": 0, "register": 0, "renew": 0, "get_domain": 0}
        self.lock = Lock()

    def count(self, method):
        with self.lock:
            self.calls[method] += 1

    def create_contact(self, payload):
        self.count("create_contact")
        return "LOCAL-OWNER"

    def register(self, domain, owner_handle):
        self.count("register")
        if isinstance(self.register_result, Exception):
            raise self.register_result
        return deepcopy(self.register_result)

    def renew(self, provider_id):
        self.count("renew")
        if isinstance(self.renew_result, Exception):
            raise self.renew_result
        return deepcopy(self.renew_result)

    def get_domain(self, provider_id):
        self.count("get_domain")
        with self.lock:
            details = self.get_responses.pop(0) if self.get_responses else self.details
        if isinstance(details, Exception):
            raise details
        return deepcopy(details)


class FulfillmentFixtures:
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user("registrant", "registrant@example.test")
        self.other = get_user_model().objects.create_user("other", "other@example.test")
        self.contact = RegistrantContact.objects.create(
            owner=self.user, first_name="Local", last_name="Registrant", email=self.user.email,
            phone_area_code="11", phone_subscriber_number="12345678", street="Fixture Road",
            street_number="1", city="Delhi", state="Delhi", postal_code="110001",
            openprovider_handle="LOCAL-OWNER",
        )

    def make_order(self, domain="localexample.com", **changes):
        values = {
            "owner": self.user, "domain": domain, "operation": DomainOrder.REGISTER,
            "amount_paise": 129900, "idempotency_key": domain, "status": DomainOrder.PAID,
            "razorpay_order_id": "order_" + domain.replace(".", ""),
            "razorpay_payment_id": "pay_" + domain.replace(".", ""),
        }
        values.update(changes)
        return DomainOrder.objects.create(**values)

    def make_renewal(self, **changes):
        managed = ManagedDomain.objects.create(
            owner=self.user, name="renewexample.com", provider_id=2001, status="active",
            expires_at=timezone.now() + timedelta(days=100),
        )
        order = self.make_order(managed.name, operation=DomainOrder.RENEW, managed_domain=managed, **changes)
        return order, managed


@override_settings(**FULFILLMENT_SETTINGS)
class FulfillmentSafetyTests(FulfillmentFixtures, TestCase):
    def test_successful_registration_is_not_repeated(self):
        order = self.make_order()
        registrar = RegistrarDouble()
        self.assertTrue(fulfill_one(order.pk, registrar))
        self.assertFalse(fulfill_one(order.pk, registrar))
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.ACTIVE)
        self.assertEqual(order.provider_result_id, 1001)
        self.assertEqual(order.managed_domain.owner, self.user)
        self.assertEqual(order.managed_domain.name, order.domain)
        self.assertEqual(registrar.calls["register"], 1)

    def test_provider_initialization_failure_stops_for_review_without_stranding_processing(self):
        order = self.make_order()
        with patch("shop.services.Openprovider", side_effect=ProviderError("private credential detail")):
            self.assertFalse(fulfill_one(order.pk))
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REVIEW)
        self.assertNotIn("private", order.provider_message)
        self.assertTrue(AuditEntry.objects.filter(order=order).exists())

    def test_registration_timeout_stays_review_and_never_automatically_retries(self):
        order = self.make_order()
        registrar = RegistrarDouble()
        registrar.register_result = ProviderError("private registrar payload")
        self.assertFalse(fulfill_one(order.pk, registrar))
        self.assertFalse(fulfill_one(order.pk, registrar))
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REVIEW)
        self.assertNotIn("private", order.provider_message)
        self.assertEqual(registrar.calls["register"], 1)
        self.assertFalse(ManagedDomain.objects.exists())

    def test_pending_registration_does_not_become_active(self):
        order = self.make_order()
        registrar = RegistrarDouble()
        registrar.register_result["status"] = "REQ"
        registrar.details["status"] = "REQ"
        fulfill_one(order.pk, registrar)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REVIEW)
        self.assertFalse(ManagedDomain.objects.filter(name=order.domain, status="active").exists())

    def test_registration_response_identity_cannot_assign_another_domain_or_registrant(self):
        for field, value in (("domain", {"name": "otherexample", "extension": "com"}),
                             ("owner_handle", "OTHER-OWNER")):
            with self.subTest(field=field):
                DomainOrder.objects.all().delete()
                order = self.make_order()
                registrar = RegistrarDouble()
                registrar.register_result[field] = value
                registrar.details[field] = value
                self.assertFalse(fulfill_one(order.pk, registrar))
                order.refresh_from_db()
                self.assertEqual(order.status, DomainOrder.REVIEW)
                self.assertFalse(ManagedDomain.objects.exists())

    def test_renewal_requires_confirmed_expiry_increase(self):
        order, managed = self.make_renewal()
        before = managed.expires_at
        registrar = RegistrarDouble(managed.name, provider_id=managed.provider_id)
        remote_before = deepcopy(registrar.details)
        remote_before["expiration_date"] = before.isoformat()
        registrar.get_responses = [remote_before, deepcopy(registrar.details)]
        self.assertTrue(fulfill_one(order.pk, registrar))
        order.refresh_from_db()
        managed.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.ACTIVE)
        self.assertGreater(managed.expires_at, before)
        self.assertEqual(registrar.calls["renew"], 1)
        self.assertFalse(fulfill_one(order.pk, registrar))
        self.assertEqual(registrar.calls["renew"], 1)

    def test_missing_unchanged_or_pending_renewal_evidence_keeps_original_expiry_for_review(self):
        for case in ("missing", "unchanged", "pending"):
            with self.subTest(case=case):
                DomainOrder.objects.all().delete()
                ManagedDomain.objects.all().delete()
                order, managed = self.make_renewal()
                before = managed.expires_at
                registrar = RegistrarDouble(managed.name, provider_id=managed.provider_id)
                remote_before = deepcopy(registrar.details)
                remote_before["expiration_date"] = before.isoformat()
                if case == "missing":
                    registrar.details.pop("expiration_date")
                elif case == "unchanged":
                    registrar.details["expiration_date"] = before.isoformat()
                else:
                    registrar.details["status"] = "REQ"
                    registrar.renew_result["status"] = "REQ"
                registrar.get_responses = [remote_before, deepcopy(registrar.details)]
                self.assertFalse(fulfill_one(order.pk, registrar))
                self.assertFalse(fulfill_one(order.pk, registrar))
                order.refresh_from_db()
                managed.refresh_from_db()
                self.assertEqual(order.status, DomainOrder.REVIEW)
                self.assertEqual(managed.expires_at, before)
                self.assertEqual(registrar.calls["renew"], 1)

    def test_already_advanced_remote_expiry_does_not_falsely_confirm_this_renewal(self):
        order, managed = self.make_renewal()
        local_before = managed.expires_at
        registrar = RegistrarDouble(managed.name, provider_id=managed.provider_id)
        # The remote date is already later than stale local data BEFORE the POST,
        # and the provider returns that same date afterwards: this is not proof
        # that this particular renewal completed.
        self.assertFalse(fulfill_one(order.pk, registrar))
        self.assertFalse(fulfill_one(order.pk, registrar))
        order.refresh_from_db()
        managed.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REVIEW)
        self.assertEqual(managed.expires_at, local_before)
        self.assertEqual(registrar.calls["renew"], 1)
        self.assertTrue(AuditEntry.objects.filter(order=order, action="renewal_baseline_verified").exists())

    def test_renewal_can_complete_only_after_advancing_the_current_remote_baseline(self):
        order, managed = self.make_renewal()
        registrar = RegistrarDouble(managed.name, provider_id=managed.provider_id)
        advanced = deepcopy(registrar.details)
        advanced["expiration_date"] = "2030-03-01 00:00:00"
        registrar.get_responses = [deepcopy(registrar.details), advanced]
        self.assertTrue(fulfill_one(order.pk, registrar))
        order.refresh_from_db()
        managed.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.ACTIVE)
        self.assertEqual(managed.expires_at.year, 2030)
        self.assertEqual(registrar.calls["get_domain"], 2)
        self.assertEqual(registrar.calls["renew"], 1)

    def test_remote_baseline_older_than_local_expiry_requires_review_before_renewal_post(self):
        order, managed = self.make_renewal()
        ManagedDomain.objects.filter(pk=managed.pk).update(expires_at=timezone.now() + timedelta(days=2000))
        registrar = RegistrarDouble(managed.name, provider_id=managed.provider_id)
        self.assertFalse(fulfill_one(order.pk, registrar))
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REVIEW)
        self.assertEqual(registrar.calls["renew"], 0)

    def test_renewal_without_baseline_expiry_or_customer_ownership_does_not_call_provider(self):
        for changes in ({"expires_at": None}, {"owner": self.other}):
            with self.subTest(changes=changes):
                DomainOrder.objects.all().delete()
                ManagedDomain.objects.all().delete()
                order, managed = self.make_renewal()
                ManagedDomain.objects.filter(pk=managed.pk).update(**changes)
                registrar = RegistrarDouble(managed.name, provider_id=managed.provider_id)
                self.assertFalse(fulfill_one(order.pk, registrar))
                self.assertEqual(registrar.calls["renew"], 0)
                order.refresh_from_db()
                self.assertEqual(order.status, DomainOrder.REVIEW)

    def test_renewal_remote_identity_must_match_local_domain_provider_id_and_contact(self):
        for field, value in (("id", 9999), ("owner_handle", "OTHER-OWNER"),
                             ("domain", {"name": "differentexample", "extension": "com"})):
            with self.subTest(field=field):
                DomainOrder.objects.all().delete()
                ManagedDomain.objects.all().delete()
                order, managed = self.make_renewal()
                before = managed.expires_at
                registrar = RegistrarDouble(managed.name, provider_id=managed.provider_id)
                registrar.details[field] = value
                self.assertFalse(fulfill_one(order.pk, registrar))
                order.refresh_from_db()
                managed.refresh_from_db()
                self.assertEqual(order.status, DomainOrder.REVIEW)
                self.assertEqual(managed.expires_at, before)

    def test_disabled_fulfillment_never_claims_paid_orders(self):
        order = self.make_order()
        registrar = RegistrarDouble()
        with override_settings(FULFILLMENT_ENABLED=False):
            with self.assertRaises(OrderError):
                fulfill_one(order.pk, registrar)
            output = StringIO()
            call_command("process_orders", stdout=output)
        self.assertIn("disabled", output.getvalue().lower())
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.PAID)
        self.assertEqual(sum(registrar.calls.values()), 0)


@override_settings(**FULFILLMENT_SETTINGS)
class StaleOrderRecoveryTests(FulfillmentFixtures, TestCase):
    def test_stale_processing_is_escalated_once_without_retry_or_network(self):
        old = self.make_order(status=DomainOrder.PROCESSING)
        fresh = self.make_order("freshexample.com", status=DomainOrder.PROCESSING)
        paid = self.make_order("paidexample.com")
        DomainOrder.objects.filter(pk__in=[old.pk, paid.pk]).update(updated_at=timezone.now() - timedelta(hours=2))
        with patch("shop.services.Openprovider") as registrar, patch("shop.payments.Razorpay") as gateway:
            call_command("mark_stale_orders", minutes=30, limit=100, stdout=StringIO())
            first_audits = AuditEntry.objects.filter(order=old).count()
            call_command("mark_stale_orders", minutes=30, limit=100, stdout=StringIO())
        registrar.assert_not_called()
        gateway.assert_not_called()
        old.refresh_from_db()
        fresh.refresh_from_db()
        paid.refresh_from_db()
        self.assertEqual(old.status, DomainOrder.REVIEW)
        self.assertEqual(fresh.status, DomainOrder.PROCESSING)
        self.assertEqual(paid.status, DomainOrder.PAID)
        self.assertEqual(first_audits, 1)
        self.assertEqual(AuditEntry.objects.filter(order=old).count(), 1)

    def test_stale_order_batch_limit_is_respected(self):
        first = self.make_order(status=DomainOrder.PROCESSING)
        second = self.make_order("secondexample.com", status=DomainOrder.PROCESSING)
        DomainOrder.objects.filter(pk__in=[first.pk, second.pk]).update(updated_at=timezone.now() - timedelta(hours=2))
        call_command("mark_stale_orders", minutes=30, limit=1, stdout=StringIO())
        self.assertEqual(DomainOrder.objects.filter(status=DomainOrder.REVIEW).count(), 1)
        self.assertEqual(DomainOrder.objects.filter(status=DomainOrder.PROCESSING).count(), 1)

    def test_stale_command_invalid_bounds_do_not_change_order_state(self):
        order = self.make_order(status=DomainOrder.PROCESSING)
        for options in ({"minutes": 0}, {"minutes": -1}, {"limit": 0}, {"limit": -1}):
            with self.subTest(options=options), self.assertRaises(CommandError):
                call_command("mark_stale_orders", stdout=StringIO(), **options)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.PROCESSING)


@override_settings(**FULFILLMENT_SETTINGS)
class RegistrationReconciliationTests(FulfillmentFixtures, TestCase):
    def reconcile(self, order, registrar, provider_id=1001):
        with patch("shop.management.commands.reconcile_registration.Openprovider", return_value=registrar):
            call_command("reconcile_registration", str(order.pk), provider_id=provider_id, stdout=StringIO())

    def test_readonly_reconciliation_recovers_registration_once_without_posting(self):
        order = self.make_order(status=DomainOrder.REVIEW)
        registrar = RegistrarDouble()
        self.reconcile(order, registrar)
        self.reconcile(order, registrar)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.ACTIVE)
        self.assertEqual(order.managed_domain.owner, self.user)
        self.assertEqual(order.managed_domain.provider_id, 1001)
        self.assertEqual(ManagedDomain.objects.count(), 1)
        self.assertEqual(registrar.calls["register"], 0)
        self.assertEqual(registrar.calls["renew"], 0)
        self.assertEqual(registrar.calls["create_contact"], 0)

    def test_pending_local_domain_is_updated_without_duplicate_registration(self):
        managed = ManagedDomain.objects.create(
            owner=self.user, name="localexample.com", provider_id=1001, status="pending",
        )
        order = self.make_order(status=DomainOrder.REVIEW, managed_domain=managed, provider_result_id=1001)
        registrar = RegistrarDouble()
        self.reconcile(order, registrar)
        managed.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(managed.status, "active")
        self.assertIsNotNone(managed.expires_at)
        self.assertEqual(order.status, DomainOrder.ACTIVE)
        self.assertEqual(order.managed_domain_id, managed.pk)
        self.assertEqual(ManagedDomain.objects.count(), 1)
        self.assertEqual(registrar.calls["register"], 0)

    def test_known_registration_identity_is_retained_after_read_failure_and_reconciled_by_get(self):
        order = self.make_order()
        registrar = RegistrarDouble()
        actual_details = registrar.details
        registrar.details = ProviderError("private lookup result")
        self.assertFalse(fulfill_one(order.pk, registrar))
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REVIEW)
        self.assertEqual(order.provider_result_id, 1001)
        self.assertFalse(ManagedDomain.objects.exists())
        self.assertFalse(fulfill_one(order.pk, registrar))
        registrar.details = actual_details
        self.reconcile(order, registrar)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.ACTIVE)
        self.assertEqual(registrar.calls["register"], 1)

    def test_reconciliation_never_replaces_a_newer_local_expiry(self):
        future = timezone.now() + timedelta(days=3650)
        managed = ManagedDomain.objects.create(owner=self.user, name="localexample.com", provider_id=1001,
                                              status="pending", expires_at=future)
        order = self.make_order(status=DomainOrder.REVIEW, managed_domain=managed, provider_result_id=1001)
        with self.assertRaises(CommandError):
            self.reconcile(order, RegistrarDouble())
        managed.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(managed.expires_at, future)
        self.assertEqual(order.status, DomainOrder.REVIEW)

    def test_reconciliation_rejects_unpaid_pending_refund_or_foreign_remote_identity(self):
        for changes, remote_changes in (
            ({"razorpay_payment_id": None}, {}),
            ({"status": DomainOrder.PAID}, {}),
            ({"refund_attempted_at": timezone.now()}, {}),
            ({"status": DomainOrder.REFUND_REVIEW}, {}),
            ({"provider_result_id": 9999}, {}),
            ({}, {"id": 9999}), ({}, {"owner_handle": "OTHER-OWNER"}),
            ({}, {"domain": {"name": "otherexample", "extension": "com"}}),
            ({}, {"status": "REQ"}), ({}, {"expiration_date": "invalid"}),
        ):
            with self.subTest(changes=changes, remote_changes=remote_changes):
                DomainOrder.objects.all().delete()
                order = self.make_order(status=DomainOrder.REVIEW)
                DomainOrder.objects.filter(pk=order.pk).update(**changes)
                registrar = RegistrarDouble()
                registrar.details.update(remote_changes)
                with self.assertRaises(CommandError):
                    self.reconcile(order, registrar)
                self.assertFalse(ManagedDomain.objects.exists())
                self.assertEqual(registrar.calls["register"], 0)

    def test_reconciliation_does_not_take_a_domain_already_owned_by_another_customer(self):
        order = self.make_order(status=DomainOrder.REVIEW)
        ManagedDomain.objects.create(owner=self.other, name=order.domain, provider_id=1001, status="active")
        registrar = RegistrarDouble()
        with self.assertRaises(CommandError):
            self.reconcile(order, registrar)
        managed = ManagedDomain.objects.get()
        self.assertEqual(managed.owner, self.other)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REVIEW)

    def test_reconciliation_transport_failure_keeps_order_review_and_redacts_remote_error(self):
        order = self.make_order(status=DomainOrder.REVIEW)
        registrar = RegistrarDouble()
        registrar.details = ProviderError("private remote response")
        with self.assertRaises(CommandError) as raised:
            self.reconcile(order, registrar)
        self.assertNotIn("private", str(raised.exception))
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REVIEW)
        self.assertFalse(ManagedDomain.objects.exists())


@skipUnless(connection.vendor == "postgresql", "Registrar race guarantees require PostgreSQL")
@override_settings(**FULFILLMENT_SETTINGS)
class FulfillmentConcurrencyTests(FulfillmentFixtures, TransactionTestCase):
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

    def test_non_durable_outer_transaction_is_rejected_before_registrar_side_effects(self):
        order = self.make_order()
        registrar = RegistrarDouble()
        with transaction.atomic():
            with self.assertRaises(RuntimeError):
                fulfill_one(order.pk, registrar)
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.PAID)
        self.assertEqual(sum(registrar.calls.values()), 0)

    def test_simultaneous_workers_register_one_paid_order_once(self):
        order = self.make_order()
        registrar = RegistrarDouble()
        outcomes = self.concurrent(lambda _: fulfill_one(order.pk, registrar))
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual(registrar.calls["register"], 1)
        self.assertEqual(ManagedDomain.objects.count(), 1)

    def test_late_registration_completion_cannot_clear_operator_review_escalation(self):
        order = self.make_order()
        registrar = RegistrarDouble()
        register = registrar.register

        def escalated_registration(domain, owner_handle):
            result = register(domain, owner_handle)
            DomainOrder.objects.filter(pk=order.pk).update(
                updated_at=timezone.now() - timedelta(hours=2),
            )
            call_command("mark_stale_orders", minutes=30, limit=100, stdout=StringIO())
            return result

        registrar.register = escalated_registration
        self.assertFalse(fulfill_one(order.pk, registrar))
        order.refresh_from_db()
        self.assertEqual(order.status, DomainOrder.REVIEW)
        self.assertEqual(registrar.calls["register"], 1)
        self.assertFalse(fulfill_one(order.pk, registrar))
        self.assertEqual(registrar.calls["register"], 1)

    def test_two_orders_for_one_registrant_create_one_owner_contact(self):
        self.contact.openprovider_handle = ""
        self.contact.save(update_fields=["openprovider_handle"])
        orders = [self.make_order("firstexample.com"), self.make_order("secondexample.com")]
        registrar = RegistrarDouble()

        def register(domain, owner_handle):
            registrar.count("register")
            name, extension = domain.split(".")
            return {"id": 1001 if domain == "firstexample.com" else 1002,
                    "domain": {"name": name, "extension": extension}, "owner_handle": owner_handle,
                    "status": "ACT", "expiration_date": "2029-03-01 00:00:00"}

        def get_domain(provider_id):
            domain = "firstexample.com" if provider_id == 1001 else "secondexample.com"
            name, extension = domain.split(".")
            return {"id": provider_id, "domain": {"name": name, "extension": extension},
                    "owner_handle": "LOCAL-OWNER", "status": "ACT", "expiration_date": "2029-03-01 00:00:00"}

        registrar.register = register
        registrar.get_domain = get_domain
        outcomes = self.concurrent(lambda index: fulfill_one(orders[index].pk, registrar), workers=2)
        self.assertEqual(outcomes.count(True), 2)
        self.assertEqual(registrar.calls["create_contact"], 1)
        self.assertEqual(registrar.calls["register"], 2)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.openprovider_handle, "LOCAL-OWNER")
        self.assertEqual(ManagedDomain.objects.filter(owner=self.user).count(), 2)
