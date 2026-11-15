from django.core.management.base import BaseCommand, CommandError
from shop.refunds import RefundError, request_refund

class Command(BaseCommand):
    help = "MANUAL: refund after verifying registrar has not completed the paid operation"

    def add_arguments(self, parser):
        parser.add_argument("order_id")
        parser.add_argument("--confirmed-not-registered", action="store_true")
        parser.add_argument("--allow-live", action="store_true", help="Only after separate owner approval for a live refund")

    def handle(self, *args, **options):
        try:
            order = request_refund(options["order_id"],
                                   confirmed_not_registered=options["confirmed_not_registered"],
                                   allow_live=options["allow_live"])
        except RefundError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Refund request recorded; status={order.status}")
