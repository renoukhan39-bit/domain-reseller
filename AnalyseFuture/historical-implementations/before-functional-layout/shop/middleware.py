"""Throttle sensitive form submissions after Django's CSRF middleware."""
import logging
import unicodedata

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .throttling import ThrottleUnavailable, consume_budget

logger = logging.getLogger(__name__)


def _response(status, retry):
    text = "Please try again later" if status == 429 else "Service temporarily unavailable"
    response = HttpResponse(text, status=status, content_type="text/plain")
    response["Retry-After"] = str(retry)
    response["Cache-Control"] = "no-store"
    return response


class SharedThrottleMiddleware(MiddlewareMixin):
    """No payment webhook limit: authenticated gateway retries must reach validation."""
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != "POST" or request.resolver_match is None:
            return None
        route = request.resolver_match.view_name
        if route not in ("login", "admin:login", "password_reset"):
            return None
        ip = request.META.get("REMOTE_ADDR", "unknown")
        if route in ("login", "admin:login"):
            identifier = unicodedata.normalize("NFKC", str(request.POST.get("username", "")).strip()).casefold()[:254]
            budgets = [("auth:login:ip-minute", ip, 10, 60),
                       ("auth:login:ip-hour", ip, 60, 3600),
                       ("auth:login:identifier-hour", identifier, 20, 3600)]
        else:
            identifier = str(request.POST.get("email", "")).strip().casefold()[:254]
            budgets = [("auth:reset:ip-minute", ip, 5, 60),
                       ("auth:reset:ip-hour", ip, 30, 3600),
                       ("auth:reset:identifier-hour", identifier, 3, 3600)]
        try:
            for scope, identity, limit, seconds in budgets:
                allowed, retry = consume_budget(scope, identity, limit, seconds)
                if not allowed:
                    return _response(429, retry)
        except ThrottleUnavailable:
            logger.warning("Shared authentication request budget unavailable")
            return _response(503, 60)
        return None

    def process_exception(self, request, exception):
        if isinstance(exception, ThrottleUnavailable):
            logger.warning("Shared customer request budget unavailable")
            return _response(503, 60)
        return None

    def process_response(self, request, response):
        retry = getattr(request, "_shared_throttle_retry_after", None)
        if retry is not None:
            # Existing views use the boolean helper; ensure even rendered search
            # failures communicate a real rate limit to browsers and clients.
            return _response(429, retry)
        return response
