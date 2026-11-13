"""Offline Openprovider contract fixtures; no registrar account or paid calls."""
from datetime import timezone
from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from .providers import Openprovider, ProviderError, parse_expiry, provider_environment


PROVIDER_SETTINGS = {
    "OPENPROVIDER_BASE_URL": "https://api.sandbox.openprovider.nl/v1",
    "OPENPROVIDER_USERNAME": "local-fixture-user",
    "OPENPROVIDER_PASSWORD": "local-fixture-password",
    "OPENPROVIDER_CONTACT_ADMIN": "",
    "OPENPROVIDER_CONTACT_TECH": "",
}


def response(data, status=200):
    result = Mock()
    result.status_code = status
    result.json.return_value = data
    return result


@override_settings(**PROVIDER_SETTINGS)
class ProviderContractTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session = Mock()
        self.provider = Openprovider(self.session)

    def available(self, **extra):
        result = {"domain": "example.com", "status": "free", "is_premium": False}
        result.update(extra)
        return {"results": [result]}

    def test_environment_uses_exact_documented_origins_and_supported_api_paths(self):
        for host, expected in (("api.sandbox.openprovider.nl", "sandbox"), ("api.openprovider.eu", "live")):
            for suffix in ("/v1", "/v1/", ":443/v1", "/v1beta"):
                with self.subTest(host=host, suffix=suffix):
                    self.assertEqual(provider_environment(f"https://{host}{suffix}"), expected)

    def test_environment_rejects_spoofed_hosts_credentials_ports_and_url_components(self):
        invalid = (None, 1, [], "", "http://api.sandbox.openprovider.nl/v1",
                   "https://api.sandbox.openprovider.nl.attacker.test/v1",
                   "https://attacker.test/api.sandbox.openprovider.nl/v1",
                   "https://api.sandbox.openprovider.nl@attacker.test/v1",
                   "https://attacker.test@api.sandbox.openprovider.nl/v1",
                   "https://@api.sandbox.openprovider.nl/v1", "https://[",
                   "https://api.sandbox.openprovider.nl:444/v1",
                   "https://api.sandbox.openprovider.nl:bad/v1",
                   "https://api.sandbox.openprovider.nl:99999/v1",
                   "https://api.sandbox.openprovider.nl/v1?redirect=other",
                   "https://api.sandbox.openprovider.nl/v1#other",
                   "https://api.sandbox.openprovider.nl/v1?",
                   "https://api.sandbox.openprovider.nl/v1#",
                   "https://api.sandbox.openprovider.nl/v1/domains",
                   "https://api.sandbox.openprovider.nl/v1///",
                   "https://api.sandbox.openprovider.nl/v2",
                   "https://api.sandbox.openprovider.nl/v1\n")
        for base in invalid:
            with self.subTest(base=base):
                self.assertIsNone(provider_environment(base))
                with override_settings(OPENPROVIDER_BASE_URL=base):
                    with self.assertRaises(ProviderError):
                        Openprovider(self.session)
        self.session.assert_not_called()

    def test_missing_credentials_fail_before_network(self):
        with override_settings(OPENPROVIDER_PASSWORD=""):
            with self.assertRaises(ProviderError):
                Openprovider(self.session)
        self.session.request.assert_not_called()

    def test_token_http_request_preserves_tls_and_disables_redirects(self):
        self.session.post.return_value = response({"code": 0, "data": {"token": "fixture-token"}})
        self.assertEqual(self.provider._token(), "fixture-token")
        self.assertEqual(self.provider._token(), "fixture-token")
        self.session.post.assert_called_once_with(
            "https://api.sandbox.openprovider.nl/v1/auth/login",
            json={"username": "local-fixture-user", "password": "local-fixture-password", "ip": "0.0.0.0"},
            timeout=15, allow_redirects=False,
        )

    def test_authentication_rejects_malformed_envelopes_and_tokens(self):
        malformed = (None, [], "private-provider-error", {}, {"code": 0},
                     {"code": False, "data": {"token": "fixture-token"}},
                     {"code": "0", "data": {"token": "fixture-token"}},
                     {"code": 1, "data": {"token": "fixture-token"}},
                     {"code": 0, "data": []},
                     *({"code": 0, "data": {"token": token}} for token in
                       (None, "", 4, [], "bad\ntoken", "nonascii-λ", "x" * 8193)))
        for data in malformed:
            with self.subTest(data_type=type(data).__name__):
                self.session.post.return_value = response(data)
                with self.assertRaises(ProviderError) as caught:
                    self.provider._token()
                self.assertEqual(str(caught.exception), "Openprovider authentication failed")

    def test_authentication_rejects_redirect_and_network_uncertainty(self):
        for status in (301, 302, 307, 308):
            self.session.post.return_value = response({"code": 0, "data": {"token": "fixture-token"}}, status)
            with self.assertRaises(ProviderError):
                self.provider._token()
        self.session.post.side_effect = requests.Timeout("sensitive-provider-response")
        with self.assertRaises(ProviderError) as caught:
            self.provider._token()
        self.assertNotIn("sensitive", str(caught.exception))

    def test_request_uses_validated_bearer_without_following_redirects(self):
        self.session.request.return_value = response({"code": 0, "data": {"id": 42}})
        with patch.object(self.provider, "_token", return_value="fixture-token"):
            self.assertEqual(self.provider.get_domain(42), {"id": 42})
        self.session.request.assert_called_once_with(
            "GET", "https://api.sandbox.openprovider.nl/v1/domains/42",
            headers={"Authorization": "Bearer fixture-token"}, json=None, timeout=25, allow_redirects=False,
        )

    def test_request_rejects_malformed_envelopes_maintenance_and_redirects(self):
        malformed = (None, [], "private-provider-error", {}, {"data": {}},
                     {"code": False, "data": {}}, {"code": "0", "data": {}},
                     {"code": 1, "data": {}}, {"code": 0, "data": None},
                     {"code": 0, "data": []}, {"code": 0, "data": {}, "maintenance": True},
                     {"code": 0, "data": {}, "maintenance": "false"})
        with patch.object(self.provider, "_token", return_value="fixture-token"):
            for data in malformed:
                with self.subTest(data_type=type(data).__name__):
                    self.session.request.return_value = response(data)
                    with self.assertRaises(ProviderError) as caught:
                        self.provider.get_domain(42)
                    self.assertNotIn("private-provider", str(caught.exception))
            self.session.request.return_value = response({"code": 0, "data": {}}, 307)
            with self.assertRaises(ProviderError):
                self.provider.get_domain(42)

    def test_request_http_timeout_and_invalid_json_are_safe_errors_without_retry(self):
        with patch.object(self.provider, "_token", return_value="fixture-token"):
            self.session.request.side_effect = requests.Timeout("sensitive-response")
            with self.assertRaises(ProviderError) as caught:
                self.provider.renew(42)
            self.assertNotIn("sensitive", str(caught.exception))
            self.assertEqual(self.session.request.call_count, 1)
            self.session.request.side_effect = None
            self.session.request.return_value = response(None)
            self.session.request.return_value.json.side_effect = ValueError("private-json")
            with self.assertRaises(ProviderError):
                self.provider.get_domain(42)

    def test_ordinary_domain_accepts_official_zero_price_premium_object(self):
        # Official domainCheckDomainResponse example includes this nonempty object
        # even when is_premium=false. Status is free for the available fixture.
        data = self.available(premium={"currency": "USD", "price": {"create": 0}})
        with patch.object(self.provider, "_request", return_value=data) as request:
            self.assertTrue(self.provider.check("example.com"))
        request.assert_called_once_with("POST", "/domains/check", {
            "domains": [{"name": "example", "extension": "com"}], "with_price": False,
        })

    def test_nonavailable_known_statuses_never_become_available(self):
        for status in ("reserved", "in use", "active", "taken", "unavailable"):
            with self.subTest(status=status), patch.object(self.provider, "_request", return_value=self.available(status=status)):
                self.assertFalse(self.provider.check("example.com"))

    def test_premium_unknown_or_contradictory_pricing_always_requires_review(self):
        for marker in (True, None, 0, 1, "false", "true", [], {}):
            with self.subTest(marker=marker), patch.object(self.provider, "_request", return_value=self.available(is_premium=marker)):
                with self.assertRaises(ProviderError):
                    self.provider.check("example.com")
        for premium in (True, False, 0, [], {}, {"price": []}, {"price": {}},
                        *({"price": {"create": price}} for price in
                          (True, 1, -1, "1", "NaN", "Infinity", "invalid", None, []))):
            with self.subTest(premium=premium), patch.object(self.provider, "_request", return_value=self.available(premium=premium)):
                with self.assertRaises(ProviderError):
                    self.provider.check("example.com")

    def test_availability_rejects_wrong_domain_ambiguous_and_malformed_results(self):
        malformed = (None, [], {}, {"results": None}, {"results": {}}, {"results": []},
                     {"results": [None]}, {"results": [self.available()["results"][0]] * 2},
                     self.available(domain="another.com"), self.available(domain=None),
                     self.available(status="mystery"), self.available(status=[]),
                     {"results": [{"domain": "example.com", "status": "free"}]})
        for data in malformed:
            with self.subTest(data=data), patch.object(self.provider, "_request", return_value=data):
                with self.assertRaises(ProviderError):
                    self.provider.check("example.com")

    def test_invalid_domain_inputs_never_reach_registrar(self):
        for domain in (None, [], "", "EXAMPLE.com", "https://example.com", "a.b.com", "bad..com", "bad_.com"):
            with self.subTest(domain=domain), patch.object(self.provider, "_request") as request:
                with self.assertRaises(ProviderError):
                    self.provider.check(domain)
                request.assert_not_called()

    def test_registration_preserves_customer_owner_and_validates_returned_id(self):
        with patch.object(self.provider, "_request", return_value={"id": 42, "status": "ACT"}) as request:
            self.assertEqual(self.provider.register("example.com", "CP123-IN")["id"], 42)
        sent = request.call_args.args[2]
        self.assertEqual(sent["owner_handle"], "CP123-IN")
        self.assertEqual(sent["admin_handle"], "CP123-IN")
        self.assertEqual(sent["tech_handle"], "CP123-IN")
        self.assertEqual(sent["autorenew"], "off")
        for data in (None, [], {}, {"id": True}, {"id": "42"}, {"id": -1}, {"id": 0}):
            with self.subTest(data=data), patch.object(self.provider, "_request", return_value=data):
                with self.assertRaises(ProviderError):
                    self.provider.register("example.com", "CP123-IN")

    def test_invalid_contact_handles_are_not_persisted_or_submitted(self):
        for handle in (None, "", [], 42, "x" * 61, "bad/handle", "bad\nhandle"):
            with self.subTest(handle=handle), patch.object(self.provider, "_request", return_value={"handle": handle}) as request:
                with self.assertRaises(ProviderError):
                    self.provider.create_contact({})
                request.reset_mock()
                with self.assertRaises(ProviderError):
                    self.provider.register("example.com", handle)
                request.assert_not_called()

    def test_invalid_ids_cannot_be_coerced_into_other_domain_operations(self):
        for domain_id in (None, True, False, 0, -1, "42", "42/renew", 1.0, [], 2 ** 63):
            with self.subTest(domain_id=domain_id), patch.object(self.provider, "_request") as request:
                for method, args in ((self.provider.get_domain, (domain_id,)), (self.provider.renew, (domain_id,)),
                                     (self.provider.update_nameservers, (domain_id, ["ns1.example.com", "ns2.example.com"]))):
                    with self.assertRaises(ProviderError):
                        method(*args)
                request.assert_not_called()

    def test_nameserver_mutation_rejects_malformed_or_duplicate_hosts(self):
        for servers in (None, [], ["ns1.example.com"], ["ns1.example.com"] * 2,
                        [[], "ns2.example.com"], ["ns1.example.com", "bad_host"],
                        ["ns1.example.com", "https://ns2.example.com"]):
            with self.subTest(servers=servers), patch.object(self.provider, "_request") as request:
                with self.assertRaises(ProviderError):
                    self.provider.update_nameservers(42, servers)
                request.assert_not_called()
        with patch.object(self.provider, "_request", return_value={}) as request:
            self.provider.update_nameservers(42, ["ns1.example.com", "ns2.example.com"])
        self.assertEqual(request.call_args.args[2]["name_servers"], [{"name": "ns1.example.com"}, {"name": "ns2.example.com"}])

    def test_expiry_is_parsed_only_from_actual_valid_provider_dates(self):
        self.assertEqual(parse_expiry("2028-12-30 00:00:00").tzinfo, timezone.utc)
        self.assertEqual(parse_expiry("2028-12-30T00:00:00Z").year, 2028)
        self.assertEqual(parse_expiry("2028-12-30T02:00:00+02:00").utcoffset().total_seconds(), 7200)
        for value in (None, "", "invalid", "0000-00-00 00:00:00", [], {}, 2028):
            with self.subTest(value=value):
                self.assertIsNone(parse_expiry(value))
