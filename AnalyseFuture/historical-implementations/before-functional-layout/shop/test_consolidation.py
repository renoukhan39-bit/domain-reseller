"""Keep legacy template/helper entry points compatible with one shared policy."""
from pathlib import Path

from django import forms
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from .payment_events import gateway_identifier
from .payments import valid_gateway_id


class GatewayIdentifierCompatibilityTests(SimpleTestCase):
    def test_valid_gateway_identifiers_keep_both_prefix_conventions(self):
        for prefix in ("order", "pay", "rfnd"):
            for value in (prefix + "_a_01", prefix + "_" + "A" * (79 - len(prefix))):
                with self.subTest(prefix=prefix, value=value):
                    self.assertTrue(gateway_identifier(value, prefix))
                    self.assertTrue(valid_gateway_id(value, prefix + "_"))

    def test_unsafe_identifiers_are_rejected_at_both_existing_entry_points(self):
        cases = [None, True, False, 42, b"pay_example", [], {}, "", "pay_",
                 "pay_../payments", "pay_a/b", "pay_a?capture=true", "pay_a#part",
                 "pay_%2Fpayments", "pay_\n", "pay_a\n", "pay_é", "pay_Ａ",
                 " pay_a", "pay_a ", "order_a", "pay_" + "A" * 77]
        for value in cases:
            with self.subTest(value=value):
                self.assertFalse(gateway_identifier(value, "pay"))
                self.assertFalse(valid_gateway_id(value, "pay_"))


@override_settings(TEMPLATES=[{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [Path(__file__).resolve().parent / "templates"],
    "APP_DIRS": True,
}])
class PasswordResetTemplateCompatibilityTests(SimpleTestCase):
    # Stock app-loader order selects admin's registration templates first.
    # These aliases support explicit project-template precedence; the customer
    # URLs continue to name shop/* directly and do not depend on that ordering.
    def test_default_html_names_render_the_authoritative_customer_pages(self):
        context = {"user": AnonymousUser(), "form": forms.Form(),
                   "csrf_token": "synthetic-csrf-token"}
        for page in ("form", "done", "confirm", "complete"):
            for validlink in (True, False):
                with self.subTest(page=page, validlink=validlink):
                    values = dict(context, validlink=validlink)
                    name = "password_reset_" + page + ".html"
                    expected = render_to_string("shop/" + name, values)
                    actual = render_to_string("registration/" + name, values)
                    self.assertEqual(actual, expected)
                    self.assertIn("Domain Reseller", actual)

    def test_default_email_name_keeps_plain_text_and_the_exact_reset_link(self):
        context = {"protocol": "https", "domain": "accounts.example.test",
                   "uid": "fixture-user", "token": "synthetic-reset-token"}
        expected = render_to_string("shop/password_reset_email.html", context)
        actual = render_to_string("registration/password_reset_email.html", context)
        reset_path = reverse("password_reset_confirm", kwargs={
            "uidb64": context["uid"], "token": context["token"]})
        self.assertEqual(actual, expected)
        self.assertIn("https://accounts.example.test" + reset_path, actual)
        self.assertNotIn("<html", actual.lower())
