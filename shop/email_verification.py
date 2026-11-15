"""Single-use signup verification using Django signing, email and database locks."""
import logging
import uuid
from smtplib import SMTPException
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import AuditEntry, EmailVerification
from .throttling import _allow_attempt

logger = logging.getLogger(__name__)
TOKEN_SALT = "registrant-email-verify-v2"
RESEND_MESSAGE = "If this address has an account awaiting verification, we will send an activation link. Please check your inbox or try again later."


def request_verification(email, remote_addr):
    """Identical visible outcome for unknown, active, throttled and failed delivery."""
    email = email.strip().lower()
    # Do not trust X-Forwarded-For. Apply limits before looking up the account.
    if not _allow_attempt("ip-minute", remote_addr, 5, 60):
        return
    if not _allow_attempt("email-minute", email, 1, 60):
        return
    if not _allow_attempt("email-hour", email, 3, 3600):
        return
    user = get_user_model().objects.filter(email__iexact=email, is_active=False).first()
    if user is not None:
        send_verification(user)


def send_verification(user):
    """Rotate the pending token, then send with a bounded SMTP timeout.

    SMTP is deliberately outside the transaction. A failed/uncertain send leaves
    the account pending and its link usable; another request can retry after the
    cooldown. Provider exceptions and recipient/token contents are never logged.
    """
    with transaction.atomic():
        # Always lock User before pending, matching consume_verification.
        user = get_user_model().objects.select_for_update().filter(pk=user.pk).first()
        if user is None or user.is_active:
            return
        pending = EmailVerification.objects.select_for_update().filter(user=user).first()
        if pending is None:
            return
        pending.nonce = uuid.uuid4()
        pending.save(update_fields=["nonce"])
        token = signing.dumps({"uid": user.pk, "email": user.email, "nonce": str(pending.nonce)}, salt=TOKEN_SALT)
    base = settings.EMAIL_VERIFICATION_BASE_URL.rstrip("/")
    try:
        parsed = urlsplit(base)
        safe_origin = (parsed.scheme in ("http", "https") and parsed.hostname
                       and not any(c.isspace() for c in base)
                       and not (parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path)
                       and (settings.DEBUG or parsed.scheme == "https"))
        # Accessing port also validates its syntax/range.
        parsed.port
    except ValueError:
        safe_origin = False
    if not safe_origin:
        AuditEntry.objects.create(actor=user, action="verification_email_failed")
        logger.error("Verification email public origin is not configured safely")
        return
    link = base + reverse("verify_email", args=[token])
    try:
        delivered = send_mail("Verify your domain reseller account", f"Verify your email: {link}",
                              settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except (SMTPException, OSError, ImproperlyConfigured, ValueError):
        delivered = 0
    action = "verification_email_sent" if delivered else "verification_email_failed"
    AuditEntry.objects.create(actor=user, action=action)
    if not delivered:
        logger.warning("Verification email delivery failed")


def _token_data(token):
    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)
        if not isinstance(data, dict):
            return None
        uid, email, nonce = data["uid"], data["email"], uuid.UUID(data["nonce"])
        if not isinstance(uid, int) or not isinstance(email, str):
            return None
    except (signing.BadSignature, KeyError, TypeError, ValueError, AttributeError):
        return None
    return uid, email, nonce


def verification_pending(token):
    data = _token_data(token)
    if data is None:
        return False
    uid, email, nonce = data
    return EmailVerification.objects.filter(user_id=uid, user__email=email, user__is_active=False, nonce=nonce).exists()


def consume_verification(token):
    """Activate once; a link is never a reusable login credential."""
    data = _token_data(token)
    if data is None:
        return False
    uid, email, nonce = data
    with transaction.atomic():
        # Lock the user as well, to serialize activation with account changes.
        user = get_user_model().objects.select_for_update().filter(pk=uid).first()
        if user is None or user.is_active or user.email != email:
            return False
        pending = EmailVerification.objects.select_for_update().filter(user=user, nonce=nonce).first()
        if pending is None:
            return False
        user.is_active = True
        user.save(update_fields=["is_active"])
        pending.delete()
        AuditEntry.objects.create(actor=user, action="email_verified")
    return True
