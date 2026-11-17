"""M3-08: deterministic signed-webhook redelivery and out-of-order safety tests.

These fixtures are synthetic and never contact Razorpay or a registrar.
"""
import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from unittest import skipUnless

from .models import AuditEntry, DomainOrder, PaymentEvent
from .services import OrderError, receive_razorpay_webhook

WEBHOOK_SECRET = "synthetic-webhook-secret"


def signed_message(event="payment.captured", gateway_order="order_m308",
                   payment_id="pay_m308", amount=50000, currency="INR",
                   status="captured"):
    payload = {
        "event": event,
        "payload": {"payment": {"entity": {
            "id": payment_id,
            "order_id": gateway_order,
            "amount": amount,
            "currency": currency,
            "status": status,
        }}},
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return raw, hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()


@override_settings(RAZORPAY_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookReplayTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="webhook-buyer", email="buyer@example.test", password="unused-test-password"
        )
        self.order = DomainOrder.objects.create(
            owner=self.user, domain="webhooksafe.example",
            operation=DomainOrder.REGISTER, amount_paise=50000,
            idempotency_key="webhook-replay",
        )
        self.body, self.signature = signed_message()

    def post_webhook(self, body=None, signature=None, event_id="evt_m308"):
        return self.client.post(
            reverse("razorpay_webhook"),
            data=body if body is not None else self.body,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature if signature is not None else self.signature,
            HTTP_X_RAZORPAY_EVENT_ID=event_id,
        )

    def test_signed_capture_before_order_mapping_reconciles_only_on_exact_redelivery(self):
        self.assertEqual(receive_razorpay_webhook(self.body, self.signature, "evt_1"),
                         "unmatched_payment_review")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, DomainOrder.AWAITING)
        event = PaymentEvent.objects.get(event_id="evt_1")
        self.assertEqual(event.outcome, "unmatched_payment_review")
        self.assertEqual(event.payload_sha256, hashlib.sha256(self.body).hexdigest())

        self.order.razorpay_order_id = "order_m308"
        self.order.save(update_fields=["razorpay_order_id"])
        self.assertEqual(receive_razorpay_webhook(self.body, self.signature, "evt_1"), "paid")
        self.assertEqual(receive_razorpay_webhook(self.body, self.signature, "evt_1"), "duplicate")

        self.order.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual(self.order.status, DomainOrder.PAID)
        self.assertEqual(self.order.razorpay_payment_id, "pay_m308")
        self.assertEqual(event.outcome, "paid")
        self.assertEqual(PaymentEvent.objects.count(), 1)
        self.assertEqual(AuditEntry.objects.filter(action="payment_captured").count(), 1)

    def test_wrong_amount_stays_unmatched_after_late_order_mapping(self):
        raw, sig = signed_message(amount=100)
        self.assertEqual(receive_razorpay_webhook(raw, sig, "evt_wrong"), "unmatched_payment_review")
        self.order.razorpay_order_id = "order_m308"
        self.order.save(update_fields=["razorpay_order_id"])
        self.assertEqual(receive_razorpay_webhook(raw, sig, "evt_wrong"), "unmatched_payment_review")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, DomainOrder.AWAITING)
        self.assertFalse(self.order.razorpay_payment_id)

    def test_wrong_currency_and_uncaptured_status_never_pay(self):
        self.order.razorpay_order_id = "order_m308"
        self.order.save(update_fields=["razorpay_order_id"])
        for number, fields in enumerate(({"currency": "USD"}, {"status": "authorized"})):
            raw, sig = signed_message(**fields)
            self.assertEqual(receive_razorpay_webhook(raw, sig, f"evt_invalid_{number}"),
                             "unmatched_payment_review")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, DomainOrder.AWAITING)
        self.assertEqual(AuditEntry.objects.filter(action="payment_reconciliation_needed").count(), 2)

    def test_different_signed_payload_with_same_event_id_is_rejected(self):
        receive_razorpay_webhook(self.body, self.signature, "evt_collision")
        changed_body, changed_signature = signed_message(amount=100)
        with self.assertRaises(OrderError):
            receive_razorpay_webhook(changed_body, changed_signature, "evt_collision")
        self.assertEqual(PaymentEvent.objects.count(), 1)

    def test_second_event_id_same_payment_is_recorded_without_second_capture(self):
        self.order.razorpay_order_id = "order_m308"
        self.order.save(update_fields=["razorpay_order_id"])
        self.assertEqual(receive_razorpay_webhook(self.body, self.signature, "evt_first"), "paid")
        self.assertEqual(receive_razorpay_webhook(self.body, self.signature, "evt_second"),
                         "already_recorded")
        self.assertEqual(AuditEntry.objects.filter(action="payment_captured").count(), 1)
        self.assertEqual(PaymentEvent.objects.count(), 2)

    def test_second_distinct_payment_on_same_order_requires_review(self):
        self.order.razorpay_order_id = "order_m308"
        self.order.save(update_fields=["razorpay_order_id"])
        receive_razorpay_webhook(self.body, self.signature, "evt_first")
        other, sig = signed_message(payment_id="pay_other")
        self.assertEqual(receive_razorpay_webhook(other, sig, "evt_second"),
                         "unmatched_payment_review")
        self.order.refresh_from_db()
        self.assertEqual(self.order.razorpay_payment_id, "pay_m308")
        self.assertEqual(AuditEntry.objects.filter(action="payment_captured").count(), 1)

    def test_authorized_event_before_capture_does_not_block_later_capture(self):
        self.order.razorpay_order_id = "order_m308"
        self.order.save(update_fields=["razorpay_order_id"])
        other, signature = signed_message(event="payment.authorized")
        self.assertEqual(receive_razorpay_webhook(other, signature, "evt_auth"), "ignored")
        self.assertEqual(receive_razorpay_webhook(self.body, self.signature, "evt_capture"), "paid")

    def test_malformed_signed_json_or_shape_returns_400_without_creating_event(self):
        for index, raw in enumerate((b"[]", b'{"event": []}',
                                     b'{"event":"payment.captured","payload":{"payment":{"entity":[]}}}')):
            signature = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
            self.assertEqual(self.post_webhook(raw, signature, f"evt_bad_{index}").status_code, 400)
        self.assertFalse(PaymentEvent.objects.exists())

    def test_invalid_signature_and_missing_id_are_rejected(self):
        self.assertEqual(self.post_webhook(signature="invalid").status_code, 400)
        self.assertEqual(self.post_webhook(event_id="").status_code, 400)
        self.assertFalse(PaymentEvent.objects.exists())

    def test_http_redelivery_does_not_depend_on_sales_feature_flags(self):
        # A valid signed gateway capture is evidence even if sales are now paused.
        self.order.razorpay_order_id = "order_m308"
        self.order.save(update_fields=["razorpay_order_id"])
        with override_settings(SALES_ENABLED=False, FULFILLMENT_ENABLED=False):
            self.assertEqual(self.post_webhook().status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, DomainOrder.PAID)
        self.assertFalse(self.order.managed_domain_id)


@skipUnless(connection.vendor == "postgresql", "Row-lock concurrency requires PostgreSQL")
@override_settings(RAZORPAY_WEBHOOK_SECRET=WEBHOOK_SECRET)
class ConcurrentCaptureTests(TransactionTestCase):
    def test_distinct_signed_event_ids_concurrently_capture_only_once(self):
        user = get_user_model().objects.create_user("parallel", "parallel@example.test")
        order = DomainOrder.objects.create(
            owner=user, domain="parallel.example",
            operation=DomainOrder.REGISTER, amount_paise=50000,
            idempotency_key="concurrent-payment", razorpay_order_id="order_m308",
        )
        body, signature = signed_message()
        barrier = Barrier(2)

        def deliver(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return receive_razorpay_webhook(body, signature, f"evt_parallel_{index}")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(deliver, range(2)))
        order.refresh_from_db()
        self.assertCountEqual(results, ["paid", "already_recorded"])
        self.assertEqual(order.status, DomainOrder.PAID)
        self.assertEqual(PaymentEvent.objects.count(), 2)
        self.assertEqual(AuditEntry.objects.filter(action="payment_captured").count(), 1)
