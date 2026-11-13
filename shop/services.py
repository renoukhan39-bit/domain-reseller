"""Order/payment business rules and a conservative fulfillment state machine."""
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import AuditEntry, DomainOrder, ManagedDomain, RegistrantContact
from .payments import Razorpay, PaymentError
from .providers import Openprovider, parse_expiry, provider_environment


from .exceptions import OrderError
from .payment_events import gateway_identifier, receive_razorpay_webhook, replay_payment_events


def sales_ready():
    environment = provider_environment(settings.OPENPROVIDER_BASE_URL)
    test_key = settings.RAZORPAY_KEY_ID.startswith("rzp_test_")
    live_key = settings.RAZORPAY_KEY_ID.startswith("rzp_live_")
    # This prevents charging real money for sandbox domains, and using
    # a test payment to buy a real live registrar domain.
    matching_environments = (environment == "sandbox" and test_key) or (environment == "live" and live_key)
    return bool(settings.SALES_ENABLED and matching_environments and
            settings.RAZORPAY_KEY_SECRET and settings.RAZORPAY_WEBHOOK_SECRET and
            settings.OPENPROVIDER_USERNAME and settings.OPENPROVIDER_PASSWORD)


def fulfillment_ready():
    return settings.FULFILLMENT_ENABLED and sales_ready()


def create_checkout_order(*, owner, domain, operation, price, key, managed_domain=None):
    """Reserve one payable operation before HTTP; uncertain POSTs are never retried."""
    from .forms import normalize_domain
    from django.core.exceptions import ValidationError
    try:
        domain = normalize_domain(domain)
    except (ValidationError, TypeError):
        raise OrderError("Invalid domain") from None
    if operation not in (DomainOrder.REGISTER, DomainOrder.RENEW):
        raise OrderError("Unsupported operation")
    if type(price) is not int or not 0 < price <= 2147483647:
        raise OrderError("Invalid server price")
    if not isinstance(key, str) or not key.strip() or len(key) > 64:
        raise OrderError("Invalid checkout request")
    if not sales_ready():
        raise OrderError("Sales are not enabled")
    if not owner.is_active or not RegistrantContact.objects.filter(owner=owner).exists():
        raise OrderError("Complete your registrant information first")
    if operation == DomainOrder.REGISTER and managed_domain is not None:
        raise OrderError("Invalid registration request")
    if operation == DomainOrder.RENEW:
        if (managed_domain is None or managed_domain.owner_id != owner.pk
                or managed_domain.name != domain or managed_domain.status != "active"):
            raise OrderError("Domain not owned by this customer or not active")
    def original():
        existing = DomainOrder.objects.filter(owner=owner, idempotency_key=key).first()
        if existing and (existing.domain != domain or existing.operation != operation
                         or (operation == DomainOrder.RENEW and existing.managed_domain_id != getattr(managed_domain, "pk", None))):
            raise OrderError("Checkout key was already used for another request")
        return existing
    existing = original()
    if existing:
        return existing
    try:
        with transaction.atomic():
            if operation == DomainOrder.RENEW:
                current = ManagedDomain.objects.select_for_update().filter(pk=managed_domain.pk).first()
                if current is None or current.owner_id != owner.pk or current.name != domain or current.status != "active":
                    raise OrderError("Domain not owned by this customer or not active")
            if operation == DomainOrder.REGISTER and ManagedDomain.objects.filter(name=domain).exists():
                raise OrderError("This domain already has an owner in this store")
            order = DomainOrder.objects.create(owner=owner, domain=domain, operation=operation,
                amount_paise=price, idempotency_key=key, managed_domain=managed_domain)
    except IntegrityError:
        existing = original()
        if existing:
            return existing
        raise OrderError("An unresolved order already exists; contact support") from None
    try:
        gateway_order = Razorpay().create_order(order)
        if (not isinstance(gateway_order, dict) or type(gateway_order.get("amount")) is not int
                or gateway_order["amount"] != price or gateway_order.get("currency") != "INR"
                or not gateway_identifier(gateway_order.get("id"), "order")):
            raise PaymentError("Unexpected payment gateway order response")
        with transaction.atomic():
            order = DomainOrder.objects.select_for_update().get(pk=order.pk)
            if order.razorpay_order_id and order.razorpay_order_id != gateway_order["id"]:
                raise PaymentError("Conflicting gateway order identifier")
            order.razorpay_order_id = gateway_order["id"]
            order.save(update_fields=["razorpay_order_id", "updated_at"])
            AuditEntry.objects.create(actor=owner, order=order, action="checkout_created")
        replay_payment_events(order.razorpay_order_id)
        order.refresh_from_db()
        return order
    except (PaymentError, IntegrityError):
        DomainOrder.objects.filter(pk=order.pk, status=DomainOrder.AWAITING).update(
            status=DomainOrder.REVIEW, provider_message="Payment initiation uncertain; reconcile gateway receipt",
            updated_at=timezone.now())
        AuditEntry.objects.create(actor=owner, order=order, action="payment_initiation_review")
        raise OrderError("Payment initiation uncertain; contact support before retrying") from None


def _registrar_identity(details, provider_id, domain, owner_handle):
    if not isinstance(details, dict):
        raise OrderError("Registrar identity is missing")
    identity = details.get("domain")
    if isinstance(identity, dict):
        identity = f"{identity.get('name', '')}.{identity.get('extension', '')}"
    if (type(details.get("id")) is not int or details["id"] != provider_id
            or not isinstance(identity, str) or identity.lower().rstrip(".") != domain
            or details.get("owner_handle") != owner_handle):
        raise OrderError("Registrar identity does not match this order")
    return str(details.get("status", "")).upper(), parse_expiry(details.get("renewal_date") or details.get("expiration_date"))


def fulfill_one(order_id, provider=None):
    """Commit a single claim before registrar writes; uncertain results never retry."""
    if not fulfillment_ready():
        raise OrderError("Fulfillment is disabled")
    with transaction.atomic(durable=True):
        order = DomainOrder.objects.select_for_update().get(pk=order_id)
        if order.status != DomainOrder.PAID or order.refund_attempted_at or order.refund_id:
            return False
        order.status = DomainOrder.PROCESSING
        order.save(update_fields=["status", "updated_at"])
        AuditEntry.objects.create(actor=order.owner, order=order, action="fulfillment_claimed")
    try:
        provider = provider or Openprovider()
        if order.operation == DomainOrder.REGISTER:
            if ManagedDomain.objects.filter(name=order.domain).exists():
                raise OrderError("Local ownership collision")
            # Serialize customer-handle creation across different paid orders.
            with transaction.atomic():
                contact = RegistrantContact.objects.select_for_update().get(owner=order.owner)
                if not contact.openprovider_handle:
                    handle = provider.create_contact(contact.provider_payload())
                    if not isinstance(handle, str) or not handle.strip() or len(handle) > 60:
                        raise OrderError("Invalid registrar contact handle")
                    contact.openprovider_handle = handle
                    contact.save(update_fields=["openprovider_handle", "updated_at"])
            result = provider.register(order.domain, contact.openprovider_handle)
            provider_id = result.get("id") if isinstance(result, dict) else None
            if type(provider_id) is not int or not 0 < provider_id <= 9223372036854775807:
                raise OrderError("Registrar did not return a valid domain identifier")
            # Retain known identity even if the following read fails or worker was escalated.
            with transaction.atomic():
                current = DomainOrder.objects.select_for_update().get(pk=order.pk)
                if current.provider_result_id and current.provider_result_id != provider_id:
                    raise OrderError("Conflicting registrar identifier")
                current.provider_result_id = provider_id
                current.save(update_fields=["provider_result_id", "updated_at"])
                if current.status != DomainOrder.PROCESSING:
                    AuditEntry.objects.create(order=current, action="late_registrar_result_review")
                    return False
            details = provider.get_domain(provider_id)
            status, expiry = _registrar_identity(details, provider_id, order.domain, contact.openprovider_handle)
            active = status == "ACT" and expiry is not None
            with transaction.atomic():
                current = DomainOrder.objects.select_for_update().get(pk=order.pk)
                if current.status != DomainOrder.PROCESSING:
                    AuditEntry.objects.create(order=current, action="late_registrar_result_review")
                    return False
                managed = ManagedDomain.objects.create(owner=order.owner, name=order.domain,
                    provider_id=provider_id, status="active" if active else "pending", expires_at=expiry)
                current.managed_domain = managed
                current.status = DomainOrder.ACTIVE if active else DomainOrder.REVIEW
                current.save(update_fields=["managed_domain", "status", "updated_at"])
                AuditEntry.objects.create(actor=order.owner, order=current, domain=managed,
                    action="registrar_registered" if active else "registry_pending")
            return active
        if order.operation != DomainOrder.RENEW:
            raise OrderError("Unsupported registrar operation")
        managed = ManagedDomain.objects.get(pk=order.managed_domain_id)
        contact = RegistrantContact.objects.get(owner=order.owner)
        baseline = managed.expires_at
        if (managed.owner_id != order.owner_id or managed.name != order.domain or managed.status != "active"
                or baseline is None or not contact.openprovider_handle):
            raise OrderError("Renewal ownership, contact or expiry is not verified")
        before = provider.get_domain(managed.provider_id)
        before_status, remote_baseline = _registrar_identity(before, managed.provider_id, order.domain, contact.openprovider_handle)
        if before_status != "ACT" or remote_baseline is None or remote_baseline < baseline:
            raise OrderError("Registrar renewal baseline is not verified")
        with transaction.atomic():
            current = DomainOrder.objects.select_for_update().get(pk=order.pk)
            if current.status != DomainOrder.PROCESSING:
                return False
            AuditEntry.objects.create(order=current, action="renewal_baseline_verified", detail=remote_baseline.isoformat())
        result = provider.renew(managed.provider_id)
        if not isinstance(result, dict) or (result.get("status") and str(result["status"]).upper() != "ACT"):
            raise OrderError("Renewal response requires review")
        details = provider.get_domain(managed.provider_id)
        status, expiry = _registrar_identity(details, managed.provider_id, order.domain, contact.openprovider_handle)
        if status != "ACT" or expiry is None or expiry <= remote_baseline:
            raise OrderError("Renewal completion is not confirmed")
        with transaction.atomic():
            current = DomainOrder.objects.select_for_update().get(pk=order.pk)
            domain = ManagedDomain.objects.select_for_update().get(pk=managed.pk)
            if current.status != DomainOrder.PROCESSING:
                AuditEntry.objects.create(order=current, action="late_registrar_result_review")
                return False
            if (domain.owner_id != order.owner_id or domain.name != order.domain
                    or domain.provider_id != managed.provider_id or domain.expires_at != baseline):
                raise OrderError("Domain changed while renewal was in progress")
            domain.expires_at = expiry
            domain.save(update_fields=["expires_at", "updated_at"])
            current.status, current.provider_result_id = DomainOrder.ACTIVE, domain.provider_id
            current.save(update_fields=["status", "provider_result_id", "updated_at"])
            AuditEntry.objects.create(actor=order.owner, order=current, domain=domain, action="registrar_renewed")
        return True
    except Exception:
        # Neither provider exception text nor registrant payloads enter logs/audit.
        with transaction.atomic():
            current = DomainOrder.objects.select_for_update().get(pk=order.pk)
            if current.status == DomainOrder.PROCESSING:
                current.status = DomainOrder.REVIEW
                current.provider_message = "Registrar action uncertain. Check registrar before retry/refund."
                current.save(update_fields=["status", "provider_message", "updated_at"])
                AuditEntry.objects.create(actor=order.owner, order=current, action="manual_reconciliation_needed")
        return False
