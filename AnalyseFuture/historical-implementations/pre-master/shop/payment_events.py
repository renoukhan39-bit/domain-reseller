"""Durable, minimal evidence from signed Razorpay captured-payment webhooks."""
import hashlib
import json
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .exceptions import OrderError
from .models import AuditEntry, DomainOrder, PaymentEvent
from .payments import verify_webhook


def gateway_identifier(value, prefix):
    return isinstance(value, str) and len(value) <= 80 and re.fullmatch(prefix + r"_[A-Za-z0-9_]+", value) is not None


def _apply_event(event):
    """Caller locks event; order lock + payment unique index serialize transitions."""
    order = DomainOrder.objects.select_for_update().filter(razorpay_order_id=event.gateway_order_id).first()
    if order is None:
        return "waiting_order"
    if (event.payment_status != "captured" or event.currency != order.currency
            or event.amount_paise != order.amount_paise):
        return "unmatched_payment_review"
    if order.razorpay_payment_id == event.payment_id and order.status in (
            DomainOrder.PAID, DomainOrder.PROCESSING, DomainOrder.ACTIVE):
        return "already_paid"
    if order.status != DomainOrder.AWAITING or order.razorpay_payment_id:
        return "unmatched_payment_review"
    if DomainOrder.objects.filter(razorpay_payment_id=event.payment_id).exclude(pk=order.pk).exists():
        return "payment_conflict_review"
    try:
        # Savepoint keeps an identifier race from discarding the signed event.
        with transaction.atomic():
            order.razorpay_payment_id = event.payment_id
            order.status = DomainOrder.PAID
            order.save(update_fields=["status", "razorpay_payment_id", "updated_at"])
            AuditEntry.objects.create(actor=order.owner, order=order, action="payment_captured")
    except IntegrityError:
        return "payment_conflict_review"
    return "paid"


def replay_payment_events(gateway_order_id=None):
    """Replay retained signed evidence only; no gateway or registrar API calls."""
    pending = PaymentEvent.objects.filter(outcome="waiting_order", event_type="payment.captured")
    if gateway_order_id:
        pending = pending.filter(gateway_order_id=gateway_order_id)
    counts = {}
    for pk in pending.order_by("pk").values_list("pk", flat=True).iterator():
        with transaction.atomic():
            event = PaymentEvent.objects.select_for_update().get(pk=pk)
            if event.outcome != "waiting_order":
                continue
            event.outcome = _apply_event(event)
            event.processed_at = timezone.now()
            event.save(update_fields=["outcome", "processed_at"])
            counts[event.outcome] = counts.get(event.outcome, 0) + 1
    return counts


def receive_razorpay_webhook(body, signature, event_id):
    if not verify_webhook(body, signature, settings.RAZORPAY_WEBHOOK_SECRET):
        raise OrderError("Invalid webhook signature")
    if not isinstance(event_id, str) or not event_id or len(event_id) > 130:
        raise OrderError("Missing event identifier")
    try:
        message = json.loads(body)
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        raise OrderError("Invalid webhook payload") from exc
    if not isinstance(message, dict) or not isinstance(message.get("event"), str) or len(message["event"]) > 60:
        raise OrderError("Invalid webhook payload")
    event_type = message["event"]
    evidence = {}
    if event_type == "payment.captured":
        try:
            payment = message["payload"]["payment"]["entity"]
            if (not isinstance(payment, dict) or not gateway_identifier(payment.get("id"), "pay")
                    or not gateway_identifier(payment.get("order_id"), "order")
                    or type(payment.get("amount")) is not int or not 0 < payment["amount"] <= 2147483647
                    or payment.get("status") != "captured" or not isinstance(payment.get("currency"), str)
                    or len(payment["currency"]) != 3):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise OrderError("Invalid captured payment payload") from None
        evidence = {"gateway_order_id": payment["order_id"], "payment_id": payment["id"],
                    "amount_paise": payment["amount"], "currency": payment["currency"], "payment_status": "captured"}
    digest = hashlib.sha256(body).hexdigest()
    with transaction.atomic():
        event, created = PaymentEvent.objects.select_for_update().get_or_create(event_id=event_id,
            defaults={"event_type": event_type, "payload_sha256": digest, **evidence})
        if not created:
            if event.payload_sha256 != digest:
                raise OrderError("Event ID collision")
            # Older versions retained only a digest and acknowledged early captures
            # as ignored. A fresh, correctly signed redelivery can recover evidence.
            if event.outcome == "ignored" and event_type == "payment.captured" and not event.payment_id:
                for name, value in evidence.items():
                    setattr(event, name, value)
                event.outcome = "waiting_order"
                event.save(update_fields=[*evidence, "outcome"])
            if event.outcome != "waiting_order":
                return "duplicate"
        event.outcome = _apply_event(event) if event_type == "payment.captured" else "ignored"
        event.processed_at = timezone.now()
        event.save(update_fields=["outcome", "processed_at"])
    return event.outcome
