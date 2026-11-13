"""Authoritative server-side state for domains, orders and payment events."""
import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

DOMAIN_LABEL = RegexValidator(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", "Use valid ASCII domain labels")


class TLDPrice(models.Model):
    extension = models.CharField(max_length=63, unique=True, validators=[DOMAIN_LABEL])
    registration_paise = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    renewal_paise = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f".{self.extension} (INR)"


class RegistrantContact(models.Model):
    """Person or business who legally owns registered domains; never substitute a reseller handle."""
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    company_name = models.CharField(max_length=160, blank=True)
    email = models.EmailField()
    phone_country_code = models.CharField(max_length=8, default="+91")
    phone_area_code = models.CharField(max_length=10)
    phone_subscriber_number = models.CharField(max_length=20)
    street = models.CharField(max_length=150)
    street_number = models.CharField(max_length=25)
    city = models.CharField(max_length=90)
    state = models.CharField(max_length=90)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default="IN")
    openprovider_handle = models.CharField(max_length=60, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def provider_payload(self):
        return {
            "name": {"first_name": self.first_name, "last_name": self.last_name},
            "company_name": self.company_name,
            "email": self.email,
            "phone": {"country_code": self.phone_country_code,
                      "area_code": self.phone_area_code,
                      "subscriber_number": self.phone_subscriber_number},
            "address": {"street": self.street, "number": self.street_number,
                        "city": self.city, "state": self.state, "zipcode": self.postal_code,
                        "country": self.country.upper()},
        }


class ManagedDomain(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="domains")
    name = models.CharField(max_length=253, unique=True)
    provider_id = models.BigIntegerField(unique=True)
    status = models.CharField(max_length=20, default="pending")
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class DomainOrder(models.Model):
    REGISTER = "register"
    RENEW = "renew"
    OPERATION_CHOICES = [(REGISTER, "Registration"), (RENEW, "Renewal")]
    AWAITING = "awaiting_payment"
    PAID = "paid"
    PROCESSING = "processing"
    ACTIVE = "active"
    REVIEW = "needs_review"
    REFUNDED = "refunded"
    STATUS_CHOICES = [(x, x.replace("_", " ").title()) for x in
                      (AWAITING, PAID, PROCESSING, ACTIVE, REVIEW, REFUNDED)]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    domain = models.CharField(max_length=253)
    operation = models.CharField(max_length=12, choices=OPERATION_CHOICES)
    amount_paise = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=AWAITING)
    idempotency_key = models.CharField(max_length=64)
    razorpay_order_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    managed_domain = models.ForeignKey(ManagedDomain, null=True, blank=True, on_delete=models.PROTECT)
    provider_result_id = models.BigIntegerField(null=True, blank=True)
    provider_message = models.TextField(blank=True)
    refund_id = models.CharField(max_length=80, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "idempotency_key"], name="unique_order_request_per_user"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.operation} {self.domain} [{self.status}]"


class PaymentEvent(models.Model):
    event_id = models.CharField(max_length=130, unique=True)
    event_type = models.CharField(max_length=60)
    payload_sha256 = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=80, blank=True)


class AuditEntry(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=80)
    order = models.ForeignKey(DomainOrder, on_delete=models.SET_NULL, null=True, blank=True)
    domain = models.ForeignKey(ManagedDomain, on_delete=models.SET_NULL, null=True, blank=True)
    detail = models.CharField(max_length=240, blank=True)
