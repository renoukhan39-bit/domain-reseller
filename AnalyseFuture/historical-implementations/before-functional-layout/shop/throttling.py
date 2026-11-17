"""Shared bounded request budgets backed by PostgreSQL row locks."""
from datetime import timedelta
from math import ceil

from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import EmailVerificationThrottle


class ThrottleUnavailable(Exception):
    pass


def consume_budget(scope, identity, limit, seconds):
    """Return (allowed, retry_after); keys and existing email windows stay stable.

    The historical model name is retained to avoid replacing a working table.
    Scope names separate email, authentication and customer-operation budgets.
    """
    if type(limit) is not int or limit < 1 or type(seconds) is not int or not 1 <= seconds <= 3600:
        raise ValueError("Throttle budgets need positive limits and windows of at most one hour")
    key = salted_hmac("email-verification-throttle", f"{scope}:{identity}", algorithm="sha256").hexdigest()
    now = timezone.now()
    try:
        with transaction.atomic():
            counter, _ = EmailVerificationThrottle.objects.select_for_update().get_or_create(
                key=key, defaults={"window_start": now})
            if counter.window_start <= now - timedelta(seconds=seconds):
                counter.window_start, counter.count = now, 0
            if counter.count >= limit:
                remaining = (counter.window_start + timedelta(seconds=seconds) - now).total_seconds()
                return False, max(1, ceil(remaining))
            counter.count += 1
            counter.save(update_fields=["window_start", "count"])
        return True, 0
    except DatabaseError as exc:
        raise ThrottleUnavailable("Shared request budgets are temporarily unavailable") from exc


def _allow_attempt(scope, identity, limit, seconds):
    """Compatibility helper for verification code and existing tests."""
    return consume_budget(scope, identity, limit, seconds)[0]


def limit_customer_request(request, scope, limit=12):
    actor = (f"user:{request.user.pk}" if request.user.is_authenticated
             else f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}")
    allowed, retry = consume_budget(f"customer:{scope}", actor, limit, 60)
    if not allowed:
        request._shared_throttle_retry_after = retry
    return not allowed
