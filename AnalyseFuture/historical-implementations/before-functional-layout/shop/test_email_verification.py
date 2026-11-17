"""Verification security tests use local mail only; no external provider claims."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from smtplib import SMTPException
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .email_verification import (
    RESEND_MESSAGE,
    TOKEN_SALT,
    _allow_attempt,
    consume_verification,
    send_verification,
)
from .models import AuditEntry, EmailVerification, EmailVerificationThrottle


MAIL_SETTINGS = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "EMAIL_VERIFICATION_BASE_URL": "https://store.example.test",
    "EMAIL_VERIFICATION_MAX_AGE": 86400,
}


@override_settings(**MAIL_SETTINGS)
class EmailVerificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "pending", "pending@example.test", "local-test-password", is_active=False,
        )
        EmailVerification.objects.create(user=self.user)
        self.url = reverse("resend_verification")

    def token(self):
        send_verification(self.user)
        return mail.outbox[-1].body.split()[-1].rstrip("/").rsplit("/", 1)[-1]

    def resend(self, email=None, **extra):
        return self.client.post(self.url, {"email": email or self.user.email}, **extra)

    def test_resend_unknown_active_disabled_and_pending_have_same_response(self):
        active = get_user_model().objects.create_user("active", "active@example.test")
        disabled = get_user_model().objects.create_user(
            "disabled", "disabled@example.test", is_active=False,
        )
        for email in (self.user.email, "missing@example.test", active.email, disabled.email):
            with self.subTest(email=email):
                response = self.resend(email)
                self.assertRedirects(response, reverse("resend_verification_done"))
                self.assertEqual(response.content, b"")
                done = self.client.get(response.url)
                self.assertContains(done, RESEND_MESSAGE)
                self.assertNotContains(done, email)
                self.assertIn("no-store", done["Cache-Control"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        disabled.refresh_from_db()
        self.assertFalse(disabled.is_active)

    def test_get_does_not_send_and_post_requires_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        page = browser.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(len(mail.outbox), 0)
        rejected = browser.post(self.url, {"email": self.user.email})
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)
        accepted = browser.post(self.url, {
            "email": self.user.email, "csrfmiddlewaretoken": browser.cookies["csrftoken"].value,
        })
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_validates_email_and_normalizes_case(self):
        response = self.resend("invalid-address")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.resend("  PENDING@EXAMPLE.TEST  ")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_link_uses_configured_origin_instead_of_request_host(self):
        with override_settings(ALLOWED_HOSTS=["attacker.example.test"]):
            self.resend(HTTP_HOST="attacker.example.test")
        self.assertIn("https://store.example.test/verify/", mail.outbox[0].body)
        self.assertNotIn("attacker.example.test", mail.outbox[0].body)

    def test_activation_is_single_use_does_not_login_and_cannot_reenable_disabled_user(self):
        token = self.token()
        url = reverse("verify_email", args=[token])
        browser = Client(enforce_csrf_checks=True)
        confirmation = browser.get(url)
        self.assertEqual(confirmation.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(browser.post(url).status_code, 403)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        response = browser.post(url, {"csrfmiddlewaretoken": browser.cookies["csrftoken"].value})
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("_auth_user_id", browser.session)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(EmailVerification.objects.filter(user=self.user).exists())
        self.assertEqual(self.client.get(url).status_code, 400)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(url).status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(AuditEntry.objects.filter(action="email_verified").count(), 1)

    def test_verifying_another_account_does_not_switch_logged_in_customer(self):
        customer = get_user_model().objects.create_user("customer", "customer@example.test")
        self.client.force_login(customer)
        self.client.post(reverse("verify_email", args=[self.token()]))
        self.assertEqual(self.client.session["_auth_user_id"], str(customer.pk))

    def test_signup_email_failure_leaves_recoverable_inactive_account(self):
        with patch("shop.email_verification.send_mail", side_effect=SMTPException("private smtp details")):
            with self.assertLogs("shop.email_verification", level="WARNING"):
                response = self.client.post(reverse("signup"), {
                    "username": "new-signup", "email": "new-signup@example.test",
                    "password1": "VERYlongSecret-12345", "password2": "VERYlongSecret-12345",
                }, REMOTE_ADDR="192.0.2.55")
        self.assertRedirects(response, reverse("login"))
        new_user = get_user_model().objects.get(username="new-signup")
        self.assertFalse(new_user.is_active)
        self.assertTrue(EmailVerification.objects.filter(user=new_user).exists())
        self.assertFalse(self.client.login(username=new_user.username, password="VERYlongSecret-12345"))
        EmailVerificationThrottle.objects.all().delete()
        self.resend(new_user.email)
        self.assertEqual(mail.outbox[0].to, [new_user.email])

    def test_tokens_expire_and_tampered_or_legacy_tokens_fail(self):
        issued = timezone.now().timestamp()
        with patch("django.core.signing.time.time", return_value=issued):
            token = self.token()
        with patch("django.core.signing.time.time", return_value=issued + 86401):
            self.assertFalse(consume_verification(token))
        self.assertFalse(consume_verification(token + "tampered"))
        legacy = signing.dumps({"uid": self.user.pk}, salt="registrant-email-verify")
        self.assertFalse(consume_verification(legacy))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_new_email_rotated_nonce_and_deleted_user_invalidate_old_links(self):
        first = self.token()
        second = self.token()
        self.assertFalse(consume_verification(first))
        self.user.email = "changed@example.test"
        self.user.save(update_fields=["email"])
        self.assertFalse(consume_verification(second))
        third = self.token()
        self.user.delete()
        self.assertFalse(consume_verification(third))

    def test_malformed_signed_payloads_are_rejected(self):
        for payload in ([], "invalid", {}, {"uid": 1, "email": self.user.email, "nonce": "bad"},
                        {"uid": [], "email": self.user.email, "nonce": str(uuid.uuid4())}):
            with self.subTest(payload=payload):
                self.assertFalse(consume_verification(signing.dumps(payload, salt=TOKEN_SALT)))
        response = self.client.get(reverse("verify_email", args=["bad"]))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Resend verification email", status_code=400)

    def test_invalid_production_email_origins_fail_closed(self):
        invalid_origins = ("", "http://store.example.test", "https://user:secret@store.example.test",
                           "https://store.example.test/path", "https://store.example.test?q=evil",
                           "https://store.example.test#evil", "https://[",
                           "https://store.example.test:invalid", "https://store.example.test:70000",
                           "https://store .example.test")
        for base in invalid_origins:
            with self.subTest(base=base), override_settings(DEBUG=False, EMAIL_VERIFICATION_BASE_URL=base):
                EmailVerificationThrottle.objects.all().delete()
                with self.assertLogs("shop.email_verification", level="ERROR") as captured:
                    pending_response = self.resend()
                unknown_response = self.resend("unknown@example.test")
                self.assertEqual(pending_response.status_code, 302)
                self.assertEqual(pending_response.url, reverse("resend_verification_done"))
                self.assertEqual(
                    (pending_response.status_code, pending_response.url, pending_response.content),
                    (unknown_response.status_code, unknown_response.url, unknown_response.content),
                )
                self.assertEqual(captured.output, [
                    "ERROR:shop.email_verification:Verification email public origin is not configured safely",
                ])
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AuditEntry.objects.filter(action="verification_email_failed").count(), len(invalid_origins))

    def test_send_to_stale_deleted_user_is_a_noop(self):
        get_user_model().objects.filter(pk=self.user.pk).delete()
        send_verification(self.user)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AuditEntry.objects.count(), 0)

    def test_failed_delivery_preserves_pending_account_and_safe_response(self):
        for error in (SMTPException("private recipient and token"), OSError("private credential"),
                      ImproperlyConfigured("private email config"), ValueError("private email config")):
            with self.subTest(error=type(error).__name__):
                EmailVerificationThrottle.objects.all().delete()
                with patch("shop.email_verification.send_mail", side_effect=error):
                    with self.assertLogs("shop.email_verification", level="WARNING") as captured:
                        response = self.resend()
                self.assertRedirects(response, reverse("resend_verification_done"))
                self.assertEqual(captured.output, [
                    "WARNING:shop.email_verification:Verification email delivery failed",
                ])
                self.user.refresh_from_db()
                self.assertFalse(self.user.is_active)
                self.assertTrue(EmailVerification.objects.filter(user=self.user).exists())
        self.assertEqual(AuditEntry.objects.filter(action="verification_email_failed").count(), 4)
        EmailVerificationThrottle.objects.all().delete()
        self.resend()
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(consume_verification(self.token()))

    def test_zero_delivery_is_recorded_as_failure_without_account_disclosure(self):
        with patch("shop.email_verification.send_mail", return_value=0):
            with self.assertLogs("shop.email_verification", level="WARNING"):
                self.assertEqual(self.resend().status_code, 302)
        self.assertTrue(AuditEntry.objects.filter(action="verification_email_failed").exists())

    def test_recipient_cooldown_applies_across_ips_and_resets(self):
        now = timezone.now()
        with patch("shop.email_verification.timezone.now", return_value=now):
            self.resend(REMOTE_ADDR="192.0.2.1")
            self.resend("PENDING@EXAMPLE.TEST", REMOTE_ADDR="192.0.2.2")
        self.assertEqual(len(mail.outbox), 1)
        with patch("shop.email_verification.timezone.now", return_value=now + timedelta(seconds=61)):
            self.resend(REMOTE_ADDR="192.0.2.2")
        self.assertEqual(len(mail.outbox), 2)

    def test_recipient_hour_limit_and_window_reset(self):
        now = timezone.now()
        for seconds in (0, 61, 122, 183):
            with patch("shop.email_verification.timezone.now", return_value=now + timedelta(seconds=seconds)):
                self.resend()
        self.assertEqual(len(mail.outbox), 3)
        with patch("shop.email_verification.timezone.now", return_value=now + timedelta(seconds=3601)):
            self.resend()
        self.assertEqual(len(mail.outbox), 4)

    def test_ip_limit_covers_distinct_addresses_and_ignores_forwarded_header(self):
        now = timezone.now()
        with patch("shop.email_verification.timezone.now", return_value=now):
            for index in range(5):
                self.resend(f"unknown{index}@example.test", HTTP_X_FORWARDED_FOR=f"192.0.2.{index}")
            self.resend(HTTP_X_FORWARDED_FOR="192.0.2.99")
        self.assertEqual(len(mail.outbox), 0)
        self.resend(REMOTE_ADDR="192.0.2.99")
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_addresses_are_also_throttled_and_keys_have_no_raw_pii(self):
        self.resend("unknown@example.test", REMOTE_ADDR="192.0.2.1")
        counters = list(EmailVerificationThrottle.objects.values("key", "count"))
        self.assertEqual(len(counters), 3)
        for counter in counters:
            self.assertRegex(counter["key"], r"^[0-9a-f]{64}$")
            self.assertEqual(counter["count"], 1)
        self.resend("UNKNOWN@EXAMPLE.TEST", REMOTE_ADDR="192.0.2.2")
        self.assertEqual(EmailVerificationThrottle.objects.filter(count=2).count(), 0)

    def test_counter_cleanup_removes_stale_rows_without_resetting_active_limits(self):
        self.assertTrue(_allow_attempt("cleanup", "active-identity", 1, 60))
        EmailVerificationThrottle.objects.create(
            key="a" * 64, window_start=timezone.now() - timedelta(days=2), count=3,
        )
        output = StringIO()
        call_command("cleanup_verification_throttles", stdout=output)
        self.assertIn("Removed 1 expired verification throttle counters", output.getvalue())
        self.assertEqual(EmailVerificationThrottle.objects.count(), 1)
        self.assertFalse(_allow_attempt("cleanup", "active-identity", 1, 60))


@skipUnless(connection.vendor == "postgresql", "Row-lock concurrency requires PostgreSQL")
@override_settings(**MAIL_SETTINGS)
class EmailVerificationConcurrencyTests(TransactionTestCase):
    def concurrent(self, operation, workers=4):
        barrier = Barrier(workers)

        def invoke(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(invoke, range(workers)))

    def test_simultaneous_initial_counter_creation_allows_one_attempt(self):
        outcomes = self.concurrent(lambda: _allow_attempt("race", "same-identity", 1, 60))
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual(EmailVerificationThrottle.objects.get().count, 1)

    def test_simultaneous_token_consumption_activates_and_audits_once(self):
        user = get_user_model().objects.create_user("pending", "pending@example.test", is_active=False)
        pending = EmailVerification.objects.create(user=user)
        token = signing.dumps({"uid": user.pk, "email": user.email, "nonce": str(pending.nonce)}, salt=TOKEN_SALT)
        outcomes = self.concurrent(lambda: consume_verification(token))
        self.assertEqual(outcomes.count(True), 1)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertFalse(EmailVerification.objects.filter(user=user).exists())
        self.assertEqual(AuditEntry.objects.filter(action="email_verified").count(), 1)

    def test_simultaneous_resend_and_activation_preserve_one_pending_or_active_state(self):
        user = get_user_model().objects.create_user("pending", "pending@example.test", is_active=False)
        pending = EmailVerification.objects.create(user=user)
        token = signing.dumps({"uid": user.pk, "email": user.email, "nonce": str(pending.nonce)}, salt=TOKEN_SALT)
        barrier = Barrier(2)

        def invoke(send):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                if send:
                    send_verification(user)
                    return None
                return consume_verification(token)
            finally:
                connections.close_all()

        with patch("shop.email_verification.send_mail", return_value=1):
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(invoke, [True, False]))
        user.refresh_from_db()
        if outcomes[1]:
            self.assertTrue(user.is_active)
            self.assertFalse(EmailVerification.objects.filter(user=user).exists())
        else:
            self.assertFalse(user.is_active)
            self.assertTrue(EmailVerification.objects.filter(user=user).exists())
