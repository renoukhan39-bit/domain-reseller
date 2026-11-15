import re
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import RegistrantContact

LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


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
