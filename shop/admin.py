from django.contrib import admin
from .models import TLDPrice, RegistrantContact, ManagedDomain, DomainOrder, PaymentEvent, AuditEntry

@admin.register(TLDPrice)
class TLDPriceAdmin(admin.ModelAdmin):
    list_display = ("extension", "registration_paise", "renewal_paise", "enabled")
    list_editable = ("registration_paise", "renewal_paise", "enabled")
    search_fields = ("extension",)

@admin.register(RegistrantContact)
class RegistrantContactAdmin(admin.ModelAdmin):
    list_display = ("owner", "email", "country", "openprovider_handle")
    search_fields = ("email", "owner__username")
    readonly_fields = ("openprovider_handle", "updated_at")

@admin.register(ManagedDomain)
class ManagedDomainAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "status", "expires_at", "provider_id")
    search_fields = ("name", "owner__username")
    readonly_fields = ("owner", "name", "provider_id", "created_at")

@admin.register(DomainOrder)
class DomainOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "domain", "owner", "operation", "amount_paise", "status", "created_at")
    list_filter = ("status", "operation")
    search_fields = ("domain", "razorpay_order_id", "razorpay_payment_id")
    readonly_fields = [f.name for f in DomainOrder._meta.fields]
    actions = []

    def has_add_permission(self, request):
        return False

@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "outcome", "received_at")
    readonly_fields = [f.name for f in PaymentEvent._meta.fields]
    def has_add_permission(self, request):
        return False

@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "order", "domain")
    readonly_fields = [f.name for f in AuditEntry._meta.fields]
    def has_add_permission(self, request):
        return False
