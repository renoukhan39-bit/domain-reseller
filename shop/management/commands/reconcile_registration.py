from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from shop.exceptions import OrderError
from shop.models import AuditEntry, DomainOrder, ManagedDomain, RegistrantContact
from shop.providers import Openprovider, ProviderError, provider_environment
from shop.services import _registrar_identity


def eligible(order):
    return (order.operation == DomainOrder.REGISTER and order.status == DomainOrder.REVIEW
            and order.razorpay_payment_id and not order.refund_attempted_at and not order.refund_id)


class Command(BaseCommand):
    help = "Confirm an uncertain registration with a read-only registrar lookup; never retries purchase"

    def add_arguments(self, parser):
        parser.add_argument("order_id")
        parser.add_argument("--provider-id", type=int)
        parser.add_argument("--allow-live", action="store_true")

    def handle(self, *args, **options):
        environment = provider_environment(settings.OPENPROVIDER_BASE_URL)
        if environment is None or (environment == "live" and not options["allow_live"]):
            raise CommandError("Use sandbox or explicitly approve a read-only live lookup with --allow-live")
        try:
            order = DomainOrder.objects.get(pk=options["order_id"])
            contact = RegistrantContact.objects.get(owner=order.owner)
        except (DomainOrder.DoesNotExist, RegistrantContact.DoesNotExist, ValidationError, ValueError):
            raise CommandError("Unknown order or missing registrant") from None
        if order.status == DomainOrder.ACTIVE and order.managed_domain_id:
            self.stdout.write("Registration already reconciled; no registrar request sent")
            return
        provider_id = options["provider_id"] or order.provider_result_id
        if (not eligible(order) or not contact.openprovider_handle or type(provider_id) is not int
                or not 0 < provider_id <= 9223372036854775807
                or (order.provider_result_id and order.provider_result_id != provider_id)):
            raise CommandError("Order is not eligible or registrar identifier conflicts")
        try:
            details = Openprovider().get_domain(provider_id)
            status, expiry = _registrar_identity(details, provider_id, order.domain, contact.openprovider_handle)
        except (ProviderError, OrderError):
            raise CommandError("Registrar lookup is unverified; no state changed") from None
        if status != "ACT" or expiry is None:
            raise CommandError("Registrar completion remains unconfirmed")
        try:
            with transaction.atomic():
                current = DomainOrder.objects.select_for_update().get(pk=order.pk)
                current_contact = RegistrantContact.objects.select_for_update().get(owner=current.owner)
                if (not eligible(current) or current.owner_id != order.owner_id or current.domain != order.domain
                        or current_contact.openprovider_handle != contact.openprovider_handle
                        or (current.provider_result_id and current.provider_result_id != provider_id)):
                    raise CommandError("Order changed during reconciliation")
                domain, _ = ManagedDomain.objects.get_or_create(name=order.domain, defaults={
                    "owner_id": order.owner_id, "provider_id": provider_id, "expires_at": expiry, "status": "active"})
                if (domain.owner_id != current.owner_id or domain.provider_id != provider_id
                        or (current.managed_domain_id and current.managed_domain_id != domain.pk)):
                    raise CommandError("Local ownership or registrar identity collision")
                domain.status, domain.expires_at = "active", expiry
                domain.save(update_fields=["status", "expires_at", "updated_at"])
                current.managed_domain, current.provider_result_id, current.status = domain, provider_id, DomainOrder.ACTIVE
                current.save(update_fields=["managed_domain", "provider_result_id", "status", "updated_at"])
                AuditEntry.objects.create(order=current, domain=domain, action="registration_reconciled")
        except IntegrityError:
            raise CommandError("Registrar identity is already linked elsewhere") from None
        self.stdout.write("Registration confirmed by read-only lookup; no purchase retried")
