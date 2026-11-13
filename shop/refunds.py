"""Operator-only refunds: persist intent before POST and reconcile uncertainty with GET."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from .models import AuditEntry, DomainOrder, ManagedDomain
from .payments import PaymentError, Razorpay, valid_gateway_id


class RefundError(Exception):
    pass


def _mark_uncertain(order_id):
    with transaction.atomic():
        current = DomainOrder.objects.select_for_update().get(pk=order_id)
        if current.status != DomainOrder.REFUNDED:
            current.status = DomainOrder.REFUND_REVIEW
            current.provider_message = "Refund result uncertain. Check Razorpay; never resend automatically."
            current.save(update_fields=["status", "provider_message", "updated_at"])
            AuditEntry.objects.create(order=current, action="refund_reconciliation_needed")


def _eligible(order):
    if (order.status != DomainOrder.REVIEW or order.refund_id or order.refund_attempted_at
            or not valid_gateway_id(order.razorpay_payment_id, "pay_")
            or not valid_gateway_id(order.razorpay_order_id, "order_")
            or order.currency != "INR" or type(order.amount_paise) is not int or order.amount_paise <= 0):
        raise RefundError("Order is not eligible for a new refund request")
    if order.operation == DomainOrder.REGISTER:
        if order.managed_domain_id or order.provider_result_id:
            raise RefundError("Reconcile the registered domain before considering a refund")
    elif order.operation == DomainOrder.RENEW:
        if not ManagedDomain.objects.filter(pk=order.managed_domain_id, owner_id=order.owner_id,
                                             name=order.domain).exists():
            raise RefundError("Renewal ownership does not match the order")
    else:
        raise RefundError("Unknown order operation")


def _payment_matches(order, payment):
    return (isinstance(payment, dict)
            and payment.get("id") == order.razorpay_payment_id
            and payment.get("order_id") == order.razorpay_order_id
            and payment.get("status") == "captured"
            and type(payment.get("amount")) is int and payment["amount"] == order.amount_paise
            and payment.get("currency") == order.currency
            and type(payment.get("amount_refunded")) is int and payment["amount_refunded"] == 0
            and payment.get("refund_status") in (None, ""))


def _refund_state(order, refund, expected_id=None):
    if (not isinstance(refund, dict) or not valid_gateway_id(refund.get("id"), "rfnd_")
            or (expected_id is not None and refund["id"] != expected_id)
            or refund.get("payment_id") != order.razorpay_payment_id
            or type(refund.get("amount")) is not int or refund["amount"] != order.amount_paise
            or refund.get("currency") != order.currency):
        raise RefundError("Refund evidence does not match the order; reconcile manually")
    status = refund.get("status")
    if status == "processed":
        return DomainOrder.REFUNDED
    if status == "pending":
        return DomainOrder.REFUND_PENDING
    if status == "failed":
        return DomainOrder.REFUND_REVIEW
    raise RefundError("Unrecognized refund status; reconcile manually")


def request_refund(order_id, *, confirmed_not_registered=False, gateway=None, allow_live=False):
    """Never repeat this POST, including after timeout, process crash or malformed response.

    Refunds remain available while sales are disabled. The explicit registrar
    confirmation and live-mode acknowledgement are operator gates, not an API.
    """
    if not confirmed_not_registered:
        raise RefundError("Reconcile registrar transaction first; pass --confirmed-not-registered")
    if connection.in_atomic_block:
        raise RefundError("Refund requests must run outside an enclosing transaction")
    key_id = settings.RAZORPAY_KEY_ID
    if not (key_id.startswith("rzp_test_") or (allow_live and key_id.startswith("rzp_live_"))):
        raise RefundError("Use test credentials, or explicitly acknowledge approved live refunds with --allow-live")
    try:
        order = DomainOrder.objects.get(pk=order_id)
        _eligible(order)
        gateway = gateway or Razorpay()
        payment = gateway.fetch_payment(order.razorpay_payment_id)
    except (DomainOrder.DoesNotExist, ValidationError, ValueError, PaymentError) as exc:
        raise RefundError("Cannot verify the payment; no refund request sent") from exc
    if not _payment_matches(order, payment):
        raise RefundError("Payment evidence is not an eligible full captured payment")
    snapshot = (order.razorpay_order_id, order.razorpay_payment_id, order.amount_paise, order.currency)
    with transaction.atomic(durable=True):
        order = DomainOrder.objects.select_for_update().get(pk=order.pk)
        _eligible(order)
        if snapshot != (order.razorpay_order_id, order.razorpay_payment_id, order.amount_paise, order.currency):
            raise RefundError("Order changed during payment verification; no refund request sent")
        order.status = DomainOrder.REFUND_PENDING
        order.refund_attempted_at = timezone.now()
        order.provider_message = "Refund requested; reconcile gateway before any further action."
        order.save(update_fields=["status", "refund_attempted_at", "provider_message", "updated_at"])
        AuditEntry.objects.create(order=order, action="refund_attempt_claimed")
    try:
        refund = gateway.refund_payment(order.razorpay_payment_id, order.amount_paise)
        status = _refund_state(order, refund)
    except (PaymentError, RefundError):
        _mark_uncertain(order.pk)
        raise RefundError("Refund status uncertain; use read-only reconciliation before further action")
    try:
        with transaction.atomic():
            current = DomainOrder.objects.select_for_update().get(pk=order.pk)
            if current.refund_id and current.refund_id != refund["id"]:
                raise RefundError("Conflicting refund evidence; reconcile manually")
            # A concurrent GET reconciliation may already have confirmed completion.
            if current.status != DomainOrder.REFUNDED:
                current.refund_id = refund["id"]
                current.status = status
                current.save(update_fields=["refund_id", "status", "updated_at"])
                AuditEntry.objects.create(order=current, action="refund_requested")
    except IntegrityError as exc:
        _mark_uncertain(order.pk)
        raise RefundError("Refund identifier conflicts with another order; reconcile manually") from exc
    return current


def reconcile_refund(order_id, *, gateway=None, refund_id=None):
    """Read gateway evidence only; never repeat refund/capture/registrar requests."""
    try:
        order = DomainOrder.objects.get(pk=order_id)
    except (DomainOrder.DoesNotExist, ValidationError, ValueError) as exc:
        raise RefundError("Unknown order") from exc
    if order.status not in (DomainOrder.REFUND_PENDING, DomainOrder.REFUND_REVIEW, DomainOrder.REFUNDED):
        raise RefundError("Order has no refund attempt to reconcile")
    if not order.refund_attempted_at:
        raise RefundError("Refund intent is not recorded; reconcile manually")
    selected_id = refund_id or order.refund_id
    if not valid_gateway_id(selected_id, "rfnd_") or (order.refund_id and selected_id != order.refund_id):
        raise RefundError("Supply the verified gateway refund identifier without changing an existing binding")
    try:
        gateway = gateway or Razorpay()
        refund = gateway.fetch_refund(selected_id)
        status = _refund_state(order, refund, expected_id=selected_id)
    except PaymentError as exc:
        AuditEntry.objects.create(order=order, action="refund_lookup_failed")
        raise RefundError("Gateway refund lookup failed; no external action was requested") from exc
    except RefundError:
        AuditEntry.objects.create(order=order, action="refund_evidence_rejected")
        raise
    try:
        with transaction.atomic():
            current = DomainOrder.objects.select_for_update().get(pk=order.pk)
            if (current.razorpay_payment_id != order.razorpay_payment_id
                    or current.amount_paise != order.amount_paise or current.currency != order.currency
                    or current.status not in (DomainOrder.REFUND_PENDING, DomainOrder.REFUND_REVIEW, DomainOrder.REFUNDED)
                    or (current.refund_id and current.refund_id != selected_id)):
                raise RefundError("Order changed during refund reconciliation")
            if current.status == DomainOrder.REFUNDED and status != DomainOrder.REFUNDED:
                raise RefundError("Conflicting completion evidence; reconcile manually")
            if current.refund_id != selected_id or current.status != status:
                current.refund_id, current.status = selected_id, status
                current.save(update_fields=["refund_id", "status", "updated_at"])
                AuditEntry.objects.create(order=current, action="refund_reconciled")
    except IntegrityError as exc:
        _mark_uncertain(order.pk)
        raise RefundError("Refund identifier conflicts with another order; reconcile manually") from exc
    return current
