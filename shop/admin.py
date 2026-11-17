from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db import IntegrityError, router, transaction
from django.http import HttpResponseRedirect

from shop.accounts.identity import email_users
from shop.forms import ChangeUserAdminForm, SignupUserAdminForm
from shop.models import TLDPrice, RegistrantContact, ManagedDomain, DomainOrder, PaymentEvent, AuditEntry


class EvidenceAdmin(admin.ModelAdmin):
    """External identities and financial history are changed through guarded services."""
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (*self.readonly_fields, "owner")
        return self.readonly_fields

    def has_change_permission(self, request, obj=None):
        if obj and obj.openprovider_handle:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method == "POST" and object_id:
            # Fetch the bound form only after serializing with registrar handle
            # creation. The outer transaction retains these locks through save.
            database = router.db_for_write(self.model)
            with transaction.atomic(using=database):
                contact = self.get_object(request, unquote(object_id))
                if contact:
                    get_user_model().objects.using(database).select_for_update().get(pk=contact.owner_id)
                    self.model.objects.using(database).select_for_update().get(pk=contact.pk)
                return super().changeform_view(request, object_id, form_url, extra_context)
        return super().changeform_view(request, object_id, form_url, extra_context)


@admin.register(ManagedDomain)
class ManagedDomainAdmin(EvidenceAdmin):
    list_display = ("name", "owner", "status", "expires_at", "provider_id")
    search_fields = ("name", "owner__username")
    readonly_fields = [field.name for field in ManagedDomain._meta.fields]


@admin.register(DomainOrder)
class DomainOrderAdmin(EvidenceAdmin):
    list_display = ("id", "domain", "owner", "operation", "amount_paise", "status", "created_at")
    list_filter = ("status", "operation")
    search_fields = ("domain", "razorpay_order_id", "razorpay_payment_id")
    readonly_fields = [f.name for f in DomainOrder._meta.fields]


@admin.register(PaymentEvent)
class PaymentEventAdmin(EvidenceAdmin):
    list_display = ("event_id", "event_type", "outcome", "received_at")
    readonly_fields = [f.name for f in PaymentEvent._meta.fields]


@admin.register(AuditEntry)
class AuditEntryAdmin(EvidenceAdmin):
    list_display = ("created_at", "actor", "action", "order", "domain")
    readonly_fields = [f.name for f in AuditEntry._meta.fields]


class CustomerUserAdmin(UserAdmin):
    add_form = SignupUserAdminForm
    form = ChangeUserAdminForm
    add_fieldsets = UserAdmin.add_fieldsets + (("Email", {"fields": ("email",)}),)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method != "POST":
            return super().changeform_view(request, object_id, form_url, extra_context)
        database = router.db_for_write(self.model)
        try:
            with transaction.atomic(using=database):
                return super().changeform_view(request, object_id, form_url, extra_context)
        except IntegrityError as error:
            # PostgreSQL reports the exact conflicting index. All admin writes
            # have rolled back before checking the competing account.
            diagnosis = getattr(error.__cause__, "diag", None)
            if getattr(diagnosis, "constraint_name", None) != "unique_normalized_user_email":
                raise
            email = request.POST.get("email", "")
            matches = email_users(email).using(database)
            if object_id:
                matches = matches.exclude(pk=unquote(object_id))
            if not email.strip() or not matches.exists():
                raise
            self.message_user(request, "Email already in use. Reload the account and try again.", messages.ERROR)
            return HttpResponseRedirect(request.path)

    def get_deleted_objects(self, objs, request):
        deleted_objects, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        if AuditEntry.objects.filter(actor__in=objs).exists():
            protected.append("Audit entries retain references to these accounts.")
        return deleted_objects, model_count, perms_needed, protected


admin.site.unregister(get_user_model())
admin.site.register(get_user_model(), CustomerUserAdmin)
