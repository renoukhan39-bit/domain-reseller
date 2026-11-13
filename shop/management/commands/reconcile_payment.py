from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from shop.models import AuditEntry, DomainOrder
from shop.payment_events import gateway_identifier, replay_payment_events
from shop.payments import PaymentError, Razorpay


class Command(BaseCommand):
    help = "Verify a Razorpay order by GET and replay retained signed captured events; never charges or fulfills"

    def add_arguments(self, parser):
        parser.add_argument("order_id")
        parser.add_argument("--gateway-order-id")
        parser.add_argument("--allow-live", action="store_true", help="Explicit operator approval for read-only live reconciliation")

    def handle(self, *args, **options):
        if not settings.RAZORPAY_KEY_ID.startswith("rzp_test_") and not (
                options["allow_live"] and settings.RAZORPAY_KEY_ID.startswith("rzp_live_")):
            raise CommandError("Test keys required; live read-only reconciliation requires --allow-live")
        try:
            order = DomainOrder.objects.get(pk=options["order_id"])
        except (DomainOrder.DoesNotExist, ValidationError, ValueError):
            raise CommandError("Unknown order") from None
        external_id = options["gateway_order_id"] or order.razorpay_order_id
        if not gateway_identifier(external_id, "order"):
            raise CommandError("Provide the gateway order identifier found by receipt; never retry creation")
        try:
            remote = Razorpay().fetch_order(external_id)
        except PaymentError:
            raise CommandError("Gateway lookup failed; no order state changed") from None
        if (not isinstance(remote, dict) or remote.get("id") != external_id
                or remote.get("receipt") != str(order.pk)
                or type(remote.get("amount")) is not int or remote["amount"] != order.amount_paise
                or remote.get("currency") != order.currency
                or remote.get("status") not in ("created", "attempted", "paid")):
            raise CommandError("Gateway order identity, receipt, amount or currency mismatch")
        try:
            with transaction.atomic():
                order = DomainOrder.objects.select_for_update().get(pk=order.pk)
                if order.razorpay_order_id and order.razorpay_order_id != external_id:
                    raise CommandError("Local gateway order identifier conflicts")
                if order.refund_attempted_at or order.refund_id or order.status in (
                        DomainOrder.REFUND_PENDING, DomainOrder.REFUND_REVIEW, DomainOrder.REFUNDED):
                    raise CommandError("Refund lifecycle requires separate reconciliation")
                if order.status == DomainOrder.REVIEW:
                    if order.razorpay_payment_id or order.managed_domain_id or order.provider_result_id:
                        raise CommandError("Registrar/payment review cannot be reset by gateway order reconciliation")
                    order.status = DomainOrder.AWAITING
                    order.provider_message = ""
                order.razorpay_order_id = external_id
                order.save(update_fields=["razorpay_order_id", "status", "provider_message", "updated_at"])
                AuditEntry.objects.create(order=order, action="gateway_order_reconciled")
        except IntegrityError:
            raise CommandError("Gateway identifier is already associated with another order") from None
        counts = replay_payment_events(external_id)
        self.stdout.write("Gateway order verified; retained signed evidence outcomes: " + str(counts))
