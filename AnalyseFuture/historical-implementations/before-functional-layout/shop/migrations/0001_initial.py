# Initial schema for independently deployable domain reseller backend.
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='TLDPrice', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('extension', models.CharField(max_length=63, unique=True, validators=[django.core.validators.RegexValidator('^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$', 'Use valid ASCII domain labels')])),
            ('registration_paise', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
            ('renewal_paise', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
            ('enabled', models.BooleanField(default=False)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name='RegistrantContact', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('first_name', models.CharField(max_length=80)),
            ('last_name', models.CharField(max_length=80)),
            ('company_name', models.CharField(blank=True, max_length=160)),
            ('email', models.EmailField(max_length=254)),
            ('phone_country_code', models.CharField(default='+91', max_length=8)),
            ('phone_area_code', models.CharField(max_length=10)),
            ('phone_subscriber_number', models.CharField(max_length=20)),
            ('street', models.CharField(max_length=150)),
            ('street_number', models.CharField(max_length=25)),
            ('city', models.CharField(max_length=90)),
            ('state', models.CharField(max_length=90)),
            ('postal_code', models.CharField(max_length=20)),
            ('country', models.CharField(default='IN', max_length=2)),
            ('openprovider_handle', models.CharField(blank=True, max_length=60)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('owner', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='ManagedDomain', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=253, unique=True)),
            ('provider_id', models.BigIntegerField(unique=True)),
            ('status', models.CharField(default='pending', max_length=20)),
            ('expires_at', models.DateTimeField(blank=True, null=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='domains', to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='DomainOrder', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('domain', models.CharField(max_length=253)),
            ('operation', models.CharField(choices=[('register', 'Registration'), ('renew', 'Renewal')], max_length=12)),
            ('amount_paise', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
            ('currency', models.CharField(default='INR', max_length=3)),
            ('status', models.CharField(choices=[('awaiting_payment','Awaiting Payment'),('paid','Paid'),('processing','Processing'),('active','Active'),('needs_review','Needs Review'),('refunded','Refunded')], default='awaiting_payment', max_length=20)),
            ('idempotency_key', models.CharField(max_length=64)),
            ('razorpay_order_id', models.CharField(blank=True, max_length=80, null=True, unique=True)),
            ('razorpay_payment_id', models.CharField(blank=True, max_length=80, null=True, unique=True)),
            ('provider_result_id', models.BigIntegerField(blank=True, null=True)),
            ('provider_message', models.TextField(blank=True)),
            ('refund_id', models.CharField(blank=True, max_length=80, null=True, unique=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('managed_domain', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='shop.manageddomain')),
            ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orders', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering':['-created_at']}),
        migrations.CreateModel(name='PaymentEvent', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('event_id', models.CharField(max_length=130, unique=True)),
            ('event_type', models.CharField(max_length=60)),
            ('payload_sha256', models.CharField(max_length=64)),
            ('received_at', models.DateTimeField(auto_now_add=True)),
            ('processed_at', models.DateTimeField(blank=True, null=True)),
            ('outcome', models.CharField(blank=True, max_length=80)),
        ]),
        migrations.CreateModel(name='AuditEntry', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('action', models.CharField(max_length=80)),
            ('detail', models.CharField(blank=True, max_length=240)),
            ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='shop.domainorder')),
            ('domain', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='shop.manageddomain')),
        ]),
        migrations.AddConstraint(model_name='domainorder', constraint=models.UniqueConstraint(fields=('owner', 'idempotency_key'), name='unique_order_request_per_user')),
    ]
