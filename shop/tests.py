"""Run: DJANGO_DEBUG=true python manage.py test shop (no live network calls)."""
import hashlib
import hmac
import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .forms import DomainSearchForm, NameServerForm
from .models import DomainOrder, ManagedDomain, PaymentEvent, RegistrantContact, TLDPrice
from .payments import verify_webhook
from .providers import Openprovider, ProviderError
from .services import OrderError, create_checkout_order, fulfill_one, receive_razorpay_webhook, sales_ready


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   EMAIL_VERIFICATION_BASE_URL='https://accounts.example.test')
class AccountTests(TestCase):
    def test_signup_email_verification(self):
        response = self.client.post(reverse('signup'), {'username':'alice','email':'alice@example.test',
          'password1':'VERYlongSecret-12345','password2':'VERYlongSecret-12345'})
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username='alice')
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        link = mail.outbox[0].body.split()[-1]
        self.client.get(link)
        self.client.post(link)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_invalid_token(self):
        self.assertEqual(self.client.get(reverse('verify_email',args=['bad'])).status_code,400)


class ValidationTests(TestCase):
    def test_domain_validation_rejects_subdomains(self):
        self.assertFalse(DomainSearchForm({'domain':'a.b.com'}).is_valid())
        self.assertFalse(DomainSearchForm({'domain':'bad..com'}).is_valid())
        self.assertFalse(DomainSearchForm({'domain':'https://example.com'}).is_valid())
        self.assertEqual(DomainSearchForm({'domain':'Example.COM'}).is_valid(),True)

    def test_nameserver_duplicates_rejected(self):
        form = NameServerForm({'ns1':'ns1.example.com','ns2':'NS1.example.com'})
        self.assertFalse(form.is_valid())

    def test_missing_webhook_secret_fails(self):
        self.assertFalse(verify_webhook(b'{}', '', 'x'))
        self.assertFalse(verify_webhook(b'{}', 'x', ''))

    @override_settings(OPENPROVIDER_USERNAME='tester', OPENPROVIDER_PASSWORD='secret',
        OPENPROVIDER_BASE_URL='https://api.sandbox.openprovider.nl/v1beta')
    def test_registrar_availability_and_premium_safety(self):
        with patch.object(Openprovider, '_request', return_value={'results':[{'domain':'example.com', 'status':'free', 'is_premium':False}]}):
            self.assertTrue(Openprovider().check('example.com'))
        with patch.object(Openprovider, '_request', return_value={'results':[{'domain':'example.com', 'status':'in use', 'is_premium':False}]}):
            self.assertFalse(Openprovider().check('example.com'))
        with patch.object(Openprovider, '_request', return_value={'results':[{'domain':'premium.com', 'status':'free', 'is_premium':True}]}):
            with self.assertRaises(ProviderError):
                Openprovider().check('premium.com')
        with patch.object(Openprovider, '_request', return_value={'results':[{'domain':'example.com', 'status':'mystery', 'is_premium':False}]}):
            with self.assertRaises(ProviderError):
                Openprovider().check('example.com')

    @override_settings(SALES_ENABLED=True, RAZORPAY_KEY_ID='rzp_live_key',
        RAZORPAY_KEY_SECRET='secret', RAZORPAY_WEBHOOK_SECRET='secret',
        OPENPROVIDER_USERNAME='username', OPENPROVIDER_PASSWORD='password',
        OPENPROVIDER_BASE_URL='https://api.sandbox.openprovider.nl/v1beta')
    def test_live_gateway_cannot_checkout_with_sandbox_registrar(self):
        self.assertFalse(sales_ready())

    @override_settings(SALES_ENABLED=True, RAZORPAY_KEY_ID='rzp_test_key',
        RAZORPAY_KEY_SECRET='secret', RAZORPAY_WEBHOOK_SECRET='secret',
        OPENPROVIDER_USERNAME='username', OPENPROVIDER_PASSWORD='password',
        OPENPROVIDER_BASE_URL='https://api.openprovider.eu/v1')
    def test_sandbox_gateway_cannot_checkout_with_live_registrar(self):
        self.assertFalse(sales_ready())


@override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-test-only', FULFILLMENT_ENABLED=True,
                   SALES_ENABLED=True, RAZORPAY_KEY_ID='rzp_test_key',
                   RAZORPAY_KEY_SECRET='razorpay-test-secret',
                   OPENPROVIDER_USERNAME='tester', OPENPROVIDER_PASSWORD='secret')
class PaymentAndFulfillmentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('buyer', 'buyer@example.test', 'strong-test-password')
        self.other = get_user_model().objects.create_user('other', 'other@example.test', 'strong-test-password')
        RegistrantContact.objects.create(owner=self.user, first_name='Buyer', last_name='Person',
          email='buyer@example.test', phone_area_code='11', phone_subscriber_number='12345678',
          street='Example Rd', street_number='10', city='Delhi', state='Delhi', postal_code='110001')
        TLDPrice.objects.create(extension='com', registration_paise=129900, renewal_paise=139900, enabled=True)
        self.order = DomainOrder.objects.create(owner=self.user, domain='safeexample.com',
          operation=DomainOrder.REGISTER, amount_paise=129900, idempotency_key='x',
          razorpay_order_id='order_verified_123')

    def _webhook(self, amount=129900, status='captured', event='payment.captured'):
        body = json.dumps({'event':event,'payload':{'payment':{'entity':{
          'id':'pay_verified_123','order_id':'order_verified_123',
          'status':status,'amount':amount,'currency':'INR'}}}}).encode()
        sig = hmac.new(b'webhook-test-only',body,hashlib.sha256).hexdigest()
        return body,sig

    def test_signed_webhook_captures_payment_once(self):
        body,sig = self._webhook()
        self.assertEqual(receive_razorpay_webhook(body,sig,'evt_1'),'paid')
        self.assertEqual(receive_razorpay_webhook(body,sig,'evt_1'),'duplicate')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,DomainOrder.PAID)
        self.assertEqual(PaymentEvent.objects.count(),1)

    def test_invalid_signature_cannot_pay(self):
        body,_ = self._webhook()
        with self.assertRaises(Exception):
            receive_razorpay_webhook(body,'wrong','evt_bad')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,DomainOrder.AWAITING)

    def test_amount_mismatch_not_paid(self):
        body,sig = self._webhook(amount=100)
        self.assertEqual(receive_razorpay_webhook(body,sig,'evt_2'),'unmatched_payment_review')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,DomainOrder.AWAITING)

    def test_missing_razorpay_order_id_never_matches_null_order(self):
        unrelated = DomainOrder.objects.create(owner=self.user, domain='another.com',
            operation=DomainOrder.REGISTER, amount_paise=129900, idempotency_key='unrelated')
        body = json.dumps({'event':'payment.captured','payload':{'payment':{'entity':{
          'id':'pay_verified_999','status':'captured','amount':129900,'currency':'INR'}}}}).encode()
        sig = hmac.new(b'webhook-test-only',body,hashlib.sha256).hexdigest()
        with self.assertRaises(OrderError):
            receive_razorpay_webhook(body,sig,'evt_no_order')
        unrelated.refresh_from_db()
        self.assertEqual(unrelated.status,DomainOrder.AWAITING)

    def test_nameserver_page_denies_other_account(self):
        domain = ManagedDomain.objects.create(owner=self.user,name='private.com', provider_id=9988, status='active')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('nameservers',args=[domain.pk])).status_code,404)

    def test_paid_order_fulfilled_and_not_fulfilled_twice(self):
        self.order.status = DomainOrder.PAID
        self.order.save()
        class Registrar:
            calls=0
            def create_contact(inner,payload): return 'BP123-IN'
            def register(inner,domain,handle):
                inner.calls += 1
                return {'id':100500,'status':'ACT','expiration_date':'2028-12-30 00:00:00'}
            def get_domain(inner,provider_id):
                return {'id':provider_id,'domain':{'name':'safeexample','extension':'com'},
                        'owner_handle':'BP123-IN','status':'ACT','expiration_date':'2028-12-30 00:00:00'}
        registrar = Registrar()
        self.assertTrue(fulfill_one(self.order.id,registrar))
        self.assertFalse(fulfill_one(self.order.id,registrar))
        self.assertEqual(registrar.calls,1)
        self.assertEqual(ManagedDomain.objects.get(name='safeexample.com').owner,self.user)

    def test_uncertain_registrar_call_needs_review(self):
        self.order.status=DomainOrder.PAID
        self.order.save()
        class Registrar:
            def create_contact(inner,payload): return 'BP123-IN'
            def register(inner,domain,handle): raise ProviderError('unknown')
        self.assertFalse(fulfill_one(self.order.pk,Registrar()))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,DomainOrder.REVIEW)

    def test_ownership_enforced_on_order_pages(self):
        self.client.force_login(self.other)
        response=self.client.get(reverse('order_detail',args=[self.order.id]))
        self.assertEqual(response.status_code,404)

    def test_payment_gateway_order_is_server_priced(self):
        self.order.delete()
        with patch('shop.services.Razorpay') as gateway:
            gateway.return_value.create_order.return_value={
              'id':'order_new_100','amount':129900,'currency':'INR'}
            result=create_checkout_order(owner=self.user, domain='safeexample.com',
              operation=DomainOrder.REGISTER,price=129900,key='brand-new')
        self.assertEqual(result.amount_paise,129900)
        self.assertEqual(result.razorpay_order_id,'order_new_100')
        with patch('shop.services.Razorpay') as second_gateway:
            repeat=create_checkout_order(owner=self.user, domain='safeexample.com',
              operation=DomainOrder.REGISTER,price=129900,key='brand-new')
            second_gateway.assert_not_called()
        self.assertEqual(repeat.pk, result.pk)
