import re
import logging
from smtplib import SMTPException
from urllib.parse import urlsplit
from django import forms
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist, TemplateSyntaxError, loader
from .models import RegistrantContact

LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
logger = logging.getLogger(__name__)


class SafePasswordResetForm(PasswordResetForm):
    """Keep Django's account/token rules, with a trusted origin and redacted failures."""
    def save(self, **kwargs):
        try:
            origin = settings.EMAIL_VERIFICATION_BASE_URL.rstrip("/")
            parsed = urlsplit(origin)
            safe = (parsed.scheme in ("http", "https") and parsed.hostname
                    and not any(c.isspace() for c in origin)
                    and not (parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path)
                    and (settings.DEBUG or parsed.scheme == "https"))
            parsed.port
        except (ValueError, AttributeError):
            safe = False
        if not safe:
            logger.warning("Password reset email origin is not configured safely")
            return
        kwargs["domain_override"] = parsed.netloc
        kwargs["use_https"] = parsed.scheme == "https"
        # A caller's extra context must not replace the trusted origin.
        extra = dict(kwargs.get("extra_email_context") or {})
        extra.update(domain=parsed.netloc, site_name=parsed.netloc, protocol=parsed.scheme)
        kwargs["extra_email_context"] = extra
        return super().save(**kwargs)

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        # Django's default form logs exception traces. SMTP failures can contain
        # credentials/recipient details, so keep this transport boundary redacted.
        try:
            subject = "".join(loader.render_to_string(subject_template_name, context).splitlines())
            message = EmailMultiAlternatives(subject, loader.render_to_string(email_template_name, context),
                                             from_email, [to_email])
            if html_email_template_name:
                message.attach_alternative(loader.render_to_string(html_email_template_name, context), "text/html")
            if not message.send():
                logger.warning("Password reset email delivery failed")
        except (SMTPException, OSError, ValueError, ImproperlyConfigured, TemplateDoesNotExist, TemplateSyntaxError):
            logger.warning("Password reset email delivery failed")


def normalize_domain(value):
    value = (value or "").strip().rstrip(".").lower()
    labels = value.split(".")
    # First release supports one-segment ASCII TLDs from an explicit allowlist.
    if len(labels) != 2 or any(not LABEL_RE.fullmatch(part) for part in labels) or len(value) > 253:
        raise forms.ValidationError("Enter a valid ASCII domain, for example example.com")
    return value


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email already in use")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = False
        if commit:
            user.save()
        return user


class ResendVerificationForm(forms.Form):
    email = forms.EmailField(max_length=254)


class DomainSearchForm(forms.Form):
    domain = forms.CharField(max_length=253)
    def clean_domain(self):
        return normalize_domain(self.cleaned_data["domain"])


class RegistrantForm(forms.ModelForm):
    class Meta:
        model = RegistrantContact
        exclude = ("owner", "openprovider_handle", "updated_at")

    def clean_country(self):
        value = self.cleaned_data["country"].strip().upper()
        if len(value) != 2 or not value.isalpha():
            raise forms.ValidationError("Use a two-letter ISO country code")
        return value


class NameServerForm(forms.Form):
    ns1 = forms.CharField(max_length=253)
    ns2 = forms.CharField(max_length=253)
    ns3 = forms.CharField(max_length=253, required=False)
    ns4 = forms.CharField(max_length=253, required=False)

    def clean(self):
        result = super().clean()
        servers = [result.get(f"ns{i}", "").strip().rstrip(".").lower() for i in range(1, 5)]
        for value in filter(None, servers):
            if len(value) > 253 or len(value.split(".")) < 2 or any(not LABEL_RE.fullmatch(x) for x in value.split(".")):
                raise forms.ValidationError("Enter valid nameserver hostnames")
        if len(set(filter(None, servers))) != len(list(filter(None, servers))):
            raise forms.ValidationError("Nameservers must be distinct")
        result["nameservers"] = list(filter(None, servers))
        return result
