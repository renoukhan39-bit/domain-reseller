"""Database email identity and race handling, using synthetic accounts only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from shop.forms import ChangeUserAdminForm, SafePasswordResetForm, SignupForm, SignupUserAdminForm
from shop.models import EmailVerification


PASSWORD = "Long-local-test-password-4581"


def signup_data(username="new", email="new@example.test"):
    return {"username": username, "email": email, "password1": PASSWORD, "password2": PASSWORD}


class EmailIdentityTests(TestCase):
    def test_signup_normalizes_email_and_rejects_existing_case_and_spaces(self):
        existing = get_user_model().objects.create(username="existing", email="  Existing@Example.TEST  ")
        duplicate = SignupForm(signup_data(email=" existing@example.test "))
        self.assertFalse(duplicate.is_valid())
        self.assertEqual(duplicate.errors["email"], ["Email already in use"])
        valid = SignupForm(signup_data(email="  New@EXAMPLE.TEST  "))
        self.assertTrue(valid.is_valid(), valid.errors)
        saved = valid.save()
        self.assertEqual(saved.email, "new@example.test")
        self.assertFalse(saved.is_active)
        existing.refresh_from_db()
        self.assertEqual(existing.email, "  Existing@Example.TEST  ")

    def test_database_rejects_duplicate_create_and_update_and_preserves_blank_accounts(self):
        users = get_user_model().objects
        users.create_user("first", "First@Example.TEST")
        second = users.create_user("second", "second@example.test")
        with self.assertRaises(IntegrityError), transaction.atomic():
            users.create_user("duplicate", "  first@example.test  ")
        with self.assertRaises(IntegrityError), transaction.atomic():
            users.filter(pk=second.pk).update(email="FIRST@EXAMPLE.TEST")
        users.create_user("blank-one", "")
        users.create_user("blank-two", "")
        users.create_user("blank-spaces", "  ")
        second.refresh_from_db()
        self.assertEqual(second.email, "second@example.test")

    def test_admin_forms_validate_normalized_email_and_allow_unchanged_or_blank_email(self):
        user = get_user_model().objects.create_user("existing", "existing@example.test")
        create = SignupUserAdminForm(signup_data(email=" EXISTING@example.test "))
        self.assertFalse(create.is_valid())
        self.assertEqual(create.errors["email"], ["Email already in use"])
        change = ChangeUserAdminForm({"username": "new", "email": "EXISTING@example.test"})
        self.assertFalse(change.is_valid())
        self.assertEqual(change.errors["email"], ["Email already in use"])
        unchanged = ChangeUserAdminForm({
            "username": user.username, "email": " EXISTING@example.test ", "date_joined": user.date_joined,
        }, instance=user)
        self.assertTrue(unchanged.is_valid(), unchanged.errors)
        blank = SignupUserAdminForm(signup_data(username="blank", email=""))
        self.assertTrue(blank.is_valid(), blank.errors)

    def test_password_reset_preserves_django_eligibility_for_legacy_spaced_email(self):
        user = get_user_model().objects.create_user("active", "active@example.test", PASSWORD)
        get_user_model().objects.filter(pk=user.pk).update(email="  Active@Example.TEST ")
        form = SafePasswordResetForm()
        self.assertEqual([account.pk for account in form.get_users("active@example.test")], [user.pk])
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertEqual(list(form.get_users("active@example.test")), [])
        user.is_active = True
        user.set_unusable_password()
        user.save(update_fields=["is_active", "password"])
        self.assertEqual(list(form.get_users("active@example.test")), [])


@skipUnless(connection.vendor == "postgresql", "Signup race requires PostgreSQL")
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SignupConcurrencyTests(TransactionTestCase):
    def simultaneous_signup(self, payloads, field):
        barrier = Barrier(2)
        original = getattr(SignupForm, field)

        def clean(form):
            value = original(form)
            barrier.wait(timeout=10)
            return value

        def signup(payload):
            close_old_connections()
            try:
                response = Client().post(reverse("signup"), payload)
                return response.status_code, response.content
            finally:
                connections.close_all()

        with patch.object(SignupForm, field, clean), patch("shop.views.request_verification"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(signup, payloads))

    def test_concurrent_case_variant_signups_create_one_pending_account(self):
        outcomes = self.simultaneous_signup([
            signup_data("first", "race@example.test"),
            signup_data("second", "RACE@EXAMPLE.TEST"),
        ], "clean_email")
        self.assertCountEqual([status for status, _ in outcomes], [200, 302])
        self.assertIn(b"Email already in use", next(body for status, body in outcomes if status == 200))
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(EmailVerification.objects.count(), 1)
        self.assertFalse(get_user_model().objects.get().is_active)

    def test_concurrent_username_signup_returns_validation_error(self):
        outcomes = self.simultaneous_signup([
            signup_data("same", "one@example.test"),
            signup_data("same", "two@example.test"),
        ], "clean_username")
        self.assertCountEqual([status for status, _ in outcomes], [200, 302])
        self.assertIn(b"already exists", next(body for status, body in outcomes if status == 200))
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(EmailVerification.objects.count(), 1)


class EmailIdentityMigrationTests(TransactionTestCase):
    before = ("shop", "0003_domainorder_refund_attempted_at_and_more")
    after = ("shop", "0004_unique_user_email")

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.before])
        self.old_apps = executor.loader.project_state([self.before]).apps
        self.users = self.old_apps.get_model("auth", "User").objects

    def tearDown(self):
        # These tests only create synthetic auth rows, without commerce records.
        self.users.all().delete()
        MigrationExecutor(connection).migrate([self.after])
        super().tearDown()

    def migrate(self):
        MigrationExecutor(connection).migrate([self.after])

    def test_existing_accounts_are_preserved_and_constraint_can_reverse_and_reapply(self):
        existing = self.users.create(username="existing", email=" Legacy@Example.TEST ")
        blank = self.users.create(username="blank", email="")
        self.migrate()
        self.assertEqual(self.users.get(pk=existing.pk).email, " Legacy@Example.TEST ")
        self.assertTrue(self.users.filter(pk=blank.pk).exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.users.create(username="duplicate", email="legacy@example.test")
        MigrationExecutor(connection).migrate([self.before])
        self.migrate()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.users.create(username="duplicate", email="LEGACY@example.test")

    def test_ambiguous_legacy_accounts_block_without_changing_or_exposing_addresses(self):
        self.users.create(username="first", email=" Private@Example.TEST ")
        self.users.create(username="second", email="private@example.test")
        before = list(self.users.order_by("pk").values("pk", "username", "email"))
        with self.assertRaises(RuntimeError) as captured:
            self.migrate()
        self.assertIn("1 duplicate address group(s)", str(captured.exception))
        self.assertNotIn("private", str(captured.exception).lower())
        self.assertEqual(list(self.users.order_by("pk").values("pk", "username", "email")), before)

    def test_ambiguous_legacy_addresses_never_choose_a_verification_or_reset_account(self):
        from shop.accounts.verification import request_verification

        first = self.users.create(username="first", email="ambiguous@example.test", is_active=False)
        self.users.create(username="second", email="AMBIGUOUS@EXAMPLE.TEST", is_active=True)
        EmailVerification.objects.create(user_id=first.pk)
        with patch("shop.accounts.verification.send_verification") as send:
            request_verification("ambiguous@example.test", "192.0.2.1")
        send.assert_not_called()
        self.assertEqual(list(SafePasswordResetForm().get_users("ambiguous@example.test")), [])
