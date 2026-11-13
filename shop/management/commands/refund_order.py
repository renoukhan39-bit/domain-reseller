from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from shop.models import AuditEntry, DomainOrder
from shop.payments import Razorpay, PaymentError

class Command(BaseCommand):
    help = "MANUAL: refund after verifying registrar has not completed the paid operation"

    def add_arguments(self, parser):
        parser.add_argument("order_id")
        parser.add_argument("--confirmed-not-registered", action="store_true")

    def handle(self, *args, **options):
        if not options["confirmed_not_registered"]:
            raise CommandError("Reconcile registrar transaction first; pass --confirmed-not-registered")
        with transaction.atomic():
            order = DomainOrder.objects.select_for_update().get(pk=options["order_id"])
            if (order.status != DomainOrder.REVIEW or not order.razorpay_payment_id or
                    order.refund_id or (order.operation == DomainOrder.REGISTER and order.managed_domain_id)):
                raise CommandError("Order is not eligible for manual refund")
            # Explicit operator-only action; external request is not safely retryable on timeout.
            try:
                refund = Razorpay().refund_payment(order.razorpay_payment_id, order.amount_paise)
            except PaymentError as exc:
                raise CommandError("Refund status uncertain; check Razorpay before retry") from exc
            if not refund.get("id"):
                raise CommandError("Missing refund identifier; check Razorpay")
            order.refund_id = refund["id"]
            order.status = DomainOrder.REFUNDED if refund.get("status") == "processed" else DomainOrder.REVIEW
            order.save(update_fields=["refund_id", "status", "updated_at"])
            AuditEntry.objects.create(actor=None, order=order, action="refund_requested")
        self.stdout.write(f"Refund requested: {refund['id']}; status={refund.get('status')}")
