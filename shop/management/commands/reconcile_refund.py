from django.core.management.base import BaseCommand, CommandError

from shop.refunds import RefundError, reconcile_refund


class Command(BaseCommand):
    help = "Read-only Razorpay refund reconciliation; never sends a new refund"

    def add_arguments(self, parser):
        parser.add_argument("order_id")
        parser.add_argument("--refund-id", help="Verified ID from Razorpay after an uncertain refund response")

    def handle(self, *args, **options):
        try:
            order = reconcile_refund(options["order_id"], refund_id=options["refund_id"])
        except RefundError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Refund evidence reconciled; status={order.status}")
