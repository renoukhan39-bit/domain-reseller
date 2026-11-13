"""Shared abuse budgets and password-reset delivery safety, using local mail."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from smtplib import SMTPException
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, close_old_connections, connection, connections
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import EmailVerificationThrottle, TLDPrice
from .throttling import consume_budget


LOCAL_SETTINGS = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "EMAIL_VERIFICATION_BASE_URL": "https://accounts.example.test",
    "PASSWORD_HASHERS": ["django.contrib.auth.hashers.MD5PasswordHasher"],
}


@override_settings(**LOCAL_SETTINGS)
class SharedThrottleTests(TestCase):
    def test_login_ip_limit_has_retry_after_and_generic_body(self):
        for _ in range(10):
            response = self.client.post(reverse("login"), {"username": "missing", "password": "invalid"})
            self.assertEqual(response.status_code, 200)
        denied = self.client.post(reverse("login"), {"username": "missing", "password": "invalid"})
        self.assertEqual(denied.status_code, 429)
        self.assertGreaterEqual(int(denied["Retry-After"]), 1)
        self.assertNotContains(denied, "missing", status_code=429)

    def test_admin_login_is_protected_by_the_shared_ip_budget(self):
        for _ in range(10):
            response = self.client.post(reverse("admin:login"), {"username": "missing", "password": "invalid"})
            self.assertEqual(response.status_code, 200)
        denied = self.client.post(reverse("admin:login"), {"username": "missing", "password": "invalid"})
        self.assertEqual(denied.status_code, 429)
        self.assertIn("Retry-After", denied)

    def test_forwarded_ip_headers_cannot_bypass_login_limit(self):
        for index in range(11):
            response = self.client.post(reverse("login"), {"username": f"missing{index}", "password": "invalid"},
                                        HTTP_X_FORWARDED_FOR=f"192.0.2.{index}")
        self.assertEqual(response.status_code, 429)

    def test_login_identifier_budget_applies_across_source_ips(self):
        for index in range(20):
            response = self.client.post(reverse("login"), {"username": "victim", "password": "invalid"},
                                        REMOTE_ADDR=f"192.0.2.{index}")
            self.assertEqual(response.status_code, 200)
        denied = self.client.post(reverse("login"), {"username": "victim", "password": "invalid"},
                                  REMOTE_ADDR="192.0.2.99")
        self.assertEqual(denied.status_code, 429)

    def test_equivalent_unicode_login_names_share_one_budget(self):
        for index in range(20):
            username = "victim" if index % 2 == 0 else "ｖｉｃｔｉｍ"
            response = self.client.post(reverse("login"), {"username": username, "password": "invalid"},
                                        REMOTE_ADDR=f"192.0.2.{index}")
            self.assertEqual(response.status_code, 200)
        denied = self.client.post(reverse("login"), {"username": "victim", "password": "invalid"},
                                  REMOTE_ADDR="192.0.2.99")
        self.assertEqual(denied.status_code, 429)

    def test_password_reset_ip_limit_applies_to_unknown_addresses(self):
        for index in range(5):
            response = self.client.post(reverse("password_reset"), {"email": f"missing{index}@example.test"})
            self.assertEqual(response.status_code, 302)
        denied = self.client.post(reverse("password_reset"), {"email": "another@example.test"})
        self.assertEqual(denied.status_code, 429)
        self.assertIn("Retry-After", denied)
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_recipient_budget_applies_across_ips(self):
        for index in range(3):
            self.assertEqual(self.client.post(reverse("password_reset"), {"email": "victim@example.test"},
                                              REMOTE_ADDR=f"192.0.2.{index}").status_code, 302)
        denied = self.client.post(reverse("password_reset"), {"email": "VICTIM@EXAMPLE.TEST"},
                                  REMOTE_ADDR="192.0.2.99")
        self.assertEqual(denied.status_code, 429)

    def test_get_health_and_webhook_do_not_consume_authentication_budgets(self):
        for _ in range(12):
            self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        self.assertEqual(self.client.get(reverse("health")).status_code, 200)
        with override_settings(RAZORPAY_WEBHOOK_SECRET=""):
            self.assertEqual(self.client.post(reverse("razorpay_webhook"), b"{}", content_type="application/json").status_code, 503)
        self.assertFalse(EmailVerificationThrottle.objects.exists())

    def test_missing_csrf_is_rejected_before_consuming_budget(self):
        browser = Client(enforce_csrf_checks=True)
        browser.get(reverse("login"))
        self.assertEqual(browser.post(reverse("login"), {"username": "missing", "password": "invalid"}).status_code, 403)
        self.assertFalse(EmailVerificationThrottle.objects.exists())

    def test_database_failure_fails_closed_without_disclosing_details(self):
        with patch("shop.throttling.EmailVerificationThrottle.objects.select_for_update", side_effect=DatabaseError("private ip and email")):
            with self.assertLogs("shop.middleware", level="WARNING") as captured:
                response = self.client.post(reverse("login"), {"username": "missing", "password": "invalid"})
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "private", status_code=503)
        self.assertTrue(all("private" not in line for line in captured.output))

    def test_throttle_rows_do_not_contain_raw_identifiers(self):
        self.client.post(reverse("login"), {"username": "private-user", "password": "invalid"}, REMOTE_ADDR="192.0.2.10")
        rows = list(EmailVerificationThrottle.objects.values("key", "count"))
        self.assertTrue(rows)
        for row in rows:
            self.assertRegex(row["key"], r"^[0-9a-f]{64}$")
            self.assertEqual(row["count"], 1)

    def test_existing_domain_search_limiter_is_shared_and_returns_retry_after(self):
        TLDPrice.objects.create(extension="com", registration_paise=10000, renewal_paise=10000, enabled=True)
        with patch("shop.views.Openprovider") as registrar:
            registrar.return_value.check.return_value = False
            for _ in range(20):
                self.assertEqual(self.client.get(reverse("home"), {"domain": "search.com"}).status_code, 200)
            denied = self.client.get(reverse("home"), {"domain": "search.com"})
        self.assertEqual(denied.status_code, 429)
        self.assertIn("Retry-After", denied)
        self.assertEqual(registrar.return_value.check.call_count, 20)

    def test_authenticated_view_budgets_are_isolated_per_customer(self):
        from .views import rate_limited
        first = get_user_model().objects.create_user("first", "first@example.test")
        second = get_user_model().objects.create_user("second", "second@example.test")
        factory = RequestFactory()
        one, two = factory.get("/"), factory.get("/")
        one.user, two.user = first, second
        self.assertFalse(rate_limited(one, "tenant-test", 1))
        self.assertTrue(rate_limited(one, "tenant-test", 1))
        self.assertFalse(rate_limited(two, "tenant-test", 1))

    def test_fixed_window_expires_without_extending_from_blocked_requests(self):
        now = timezone.now()
        with patch("shop.throttling.timezone.now", return_value=now):
            self.assertEqual(consume_budget("window-test", "identity", 1, 60), (True, 0))
        with patch("shop.throttling.timezone.now", return_value=now + timedelta(seconds=10)):
            allowed, retry_after = consume_budget("window-test", "identity", 1, 60)
            self.assertFalse(allowed)
            self.assertEqual(retry_after, 50)
        with patch("shop.throttling.timezone.now", return_value=now + timedelta(seconds=60)):
            self.assertEqual(consume_budget("window-test", "identity", 1, 60), (True, 0))


@override_settings(**LOCAL_SETTINGS)
class SafePasswordResetTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("active", "active@example.test", "local-test-password")

    def test_active_and_unknown_accounts_receive_identical_confirmation(self):
        active = self.client.post(reverse("password_reset"), {"email": self.user.email}, follow=True)
        unknown = self.client.post(reverse("password_reset"), {"email": "unknown@example.test"}, follow=True)
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.redirect_chain, unknown.redirect_chain)
        self.assertEqual(active.content, unknown.content)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_link_uses_trusted_origin_instead_of_request_host(self):
        with override_settings(ALLOWED_HOSTS=["attacker.example.test"]):
            response = self.client.post(reverse("password_reset"), {"email": self.user.email}, HTTP_HOST="attacker.example.test")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://accounts.example.test/accounts/reset/", mail.outbox[0].body)
        self.assertNotIn("attacker.example.test", mail.outbox[0].body)

    def test_transport_and_config_errors_do_not_expose_eligible_accounts(self):
        for error in (SMTPException("private recipient and password"), OSError("private credential"),
                      ValueError("private config"), ImproperlyConfigured("private backend")):
            with self.subTest(error=type(error).__name__):
                EmailVerificationThrottle.objects.all().delete()
                with patch("django.contrib.auth.forms.EmailMultiAlternatives.send", side_effect=error):
                    with self.assertLogs("shop.forms", level="WARNING") as logs:
                        response = self.client.post(reverse("password_reset"), {"email": self.user.email})
                self.assertEqual(response.status_code, 302)
                self.assertTrue(all("private" not in line for line in logs.output))
                unknown = self.client.post(reverse("password_reset"), {"email": "unknown@example.test"})
                self.assertEqual(response.url, unknown.url)

    def test_unsafe_public_origin_keeps_same_safe_confirmation(self):
        for origin in ("", "http://accounts.example.test", "https://[", "https://user:private@accounts.example.test",
                       "https://accounts.example.test/path", "https://accounts.example.test?query=private"):
            with self.subTest(origin=origin), override_settings(DEBUG=False, EMAIL_VERIFICATION_BASE_URL=origin):
                EmailVerificationThrottle.objects.all().delete()
                response = self.client.post(reverse("password_reset"), {"email": self.user.email})
                unknown = self.client.post(reverse("password_reset"), {"email": "unknown@example.test"})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, unknown.url)
        self.assertEqual(len(mail.outbox), 0)


@skipUnless(connection.vendor == "postgresql", "Shared-budget concurrency requires PostgreSQL")
class SharedThrottleConcurrencyTests(TransactionTestCase):
    def test_concurrent_initial_budget_creation_admits_only_limit(self):
        barrier = Barrier(8)

        def attempt(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return consume_budget("initial-race", "same-identity", 3, 60)[0]
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=8) as pool:
            allowed = list(pool.map(attempt, range(8)))
        self.assertEqual(allowed.count(True), 3)
        self.assertEqual(EmailVerificationThrottle.objects.get().count, 3)
