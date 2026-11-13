"""Order/payment business rules and a conservative fulfillment state machine."""
import hashlib
import json
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import AuditEntry, DomainOrder, ManagedDomain, PaymentEvent, RegistrantContact
from .payments import Razorpay, PaymentError, verify_webhook
from .providers import Openprovider, ProviderError, parse_expiry


class OrderError(Exception):
    pass


def sales_ready():
    sandbox = "sandbox.openprovider.nl" in settings.OPENPROVIDER_BASE_URL
    test_key = settings.RAZORPAY_KEY_ID.startswith("rzp_test_")
    live_key = settings.RAZORPAY_KEY_ID.startswith("rzp_live_")
    # This prevents charging real money for sandbox domains, and using
    # a test payment to buy a real live registrar domain.
    matching_environments = (sandbox and test_key) or (not sandbox and live_key)
    return bool(settings.SALES_ENABLED and matching_environments and
            settings.RAZORPAY_KEY_SECRET and settings.RAZORPAY_WEBHOOK_SECRET and
            settings.OPENPROVIDER_USERNAME and settings.OPENPROVIDER_PASSWORD)


def fulfillment_ready():
    return settings.FULFILLMENT_ENABLED and sales_ready()


def create_checkout_order(*, owner, domain, operation, price, key, managed_domain=None):
    """Idempotent local order; gateway HTTP timeout leaves order for operator reconciliation."""
    if not sales_ready():
        raise OrderError("Sales are not enabled")
    if not RegistrantContact.objects.filter(owner=owner).exists():
        raise OrderError("Complete your registrant information first")
    if not key or len(key) > 64:
        raise OrderError("Invalid checkout request")
    # Return the original order before any duplicate-domain guard. The per-user
    # unique constraint still protects concurrent retries of the same request.
    existing = DomainOrder.objects.filter(owner=owner, idempotency_key=key).first()
    if existing:
        if existing.domain != domain or existing.operation != operation:
            raise OrderError("Checkout key was already used for another request")
        return existing
    if operation == DomainOrder.REGISTER:
        if ManagedDomain.objects.filter(name=domain).exists():
            raise OrderError("This domain already has an owner in this store")
        # Do not accept a second payment while an earlier registration is unresolved.
        if DomainOrder.objects.filter(domain=domain, operation=DomainOrder.REGISTER).exclude(
            status__in=[DomainOrder.REFUNDED]
        ).exists():
            raise OrderError("An order already exists for this domain; contact support")
    else:
        if managed_domain is None or managed_domain.owner_id != owner.pk:
            raise OrderError("Domain not owned by this customer")
        if DomainOrder.objects.filter(managed_domain=managed_domain, operation=DomainOrder.RENEW).exclude(
            status__in=[DomainOrder.REFUNDED, DomainOrder.ACTIVE]
        ).exists():
            raise OrderError("A renewal is already pending")
    with transaction.atomic():
        existing = DomainOrder.objects.filter(owner=owner, idempotency_key=key).first()
        if existing:
            if existing.domain != domain or existing.operation != operation:
                raise OrderError("Checkout key was already used for another request")
            return existing
        order = DomainOrder.objects.create(owner=owner, domain=domain,
            operation=operation, amount_paise=price, idempotency_key=key,
            managed_domain=managed_domain)
    try:
        gateway_order = Razorpay().create_order(order)
        if (gateway_order.get("amount") != price or gateway_order.get("currency") != "INR"
                or not str(gateway_order.get("id", "")).startswith("order_")):
            raise PaymentError("Unexpected payment gateway order response")
        order.razorpay_order_id = gateway_order["id"]
        order.save(update_fields=["razorpay_order_id", "updated_at"])
        AuditEntry.objects.create(actor=owner, order=order, action="checkout_created")
        return order
    except PaymentError as exc:
        order.status = DomainOrder.REVIEW
        order.provider_message = "Payment order initiation uncertain; reconcile gateway receipt"
        order.save(update_fields=["status", "provider_message", "updated_at"])
        raise OrderError(str(exc)) from exc


def receive_razorpay_webhook(body, signature, event_id):
    """The sole automatic payment->paid transition. Verify original request bytes."""
    if not verify_webhook(body, signature, settings.RAZORPAY_WEBHOOK_SECRET):
        raise OrderError("Invalid webhook signature")
    if not event_id or len(event_id) > 130:
        raise OrderError("Missing event identifier")
    try:
        message = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise OrderError("Invalid webhook payload") from exc
    event_type = message.get("event", "")
    digest = hashlib.sha256(body).hexdigest()
    with transaction.atomic():
        event, created = PaymentEvent.objects.get_or_create(event_id=event_id,
            defaults={"event_type": event_type[:60], "payload_sha256": digest})
        if not created:
            if event.payload_sha256 != digest:
                raise OrderError("Event ID collision")
            return "duplicate"
        event.outcome = "ignored"
        if event_type == "payment.captured":
            payment = message.get("payload", {}).get("payment", {}).get("entity", {})
            external_order = payment.get("order_id", "")
            order = (DomainOrder.objects.select_for_update().filter(
                razorpay_order_id=external_order).first()
                if isinstance(external_order, str) and external_order.startswith("order_")
                else None)
            if (order and order.status == DomainOrder.AWAITING and
                payment.get("status") == "captured" and
                payment.get("amount") == order.amount_paise and
                payment.get("currency") == "INR" and
                str(payment.get("id", "")).startswith("pay_")):
                order.status = DomainOrder.PAID
                order.razorpay_payment_id = payment["id"]
                order.save(update_fields=["status", "razorpay_payment_id", "updated_at"])
                AuditEntry.objects.create(actor=order.owner, order=order, action="payment_captured")
                event.outcome = "paid"
            elif order:
                event.outcome = "unmatched_payment_review"
        event.processed_at = timezone.now()
        event.save(update_fields=["outcome", "processed_at"])
    return event.outcome


def fulfill_one(order_id, provider=None):
    """At-most-one automatic registrar attempt; network uncertainty requires review.

    This intentionally prefers stopping for human reconciliation over blindly
    retrying a potentially charged registration or renewal.
    """
    if not fulfillment_ready():
        raise OrderError("Fulfillment is disabled")
    with transaction.atomic():
        order = DomainOrder.objects.select_for_update().get(pk=order_id)
        if order.status != DomainOrder.PAID:
            return False
        order.status = DomainOrder.PROCESSING
        order.save(update_fields=["status", "updated_at"])
    provider = provider or Openprovider()
    try:
        if order.operation == DomainOrder.REGISTER:
            if ManagedDomain.objects.filter(name=order.domain).exists():
                raise OrderError("Local ownership collision; reconcile")
            contact = RegistrantContact.objects.get(owner=order.owner)
            if not contact.openprovider_handle:
                handle = provider.create_contact(contact.provider_payload())
                contact.openprovider_handle = handle
                contact.save(update_fields=["openprovider_handle", "updated_at"])
            result = provider.register(order.domain, contact.openprovider_handle)
            provider_id = int(result["id"])
            remote_status = str(result.get("status", "")).upper()
            with transaction.atomic():
                managed = ManagedDomain.objects.create(owner=order.owner, name=order.domain,
                    provider_id=provider_id, status="active" if remote_status == "ACT" else "pending",
                    expires_at=parse_expiry(result.get("expiration_date")))
                order.managed_domain = managed
                order.provider_result_id = provider_id
                order.status = DomainOrder.ACTIVE if remote_status == "ACT" else DomainOrder.REVIEW
                order.save(update_fields=["managed_domain", "provider_result_id", "status", "updated_at"])
                AuditEntry.objects.create(actor=order.owner, order=order, domain=managed,
                                          action="registrar_registered" if remote_status == "ACT" else "registry_pending")
        else:
            managed = order.managed_domain
            if managed is None or managed.owner_id != order.owner_id:
                raise OrderError("Renewal ownership mismatch")
            provider.renew(managed.provider_id)
            # Re-fetch actual renewal date instead of adding 365 days locally.
            details = provider.get_domain(managed.provider_id)
            managed.expires_at = parse_expiry(details.get("renewal_date") or details.get("expiration_date"))
            managed.save(update_fields=["expires_at", "updated_at"])
            order.status = DomainOrder.ACTIVE
            order.provider_result_id = managed.provider_id
            order.save(update_fields=["status", "provider_result_id", "updated_at"])
            AuditEntry.objects.create(actor=order.owner, order=order, domain=managed,
                                      action="registrar_renewed")
        return True
    except Exception:
        # Details might include PII/credentials from remote errors; do not log them.
        order.status = DomainOrder.REVIEW
        order.provider_message = "Registrar action uncertain. Check registrar before retry/refund."
        order.save(update_fields=["status", "provider_message", "updated_at"])
        AuditEntry.objects.create(actor=order.owner, order=order, action="manual_reconciliation_needed")
        return False
