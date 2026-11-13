"""Real Openprovider API adapter. Test doubles live only in tests."""
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlparse
import requests
from django.conf import settings
from django.core.cache import cache


class ProviderError(Exception):
    pass


class Openprovider:
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.base = settings.OPENPROVIDER_BASE_URL
        parsed = urlparse(self.base)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username:
            raise ProviderError("OPENPROVIDER_BASE_URL must be an HTTPS API endpoint")
        if not settings.OPENPROVIDER_USERNAME or not settings.OPENPROVIDER_PASSWORD:
            raise ProviderError("Openprovider credentials are missing")

    def _token(self):
        cache_key = "openprovider-token-" + sha256(f"{self.base}:{settings.OPENPROVIDER_USERNAME}".encode()).hexdigest()
        token = cache.get(cache_key)
        if token:
            return token
        try:
            response = self.session.post(self.base + "/auth/login", json={
                "username": settings.OPENPROVIDER_USERNAME,
                "password": settings.OPENPROVIDER_PASSWORD,
                "ip": "0.0.0.0",
            }, timeout=15)
            response.raise_for_status()
            token = response.json()["data"]["token"]
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Openprovider authentication failed") from exc
        cache.set(cache_key, token, timeout=2400)
        return token

    def _request(self, method, path, payload=None):
        try:
            response = self.session.request(method, self.base + path,
                headers={"Authorization": f"Bearer {self._token()}"},
                json=payload, timeout=25)
            response.raise_for_status()
            data = response.json()
            if data.get("code", 0) != 0:
                raise ProviderError(f"Openprovider reported code {data.get('code')}")
            return data.get("data", {})
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Openprovider request failed; reconcile externally before retry") from exc

    def check(self, domain):
        name, extension = domain.split(".", 1)
        data = self._request("POST", "/domains/check", {
            "domains": [{"name": name, "extension": extension}], "with_price": False,
        })
        results = data.get("results", [])
        if not results:
            raise ProviderError("Availability result is missing")
        result = results[0]
        # Never interpret unknown statuses as available.
        status = str(result.get("status", "")).lower()
        if status not in {"free", "reserved", "in use", "active", "taken", "unavailable"}:
            raise ProviderError("Unrecognized registrar availability response")
        if result.get("is_premium") or result.get("premium"):
            raise ProviderError("Premium domain requires manual pricing and cannot use fixed checkout")
        return status == "free"

    def create_contact(self, payload):
        data = self._request("POST", "/customers", payload)
        handle = data.get("handle")
        if not handle:
            raise ProviderError("Registrar did not return contact handle")
        return handle

    def register(self, domain, owner_handle):
        name, extension = domain.split(".", 1)
        admin = settings.OPENPROVIDER_CONTACT_ADMIN or owner_handle
        tech = settings.OPENPROVIDER_CONTACT_TECH or owner_handle
        data = self._request("POST", "/domains", {
            "domain": {"name": name, "extension": extension}, "period": 1,
            "owner_handle": owner_handle, "admin_handle": admin,
            "tech_handle": tech, "billing_handle": admin,
            "ns_group": settings.OPENPROVIDER_NS_GROUP, "autorenew": "off",
        })
        if not data.get("id"):
            raise ProviderError("Registrar did not return a domain ID; reconcile before retry")
        return data

    def renew(self, provider_id):
        return self._request("POST", f"/domains/{int(provider_id)}/renew", {"period": 1})

    def update_nameservers(self, provider_id, servers):
        return self._request("PUT", f"/domains/{int(provider_id)}", {
            "name_servers": [{"name": s} for s in servers], "remove_nses": True,
        })

    def get_domain(self, provider_id):
        return self._request("GET", f"/domains/{int(provider_id)}")


def parse_expiry(value):
    if not value:
        return None
    # Openprovider commonly returns UTC timestamps with a space separator.
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except (ValueError, TypeError):
        return None
