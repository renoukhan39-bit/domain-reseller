from django.core.management.base import BaseCommand
from shop.models import DomainOrder
from shop.services import fulfill_one, fulfillment_ready

class Command(BaseCommand):
    help = "Process captured, paid domain orders using the real registrar integration"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        if not fulfillment_ready():
            self.stdout.write("Fulfillment disabled; no registrar calls made")
            return
        count = 0
        for pk in list(DomainOrder.objects.filter(status=DomainOrder.PAID)
                       .order_by("created_at").values_list("pk", flat=True)[:max(0, min(options["limit"], 100))]):
            if fulfill_one(pk):
                count += 1
        self.stdout.write(f"Fulfilled {count} orders")
