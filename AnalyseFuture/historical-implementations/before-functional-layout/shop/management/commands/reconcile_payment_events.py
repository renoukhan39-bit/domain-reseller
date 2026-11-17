from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from shop.models import DomainOrder
from shop.payment_events import replay_payment_events


class Command(BaseCommand):
    help = "Reprocess retained signed payment evidence; never contacts a provider"

    def add_arguments(self, parser):
        parser.add_argument("--order-id")

    def handle(self, *args, **options):
        gateway_id = None
        if options["order_id"]:
            try:
                gateway_id = DomainOrder.objects.get(pk=options["order_id"]).razorpay_order_id
            except (DomainOrder.DoesNotExist, ValidationError, ValueError):
                raise CommandError("Unknown order") from None
            if not gateway_id:
                raise CommandError("Reconcile the gateway order identifier first")
        counts = replay_payment_events(gateway_id)
        self.stdout.write("Signed payment evidence processed: " + str(counts))
