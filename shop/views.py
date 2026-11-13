"""Server-rendered customer interface; all state-changing operations use POST/CSRF."""
import json
import secrets
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.decorators.cache import never_cache
from django.db import transaction
from .email_verification import RESEND_MESSAGE, consume_verification, request_verification, verification_pending
from .forms import DomainSearchForm, NameServerForm, RegistrantForm, ResendVerificationForm, SignupForm, normalize_domain
from .models import AuditEntry, DomainOrder, EmailVerification, ManagedDomain, RegistrantContact, TLDPrice
from .providers import Openprovider, ProviderError
from .services import OrderError, create_checkout_order, receive_razorpay_webhook, sales_ready


def rate_limited(request, key_prefix, limit=12):
    """Best-effort app limit; deploy with shared Redis cache and edge throttling in production."""
    from django.core.cache import cache
    # Use authenticated user identity, not attacker-controlled forwarded IP headers.
    actor = str(request.user.pk) if request.user.is_authenticated else request.META.get("REMOTE_ADDR", "unknown")
    key = f"throttle:{key_prefix}:{actor}"
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, 60)
    return False


@require_GET
def home(request):
    form = DomainSearchForm(request.GET or None)
    found = None
    if "domain" in request.GET and form.is_valid():
        domain = form.cleaned_data["domain"]
        extension = domain.rsplit(".", 1)[1]
        tld = TLDPrice.objects.filter(extension=extension, enabled=True).first()
        if not tld:
            messages.error(request, "This extension is not currently supported")
        elif rate_limited(request, "availability", 20):
            messages.error(request, "Too many searches; try again shortly")
        else:
            try:
                available = Openprovider().check(domain)
                found = {"domain": domain, "available": available, "price": tld.registration_paise,
                         "checkout_key": secrets.token_hex(24)}
            except ProviderError:
                messages.error(request, "Registrar search temporarily unavailable; no availability claim made")
    return render(request, "shop/home.html", {"form": form, "found": found, "sales_enabled": sales_ready()})


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST" and rate_limited(request, "signup", 5):
        return HttpResponse("Please try again in a minute", status=429)
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            EmailVerification.objects.create(user=user)
        request_verification(user.email, request.META.get("REMOTE_ADDR", "unknown"))
        messages.success(request, "Account created. Check your email to activate it.")
        return redirect("login")
    return render(request, "shop/signup.html", {"form": form})


@never_cache
@require_http_methods(["GET", "POST"])
def resend_verification(request):
    form = ResendVerificationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        request_verification(form.cleaned_data["email"], request.META.get("REMOTE_ADDR", "unknown"))
        return redirect("resend_verification_done")
    return render(request, "registration/resend_verification.html", {"form": form})


@never_cache
@require_GET
def resend_verification_done(request):
    return render(request, "registration/resend_verification_done.html", {"notice": RESEND_MESSAGE})


@never_cache
@require_http_methods(["GET", "POST"])
def verify_email(request, token):
    if request.method == "GET" and verification_pending(token):
        response = render(request, "registration/verification_confirm.html")
    elif request.method == "POST" and consume_verification(token):
        messages.success(request, "Email verified. Sign in to complete your registrant profile.")
        response = redirect("login")
    else:
        response = render(request, "registration/verification_invalid.html", status=400)
    response["Referrer-Policy"] = "no-referrer"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def contact(request):
    existing = RegistrantContact.objects.filter(owner=request.user).first()
    # Registry owner handle may already exist: mutations require correct API synchronization.
    if existing and existing.openprovider_handle:
        return render(request, "shop/contact_locked.html", {"contact": existing})
    form = RegistrantForm(request.POST or None, instance=existing)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.owner = request.user
        record.save()
        messages.success(request, "Registrant details saved")
        return redirect("dashboard")
    return render(request, "shop/contact.html", {"form": form})


@login_required
@require_GET
def dashboard(request):
    return render(request, "shop/dashboard.html", {
        "domains": ManagedDomain.objects.filter(owner=request.user).order_by("name"),
        "orders": DomainOrder.objects.filter(owner=request.user)[:30],
        "has_contact": RegistrantContact.objects.filter(owner=request.user).exists(),
    })


@login_required
@require_POST
def buy(request, domain):
    if rate_limited(request, "purchase", 8):
        return HttpResponse("Please try again shortly", status=429)
    try:
        domain = normalize_domain(domain)
    except Exception:
        raise Http404()
    tld = TLDPrice.objects.filter(extension=domain.rsplit(".", 1)[1], enabled=True).first()
    if not tld:
        raise Http404()
    if not sales_ready():
        messages.error(request, "Sales are currently disabled")
        return redirect("home")
    try:
        if not Openprovider().check(domain):
            raise OrderError("Domain is no longer available")
        order = create_checkout_order(owner=request.user, domain=domain, operation=DomainOrder.REGISTER,
            price=tld.registration_paise, key=request.POST.get("idempotency_key", ""))
        return redirect("order_detail", order_id=order.pk)
    except (ProviderError, OrderError) as exc:
        messages.error(request, str(exc))
        return redirect("home")


@login_required
@require_POST
def renew(request, domain_id):
    if rate_limited(request, "renew", 8):
        return HttpResponse("Please try again shortly", status=429)
    domain = get_object_or_404(ManagedDomain, id=domain_id, owner=request.user)
    if domain.status != "active":
        messages.error(request, "Contact support to renew a non-active domain")
        return redirect("dashboard")
    tld = TLDPrice.objects.filter(extension=domain.name.rsplit(".", 1)[1], enabled=True).first()
    if not tld:
        messages.error(request, "This extension is not currently offered")
        return redirect("dashboard")
    try:
        order = create_checkout_order(owner=request.user, domain=domain.name, operation=DomainOrder.RENEW,
            price=tld.renewal_paise, key=request.POST.get("idempotency_key", ""), managed_domain=domain)
        return redirect("order_detail", order_id=order.pk)
    except OrderError as exc:
        messages.error(request, str(exc))
        return redirect("dashboard")


@login_required
@require_GET
def order_detail(request, order_id):
    order = get_object_or_404(DomainOrder, pk=order_id, owner=request.user)
    return render(request, "shop/order.html", {
        "order": order, "key_id": settings.RAZORPAY_KEY_ID, "checkout_enabled": sales_ready(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def nameservers(request, domain_id):
    domain = get_object_or_404(ManagedDomain, id=domain_id, owner=request.user)
    if domain.status != "active":
        raise Http404()
    form = NameServerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not settings.FULFILLMENT_ENABLED:
            messages.error(request, "Registrar management is currently disabled")
        elif rate_limited(request, "nameservers", 5):
            return HttpResponse("Please try again shortly", status=429)
        else:
            try:
                Openprovider().update_nameservers(domain.provider_id, form.cleaned_data["nameservers"])
                AuditEntry.objects.create(actor=request.user, domain=domain, action="nameservers_changed")
                messages.success(request, "Nameserver update sent to registrar")
                return redirect("dashboard")
            except ProviderError:
                messages.error(request, "Update uncertain; check registrar status before retry")
    return render(request, "shop/nameservers.html", {"domain": domain, "form": form})


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return HttpResponse("Unavailable", status=503)
    if len(request.body) > 128 * 1024:
        return HttpResponse("Request too large", status=413)
    try:
        receive_razorpay_webhook(request.body,
            request.headers.get("X-Razorpay-Signature", ""),
            request.headers.get("X-Razorpay-Event-Id", ""))
    except OrderError:
        return HttpResponse("Invalid webhook", status=400)
    return HttpResponse("OK", status=200)


@require_GET
def health(request):
    from django.db import connection
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        return HttpResponse("unhealthy", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
