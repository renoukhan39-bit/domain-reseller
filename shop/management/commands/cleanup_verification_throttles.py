from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import EmailVerificationThrottle


class Command(BaseCommand):
    help = "Remove verification throttle counters older than one day (longest window is one hour)"

    def handle(self, *args, **options):
        deleted, _ = EmailVerificationThrottle.objects.filter(
            window_start__lt=timezone.now() - timedelta(days=1)).delete()
        self.stdout.write(f"Removed {deleted} expired verification throttle counters")
