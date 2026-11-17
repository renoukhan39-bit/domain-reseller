"""Registrant edits must serialize with registrar handle assignment."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from shop.models import RegistrantContact


CONTACT_DATA = {
    "first_name": "Test", "last_name": "Registrant", "company_name": "",
    "email": "contact@example.test", "phone_country_code": "+91",
    "phone_area_code": "11", "phone_subscriber_number": "12345678",
    "street": "Test Road", "street_number": "1", "city": "Delhi",
    "state": "Delhi", "postal_code": "110001", "country": "IN",
}


class ContactTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("contact-owner", "owner@example.test")
        self.client.force_login(self.owner)

    def test_create_then_update_unlinked_contact(self):
        for name in ("First", "Second"):
            response = self.client.post(reverse("contact"), {**CONTACT_DATA, "first_name": name})
            self.assertRedirects(response, reverse("dashboard"))
            self.assertEqual(RegistrantContact.objects.get(owner=self.owner).first_name, name)
        self.assertEqual(RegistrantContact.objects.count(), 1)

    def test_linked_contact_cannot_be_changed_by_customer(self):
        contact = RegistrantContact.objects.create(
            owner=self.owner, openprovider_handle="OWNER-1", **CONTACT_DATA
        )
        response = self.client.post(reverse("contact"), {**CONTACT_DATA, "first_name": "Changed"})
        self.assertContains(response, "Registry contact exists")
        contact.refresh_from_db()
        self.assertEqual(contact.first_name, CONTACT_DATA["first_name"])
        self.assertEqual(contact.openprovider_handle, "OWNER-1")

    def test_customer_can_only_update_own_contact(self):
        other = get_user_model().objects.create_user("other-contact", "other@example.test")
        contact = RegistrantContact.objects.create(owner=other, **CONTACT_DATA)
        self.client.post(reverse("contact"), {**CONTACT_DATA, "first_name": "Mine", "owner": other.pk})
        contact.refresh_from_db()
        self.assertEqual(contact.first_name, CONTACT_DATA["first_name"])
        self.assertEqual(RegistrantContact.objects.get(owner=self.owner).first_name, "Mine")


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class ContactConcurrencyTests(TransactionTestCase):
    def test_profile_post_waits_for_handle_creation_and_preserves_provider_identity(self):
        owner = get_user_model().objects.create_user("contact-race", "race@example.test")
        contact = RegistrantContact.objects.create(owner=owner, **CONTACT_DATA)
        started = Event()
        backend = {}

        def edit_contact():
            close_old_connections()
            try:
                browser = Client()
                browser.force_login(owner)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    backend["pid"] = cursor.fetchone()[0]
                started.set()
                return browser.post(reverse("contact"), {**CONTACT_DATA, "first_name": "Changed"})
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                current = RegistrantContact.objects.select_for_update().get(pk=contact.pk)
                current.openprovider_handle = "ASSIGNED-BY-WORKER"
                current.save(update_fields=["openprovider_handle", "updated_at"])
                request = pool.submit(edit_contact)
                self.assertTrue(started.wait(10))
                blocked = False
                deadline = monotonic() + 10
                while monotonic() < deadline and not request.done():
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT cardinality(pg_blocking_pids(%s)) > 0", [backend["pid"]])
                        blocked = cursor.fetchone()[0]
                    if blocked:
                        break
                    sleep(0.01)
            response = request.result(timeout=10)

        self.assertTrue(blocked, "Expected the contact write to wait for the registrar transaction")
        self.assertContains(response, "Registry contact exists")
        contact.refresh_from_db()
        self.assertEqual(contact.openprovider_handle, "ASSIGNED-BY-WORKER")
        self.assertEqual(contact.first_name, CONTACT_DATA["first_name"])
