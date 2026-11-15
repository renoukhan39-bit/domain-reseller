"""Real Openprovider API adapter. Test doubles live only in tests."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from urllib.parse import urlsplit
import requests
from django.conf import settings
from django.core.cache import cache


class ProviderError(Exception):
    pass


def provider_environment(base_url):
    """Recognize only the documented HTTPS API origins, never substring matches."""
    if not isinstance(base_url, str) or any(c.isspace() for c in base_url):
        return None
    try:
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443) or "?" in base_url or "#" in base_url
                or parsed.path not in ("/v1", "/v1/", "/v1beta", "/v1beta/")):
            return None
        return {"api.sandbox.openprovider.nl": "sandbox", "api.openprovider.eu": "live"}.get(parsed.hostname)
    except ValueError:
        return None


def _provider_id(value):
    if type(value) is not int or not 0 < value <= 9223372036854775807:
        raise ProviderError("Invalid registrar domain identifier")
    return value


def _domain_parts(domain):
    if not isinstance(domain, str) or len(domain) > 253:
        raise ProviderError("Invalid registrar domain")
    labels = domain.split(".")
    if len(labels) != 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in labels):
        raise ProviderError("Invalid registrar domain")
    return labels


def _response_data(response):
    response.raise_for_status()
    if not 200 <= response.status_code < 300:
        raise ProviderError("Registrar returned an unexpected HTTP response")
    envelope = response.json()
    if (not isinstance(envelope, dict) or type(envelope.get("code")) is not int
            or envelope["code"] != 0 or not isinstance(envelope.get("data"), dict)
            or ("maintenance" in envelope and envelope["maintenance"] is not False)):
        raise ProviderError("Registrar response is unavailable or malformed")
    return envelope["data"]


def _valid_token(token):
    return (isinstance(token, str) and token.isascii() and 0 < len(token) <= 8192
            and not any(c.isspace() for c in token))


class Openprovider:
    def __init__(self, session=None):
        self.session = session or requests.Session()
        if provider_environment(settings.OPENPROVIDER_BASE_URL) is None:
            raise ProviderError("OPENPROVIDER_BASE_URL must be a documented HTTPS API endpoint")
        self.base = settings.OPENPROVIDER_BASE_URL.rstrip("/")
        if not settings.OPENPROVIDER_USERNAME or not settings.OPENPROVIDER_PASSWORD:
            raise ProviderError("Openprovider credentials are missing")

    def _token(self):
        cache_key = "openprovider-token-" + sha256(f"{self.base}:{settings.OPENPROVIDER_USERNAME}".encode()).hexdigest()
        token = cache.get(cache_key)
        if _valid_token(token):
            return token
        try:
            response = self.session.post(self.base + "/auth/login", json={
                "username": settings.OPENPROVIDER_USERNAME,
                "password": settings.OPENPROVIDER_PASSWORD,
                "ip": "0.0.0.0",
            }, timeout=15, allow_redirects=False)
            token = _response_data(response).get("token")
            if not _valid_token(token):
                raise ProviderError("Registrar authentication response is malformed")
        except (requests.RequestException, ValueError, TypeError, ProviderError) as exc:
            raise ProviderError("Openprovider authentication failed") from exc
        cache.set(cache_key, token, timeout=2400)
        return token

    def _request(self, method, path, payload=None):
        try:
            response = self.session.request(method, self.base + path,
                headers={"Authorization": f"Bearer {self._token()}"},
                json=payload, timeout=25, allow_redirects=False)
            return _response_data(response)
        except (requests.RequestException, ValueError, TypeError, ProviderError) as exc:
            raise ProviderError("Openprovider request failed; reconcile externally before retry") from exc

    def check(self, domain):
        name, extension = _domain_parts(domain)
        data = self._request("POST", "/domains/check", {
            "domains": [{"name": name, "extension": extension}], "with_price": False,
        })
        if not isinstance(data, dict):
            raise ProviderError("Availability result is malformed")
        results = data.get("results")
        if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
            raise ProviderError("Availability result is missing")
        result = results[0]
        if result.get("domain") != domain:
            raise ProviderError("Availability result does not match requested domain")
        # Never interpret unknown statuses as available.
        status = result.get("status")
        if not isinstance(status, str):
            raise ProviderError("Unrecognized registrar availability response")
        status = status.lower()
        if status not in {"free", "reserved", "in use", "active", "taken", "unavailable"}:
            raise ProviderError("Unrecognized registrar availability response")
        if result.get("is_premium") is not False:
            raise ProviderError("Premium domain requires manual pricing and cannot use fixed checkout")
        # The official ordinary-domain example includes a nonempty premium object
        # with create=0. Reject contradictory/nonzero or malformed price metadata.
        premium = result.get("premium")
        if premium is not None:
            if (not isinstance(premium, dict) or not isinstance(premium.get("price"), dict)
                    or "create" not in premium["price"] or isinstance(premium["price"]["create"], bool)):
                raise ProviderError("Premium pricing is ambiguous; manual review required")
            try:
                create_price = Decimal(str(premium["price"]["create"]))
            except (InvalidOperation, ValueError):
                raise ProviderError("Premium pricing is ambiguous; manual review required") from None
            if not create_price.is_finite() or create_price != 0:
                raise ProviderError("Premium pricing requires manual review")
        return status == "free"

    def create_contact(self, payload):
        data = self._request("POST", "/customers", payload)
        handle = data.get("handle") if isinstance(data, dict) else None
        if not isinstance(handle, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,60}", handle):
            raise ProviderError("Registrar did not return contact handle")
        return handle

    def register(self, domain, owner_handle):
        name, extension = _domain_parts(domain)
        if not isinstance(owner_handle, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,60}", owner_handle):
            raise ProviderError("Invalid registrar owner handle")
        admin = settings.OPENPROVIDER_CONTACT_ADMIN or owner_handle
        tech = settings.OPENPROVIDER_CONTACT_TECH or owner_handle
        data = self._request("POST", "/domains", {
            "domain": {"name": name, "extension": extension}, "period": 1,
            "owner_handle": owner_handle, "admin_handle": admin,
            "tech_handle": tech, "billing_handle": admin,
            "ns_group": settings.OPENPROVIDER_NS_GROUP, "autorenew": "off",
        })
        if not isinstance(data, dict):
            raise ProviderError("Registrar did not return a domain ID; reconcile before retry")
        _provider_id(data.get("id"))
        return data

    def renew(self, provider_id):
        return self._request("POST", f"/domains/{_provider_id(provider_id)}/renew", {"period": 1})

    def update_nameservers(self, provider_id, servers):
        if (not isinstance(servers, list) or not 2 <= len(servers) <= 4
                or any(not isinstance(server, str) or len(server) > 253 or len(server.split(".")) < 2
                       or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                              for label in server.split(".")) for server in servers)
                or len(set(servers)) != len(servers)):
            raise ProviderError("Invalid registrar nameservers")
        return self._request("PUT", f"/domains/{_provider_id(provider_id)}", {
            "name_servers": [{"name": s} for s in servers], "remove_nses": True,
        })

    def get_domain(self, provider_id):
        return self._request("GET", f"/domains/{_provider_id(provider_id)}")


def parse_expiry(value):
    if not isinstance(value, str) or not value:
        return None
    # Openprovider commonly returns UTC timestamps with a space separator.
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except (ValueError, TypeError):
        return None
