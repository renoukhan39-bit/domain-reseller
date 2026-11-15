from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from shop.models import AuditEntry, DomainOrder


class Command(BaseCommand):
    help = "Escalate stale PROCESSING orders to manual review; never retries registrar operations"

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=30)
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if options["minutes"] < 5 or not 1 <= options["limit"] <= 1000:
            raise CommandError("Use at least five minutes and a batch limit from 1 to 1000")
        cutoff = timezone.now() - timedelta(minutes=options["minutes"])
        with transaction.atomic():
            orders = list(DomainOrder.objects.select_for_update(skip_locked=True).filter(
                status=DomainOrder.PROCESSING, updated_at__lt=cutoff).order_by("updated_at")[:options["limit"]])
            for order in orders:
                order.status = DomainOrder.REVIEW
                order.provider_message = "Worker completion uncertain; reconcile registrar before retry/refund."
                order.save(update_fields=["status", "provider_message", "updated_at"])
                AuditEntry.objects.create(order=order, action="stale_fulfillment_review")
        self.stdout.write(f"Escalated {len(orders)} stale orders; no registrar requests sent")
