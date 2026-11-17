"""Fail-closed nameserver mutation tests; registrar calls are mocked, never live."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AuditEntry, ManagedDomain, RegistrantContact
from .providers import ProviderError


SANDBOX_SETTINGS = {
    "SALES_ENABLED": True,
    "FULFILLMENT_ENABLED": True,
    "RAZORPAY_KEY_ID": "rzp_test_local",
    "RAZORPAY_KEY_SECRET": "fixture-only",
    "RAZORPAY_WEBHOOK_SECRET": "fixture-only",
    "OPENPROVIDER_BASE_URL": "https://api.sandbox.openprovider.nl/v1",
    "OPENPROVIDER_USERNAME": "sandbox-fixture-user",
    "OPENPROVIDER_PASSWORD": "sandbox-fixture-password",
}


@override_settings(**SANDBOX_SETTINGS)
class NameserverRegistrarSafetyTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            "domain-owner", "owner@example.test", "safe-local-fixture-password"
        )
        self.other = get_user_model().objects.create_user(
            "other-user", "other@example.test", "safe-local-fixture-password"
        )
        self.contact = RegistrantContact.objects.create(
            owner=self.owner, first_name="Domain", last_name="Owner",
            email=self.owner.email, phone_area_code="11",
            phone_subscriber_number="12345678", street="Test Rd",
            street_number="1", city="Delhi", state="Delhi",
            postal_code="110001", openprovider_handle="OWNER-123",
        )
        self.domain = ManagedDomain.objects.create(
            owner=self.owner, name="example.com", provider_id=13579, status="active",
        )
        self.url = reverse("nameservers", args=[self.domain.pk])
        self.payload = {"ns1": "ns1.example.net", "ns2": "ns2.example.net"}
        self.client.force_login(self.owner)

    def registrar_record(self, **changes):
        result = {
            "id": self.domain.provider_id,
            "domain": {"name": "example", "extension": "com"},
            "owner_handle": "OWNER-123",
            "status": "ACT",
            "renewal_date": "2028-01-01 00:00:00",
        }
        result.update(changes)
        return result

    @patch("shop.views.Openprovider")
    def test_verified_owner_and_active_registrar_record_allows_update(self, provider_cls):
        provider = provider_cls.return_value
        provider.get_domain.return_value = self.registrar_record()
        response = self.client.post(self.url, self.payload)
        self.assertRedirects(response, reverse("dashboard"))
        provider.get_domain.assert_called_once_with(self.domain.provider_id)
        provider.update_nameservers.assert_called_once_with(
            self.domain.provider_id, ["ns1.example.net", "ns2.example.net"]
        )
        self.assertEqual(AuditEntry.objects.filter(
            actor=self.owner, domain=self.domain, action="nameservers_changed"
        ).count(), 1)

    @patch("shop.views.Openprovider")
    @override_settings(SALES_ENABLED=False)
    def test_sales_disabled_blocks_provider_even_if_fulfillment_enabled(self, provider_cls):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 200)
        provider_cls.assert_not_called()
        self.assertFalse(AuditEntry.objects.filter(action="nameservers_changed").exists())

    @patch("shop.views.Openprovider")
    @override_settings(FULFILLMENT_ENABLED=False)
    def test_fulfillment_disabled_blocks_provider(self, provider_cls):
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 200)
        provider_cls.assert_not_called()

    @patch("shop.views.Openprovider")
    @override_settings(OPENPROVIDER_BASE_URL="https://api.openprovider.eu/v1")
    def test_test_payment_cannot_mutate_live_registrar(self, provider_cls):
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 200)
        provider_cls.assert_not_called()

    @patch("shop.views.Openprovider")
    def test_missing_customer_handle_blocks_before_registrar_read(self, provider_cls):
        self.contact.openprovider_handle = ""
        self.contact.save(update_fields=["openprovider_handle"])
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 200)
        provider_cls.assert_not_called()

    @patch("shop.views.Openprovider")
    def test_wrong_registrar_owner_blocks_mutation(self, provider_cls):
        provider = provider_cls.return_value
        provider.get_domain.return_value = self.registrar_record(owner_handle="OTHER-HANDLE")
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 200)
        provider.update_nameservers.assert_not_called()
        self.assertFalse(AuditEntry.objects.filter(action="nameservers_changed").exists())

    @patch("shop.views.Openprovider")
    def test_wrong_domain_id_or_name_blocks_mutation(self, provider_cls):
        provider = provider_cls.return_value
        for record in (
            self.registrar_record(id=87654),
            self.registrar_record(domain={"name": "unrelated", "extension": "com"}),
        ):
            with self.subTest(record=record):
                provider.get_domain.return_value = record
                self.assertEqual(self.client.post(self.url, self.payload).status_code, 200)
        provider.update_nameservers.assert_not_called()

    @patch("shop.views.Openprovider")
    def test_pending_registrar_status_blocks_mutation(self, provider_cls):
        provider = provider_cls.return_value
        provider.get_domain.return_value = self.registrar_record(status="REQ")
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 200)
        provider.update_nameservers.assert_not_called()

    @patch("shop.views.Openprovider")
    def test_registrar_read_timeout_blocks_mutation(self, provider_cls):
        provider = provider_cls.return_value
        provider.get_domain.side_effect = ProviderError("fixture registrar timeout")
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 200)
        provider.update_nameservers.assert_not_called()
        self.assertFalse(AuditEntry.objects.filter(action="nameservers_changed").exists())

    @patch("shop.views.Openprovider")
    def test_other_customer_cannot_change_nameservers(self, provider_cls):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 404)
        provider_cls.assert_not_called()
