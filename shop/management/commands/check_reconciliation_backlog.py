"""Read-only, non-PII reconciliation backlog signal for external monitoring.

Operators should run mark_stale_orders separately before this check. This
command never changes financial/registrar state or calls external providers.
"""
import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from shop.models import DomainOrder, PaymentEvent


class Command(BaseCommand):
    help = (
        "Print reconciliation backlog counts as JSON and fail if operator attention "
        "is required. No order IDs, domains, payments or personal data are printed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes", type=int, default=30,
            help="Minimum age for stalled workflows and unmatched early events (5–10080).",
        )
        parser.add_argument(
            "--warn-only", action="store_true",
            help="Keep exit status zero when problems exist (for dashboards or exploratory runs).",
        )

    def handle(self, *args, **options):
        minutes = options["minutes"]
        if not 5 <= minutes <= 10080:
            raise CommandError("Use an age threshold between 5 and 10080 minutes")

        now = timezone.now()
        cutoff = now - timedelta(minutes=minutes)
        # Each query is read-only. Counts are operational estimates, not a
        # transactionally consistent financial ledger or a provider balance.
        counts = {
            "manual_review_orders": DomainOrder.objects.filter(
                status=DomainOrder.REVIEW,
            ).count(),
            "stale_paid_orders": DomainOrder.objects.filter(
                status=DomainOrder.PAID, updated_at__lte=cutoff,
            ).count(),
            "stale_processing_orders": DomainOrder.objects.filter(
                status=DomainOrder.PROCESSING, updated_at__lte=cutoff,
            ).count(),
            "refund_review_orders": DomainOrder.objects.filter(
                status=DomainOrder.REFUND_REVIEW,
            ).count(),
            "stale_refund_pending_orders": DomainOrder.objects.filter(
                status=DomainOrder.REFUND_PENDING, updated_at__lte=cutoff,
            ).count(),
            "stale_waiting_payment_events": PaymentEvent.objects.filter(
                event_type="payment.captured", outcome="waiting_order",
                received_at__lte=cutoff,
            ).count(),
            "payment_event_conflicts": PaymentEvent.objects.filter(
                outcome__in=("unmatched_payment_review", "payment_conflict_review"),
            ).count(),
            "legacy_ignored_captures": PaymentEvent.objects.filter(
                event_type="payment.captured", outcome="ignored",
            ).count(),
            "stale_unprocessed_payment_events": PaymentEvent.objects.filter(
                Q(processed_at__isnull=True) | Q(outcome=""),
                received_at__lte=cutoff,
            ).exclude(outcome="waiting_order").count(),
        }

        needs_attention = [name for name, count in counts.items() if count]
        report = {
            "schema_version": 1,
            "checked_at": now.isoformat(),
            "minimum_age_minutes": minutes,
            "status": "alert" if needs_attention else "ok",
            "counts": counts,
            "alert_categories": needs_attention,
        }
        self.stdout.write(json.dumps(report, sort_keys=True))

        if needs_attention and not options["warn_only"]:
            # Only category names, never tenant data, appear in stderr or logs.
            raise CommandError(
                "Reconciliation backlog requires operator review; see JSON counts."
            )
