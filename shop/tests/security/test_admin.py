"""Administrative evidence must survive object, bulk, and related deletion routes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest import skipUnless
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.db import IntegrityError, close_old_connections, connection, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from shop.models import AuditEntry, DomainOrder, ManagedDomain, PaymentEvent, RegistrantContact, TLDPrice


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class AdminEvidenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.superuser = users.objects.create_superuser('admin', 'admin@example.test')
        cls.staff = users.objects.create_user('staff', 'staff@example.test', is_staff=True)
        cls.staff.user_permissions.set(Permission.objects.all())
        cls.customer = users.objects.create_user('customer', 'customer@example.test')
        cls.actor = users.objects.create_user('operator', 'operator@example.test')
        cls.domain = ManagedDomain.objects.create(
            owner=cls.customer, name='evidence.example', provider_id=1234, status='active',
        )
        cls.order = DomainOrder.objects.create(
            owner=cls.customer, domain='evidence.example', operation=DomainOrder.REGISTER,
            amount_paise=129900, idempotency_key='evidence-order',
        )
        cls.payment = PaymentEvent.objects.create(
            event_id='evt_evidence', event_type='payment.captured', payload_sha256='a' * 64,
        )
        cls.audit = AuditEntry.objects.create(
            actor=cls.actor, action='registration_confirmed', order=cls.order, domain=cls.domain,
        )
        cls.contact = RegistrantContact.objects.create(
            owner=cls.customer, first_name='Customer', last_name='Fixture',
            email='customer@example.test', phone_area_code='11', phone_subscriber_number='12345678',
            street='Fixture Road', street_number='1', city='Delhi', state='Delhi',
            postal_code='110001', openprovider_handle='CF123-IN',
        )

    def change_url(self, obj):
        return reverse(f'admin:shop_{obj._meta.model_name}_change', args=[obj.pk])

    def delete_url(self, obj):
        return reverse(f'admin:shop_{obj._meta.model_name}_delete', args=[obj.pk])

    def test_financial_registrar_and_audit_records_are_view_only(self):
        records = (self.order, self.payment, self.audit, self.domain)
        for operator in (self.staff, self.superuser):
            self.client.force_login(operator)
            for obj in records:
                with self.subTest(operator=operator.username, model=obj._meta.model_name):
                    self.assertEqual(self.client.get(self.change_url(obj)).status_code, 200)
                    self.assertEqual(self.client.post(self.change_url(obj), {}).status_code, 403)
                    add_url = reverse(f'admin:shop_{obj._meta.model_name}_add')
                    self.assertEqual(self.client.get(add_url).status_code, 403)
                    self.assertEqual(self.client.post(add_url, {}).status_code, 403)
                    self.assertEqual(self.client.get(self.delete_url(obj)).status_code, 403)
                    self.assertEqual(self.client.post(self.delete_url(obj), {'post': 'yes'}).status_code, 403)
                    self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_bulk_action_cannot_delete_evidence(self):
        for operator in (self.staff, self.superuser):
            self.client.force_login(operator)
            for obj in (self.order, self.payment, self.audit, self.domain):
                with self.subTest(operator=operator.username, model=obj._meta.model_name):
                    list_url = reverse(f'admin:shop_{obj._meta.model_name}_changelist')
                    response = self.client.get(list_url)
                    self.assertEqual(response.status_code, 200)
                    action_form = response.context['action_form']
                    actions = [value for value, label in action_form.fields['action'].choices] if action_form else []
                    self.assertNotIn('delete_selected', actions)
                    self.client.post(list_url, {'action': 'delete_selected', '_selected_action': obj.pk, 'post': 'yes'})
                    self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_linked_contact_cannot_be_changed_or_deleted(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(self.change_url(self.contact)).status_code, 200)
        self.assertEqual(self.client.post(self.change_url(self.contact), {'owner': self.actor.pk}).status_code, 403)
        self.assertEqual(self.client.post(self.delete_url(self.contact), {'post': 'yes'}).status_code, 403)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.owner_id, self.customer.pk)
        self.assertEqual(self.contact.openprovider_handle, 'CF123-IN')

    def test_user_deletion_preserves_audit_actor_for_single_and_bulk_routes(self):
        self.client.force_login(self.superuser)
        user_delete = reverse('admin:auth_user_delete', args=[self.actor.pk])
        response = self.client.post(user_delete, {'post': 'yes'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(get_user_model().objects.filter(pk=self.actor.pk).exists())
        self.client.post(reverse('admin:auth_user_changelist'), {
            'action': 'delete_selected', '_selected_action': self.actor.pk, 'post': 'yes',
        })
        self.audit.refresh_from_db()
        self.assertEqual(self.audit.actor_id, self.actor.pk)

    def test_customers_with_registered_assets_cannot_be_deleted(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('admin:auth_user_delete', args=[self.customer.pk]), {'post': 'yes'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(get_user_model().objects.filter(pk=self.customer.pk).exists())

    def test_unlinked_profile_and_pricing_are_editable(self):
        self.client.force_login(self.superuser)
        RegistrantContact.objects.filter(pk=self.contact.pk).update(openprovider_handle='')
        self.contact.refresh_from_db()
        data = {field.name: getattr(self.contact, field.name) for field in RegistrantContact._meta.fields
                if field.editable and field.name not in ('id', 'owner')}
        data['owner'] = self.actor.pk
        data['city'] = 'Mumbai'
        response = self.client.post(self.change_url(self.contact), data)
        self.assertEqual(response.status_code, 302)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.city, 'Mumbai')
        self.assertEqual(self.contact.owner_id, self.customer.pk)
        price = TLDPrice.objects.create(extension='com', registration_paise=129900, renewal_paise=139900)
        response = self.client.post(self.change_url(price), {
            'extension': 'com', 'registration_paise': 139900, 'renewal_paise': 149900, 'enabled': True,
        })
        self.assertEqual(response.status_code, 302)
        price.refresh_from_db()
        self.assertTrue(price.enabled)
        self.assertEqual(price.registration_paise, 139900)

    def test_unrelated_user_save_integrity_errors_remain_visible(self):
        self.client.force_login(self.superuser)
        model_admin = admin.site._registry[get_user_model()]
        with patch.object(model_admin, 'save_model', side_effect=IntegrityError('Unrelated integrity failure')):
            with self.assertRaisesMessage(IntegrityError, 'Unrelated integrity failure'):
                self.client.post(reverse('admin:auth_user_add'), {
                    'username': 'new', 'email': 'new@example.test', 'usable_password': 'true',
                    'password1': 'StrongAdminFixture-12345', 'password2': 'StrongAdminFixture-12345',
                })
        self.assertFalse(get_user_model().objects.filter(username='new').exists())

    def test_user_add_form_rejects_duplicate_normalized_email(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin:auth_user_add'))
        self.assertContains(response, 'name="email"')
        response = self.client.post(reverse('admin:auth_user_add'), {
            'username': 'duplicate', 'email': ' CUSTOMER@example.test ',
            'password1': 'StrongAdminFixture-12345', 'password2': 'StrongAdminFixture-12345',
            'usable_password': 'true',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['adminform'].form.errors)
        self.assertFalse(get_user_model().objects.filter(username='duplicate').exists())

    def test_user_edit_form_rejects_duplicate_normalized_email(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('admin:auth_user_change', args=[self.actor.pk]), {
            'username': self.actor.username, 'email': ' CUSTOMER@example.test ', 'is_active': True,
            'date_joined_0': self.actor.date_joined.strftime('%Y-%m-%d'),
            'date_joined_1': self.actor.date_joined.strftime('%H:%M:%S'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['adminform'].form.errors)
        self.actor.refresh_from_db()
        self.assertEqual(self.actor.email, 'operator@example.test')


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class AdminContactConcurrencyTests(TransactionTestCase):
    def test_waiting_admin_post_cannot_overwrite_new_registrar_handle(self):
        operator = get_user_model().objects.create_superuser('admin', 'admin@example.test')
        customer = get_user_model().objects.create_user('customer', 'customer@example.test')
        contact = RegistrantContact.objects.create(
            owner=customer, first_name='Customer', last_name='Fixture', email='customer@example.test',
            phone_area_code='11', phone_subscriber_number='12345678', street='Fixture Road',
            street_number='1', city='Delhi', state='Delhi', postal_code='110001',
        )
        data = {field.name: getattr(contact, field.name) for field in RegistrantContact._meta.fields
                if field.editable and field.name not in ('id', 'owner')}
        data['owner'] = customer.pk
        data['city'] = 'Mumbai'
        snapshot_read = Event()
        model_admin = admin.site._registry[RegistrantContact]
        original_get_object = model_admin.get_object

        def observe_snapshot(*args, **kwargs):
            obj = original_get_object(*args, **kwargs)
            if obj and not obj.openprovider_handle:
                snapshot_read.set()
            return obj

        def submit_change():
            close_old_connections()
            try:
                client = Client()
                client.force_login(operator)
                return client.post(reverse('admin:shop_registrantcontact_change', args=[contact.pk]), data).status_code
            finally:
                connections.close_all()

        with patch.object(model_admin, 'get_object', side_effect=observe_snapshot):
            with ThreadPoolExecutor(max_workers=1) as executor:
                with transaction.atomic():
                    locked = RegistrantContact.objects.select_for_update().get(pk=contact.pk)
                    pending = executor.submit(submit_change)
                    self.assertTrue(snapshot_read.wait(10), 'Admin did not read the original contact')
                    locked.openprovider_handle = 'CF123-IN'
                    locked.save(update_fields=['openprovider_handle', 'updated_at'])
                self.assertEqual(pending.result(timeout=15), 403)
        contact.refresh_from_db()
        self.assertEqual(contact.openprovider_handle, 'CF123-IN')
        self.assertEqual(contact.city, 'Delhi')


@skipUnless(connection.vendor == 'postgresql', 'Admin email races require PostgreSQL')
@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class AdminEmailConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_superuser('admin', 'admin@example.test')

    def simultaneous_posts(self, requests):
        model_admin = admin.site._registry[get_user_model()]
        original_save = model_admin.save_model
        barrier = Barrier(2)

        def save_after_validation(*args, **kwargs):
            barrier.wait(timeout=10)
            return original_save(*args, **kwargs)

        def post(item):
            close_old_connections()
            try:
                client = Client()
                client.force_login(self.operator)
                url, payload = item
                response = client.post(url, payload)
                return response.status_code, response.get('Location'), [str(message) for message in get_messages(response.wsgi_request)]
            finally:
                connections.close_all()

        with patch.object(model_admin, 'save_model', side_effect=save_after_validation):
            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(post, requests))

    def test_concurrent_add_duplicate_email_returns_retry_message(self):
        url = reverse('admin:auth_user_add')
        requests = [(url, {
            'username': username, 'email': email, 'usable_password': 'true',
            'password1': 'StrongAdminFixture-12345', 'password2': 'StrongAdminFixture-12345',
        }) for username, email in [('first', 'race@example.test'), ('second', 'RACE@EXAMPLE.TEST')]]
        results = self.simultaneous_posts(requests)
        self.assertEqual([status for status, _, _ in results], [302, 302])
        self.assertEqual(sum(location == url for _, location, _ in results), 1)
        self.assertTrue(any('Email already in use. Reload the account and try again.' in messages
                            for _, _, messages in results))
        self.assertEqual(get_user_model().objects.filter(email='race@example.test').count(), 1)
        self.assertEqual(get_user_model().objects.count(), 2)

    def test_concurrent_edit_duplicate_email_preserves_losing_account(self):
        users = [get_user_model().objects.create_user(name, f'{name}@example.test') for name in ('first', 'second')]
        requests = [(reverse('admin:auth_user_change', args=[user.pk]), {
            'username': user.username, 'email': 'race@example.test', 'is_active': True,
            'date_joined_0': user.date_joined.strftime('%Y-%m-%d'),
            'date_joined_1': user.date_joined.strftime('%H:%M:%S'),
        }) for user in users]
        results = self.simultaneous_posts(requests)
        self.assertEqual([status for status, _, _ in results], [302, 302])
        self.assertTrue(any('Email already in use. Reload the account and try again.' in messages
                            for _, _, messages in results))
        self.assertEqual(get_user_model().objects.filter(email='race@example.test').count(), 1)
        for user in users:
            original_email = user.email
            user.refresh_from_db()
            self.assertIn(user.email, (original_email, 'race@example.test'))
        self.assertEqual(get_user_model().objects.count(), 3)
