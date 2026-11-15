# Openprovider contract validation — M4-07

The adapter uses the existing Requests HTTP client and Openprovider's documented REST contract. No registrar write or real sandbox request was made for these checks. Sales and fulfillment remain disabled unless the owner separately approves a sandbox or live acceptance run.

## API version and trusted destinations

Openprovider's [official migration banner](https://github.com/openprovider/api-documentation/blob/e7742139b438525955e21f9cc0957ab2b84402a5/index.html#L75-L76) states that `/v1` is available and functionally identical, new integrations must use it, and existing `/v1beta` integrations must migrate before **30 June 2027**. The same repository's older README still recommends `/v1beta`; the newer migration notice takes precedence. Current documentation is at [developer.openprovider.com](https://developer.openprovider.com/).

`provider_environment()` recognizes exactly `https://api.sandbox.openprovider.nl/v1` as sandbox and `https://api.openprovider.eu/v1` as live. Explicit legacy `/v1beta` configuration remains recognized during migration, with no claim that it is appropriate for new integrations. An optional standard HTTPS port is permitted. Other hostnames, embedded usernames/passwords, query strings, fragments, custom ports, and additional path segments are rejected. The environment pairing guard must use this classification rather than searching the URL for a sandbox substring.

Requests keep TLS verification enabled and disable redirects for authentication and authenticated API calls. This prevents an API redirect from selecting a different credential destination. Authentication and domain requests have bounded timeouts. The adapter never automatically retries a registrar mutation after an uncertain response.

## Validated response contracts

- Responses require a successful HTTP status, an object envelope with integer `code: 0`, and an object `data`. Maintenance responses, missing/non-object data, bad JSON, network failures and redirects become redacted `ProviderError` messages. Provider descriptions, credentials, and customer data are not included in outward errors.
- Authentication requires a nonempty bounded ASCII token without whitespace. Invalid tokens cannot become authorization headers or cached credentials.
- Availability requires exactly one result, the exact requested domain, a recognized availability status and explicit boolean `is_premium: false` before fixed-price checkout can proceed. Missing, unknown or contradictory classifications stop checkout.
- The [official availability example](https://github.com/openprovider/api-documentation/blob/e7742139b438525955e21f9cc0957ab2b84402a5/swagger/domain.swagger.json#L2161) includes a nonempty `premium` object with `price.create: 0` even when `is_premium` is false. This ordinary-domain shape is accepted. Nonzero, nonfinite, contradictory, or malformed premium metadata requires manual review; fixed-price premium sales remain unsupported.
- Domain identifiers must be positive bounded integers, never booleans, floating point values, or strings that can change a URL path. Registration must return a valid identifier. Customer handles and nameservers are validated before use; the customer-specific owner handle is retained.
- Provider dates are parsed only from actual valid timestamp strings. Missing or malformed values stay unknown; the application must not derive a successful renewal expiry by adding a local year. The official schema identifies `renewal_date` as the primary renewal reference.

## Evidence and remaining acceptance gates

Offline adapter tests in `shop/test_providers.py` passed with fake HTTP responses: 19 tests cover official zero-price premium shapes, malformed JSON/envelopes/tokens, host spoofing, redirects, request timeouts, domain mismatches, invalid identifiers and contacts, nameserver validation, and expiry parsing. These tests exercise the adapter's transport contract and fail-closed behavior; they do not prove Openprovider's sandbox currently accepts every endpoint or registry-specific field.

To accept M4-07, an authorized operator still needs separate sandbox credentials and approved network access, then must verify authentication, availability, actual customer handle ownership, registration, renewal-date advancement, nameserver changes, pending states, provider errors and read-only reconciliation against the current API. Retain captured evidence securely and redact registrant information. Do not run a live purchase to substitute for missing sandbox verification.

## Reuse and license decision

**CONFIGURE / REUSE:** the existing [Requests client](https://github.com/psf/requests) (Apache-2.0) provides HTTP/TLS/timeouts; Python's standard URL, decimal and datetime libraries provide parsing. **BUILD:** this project's small provider adapter validates domain-specific responses and safety invariants. No third-party application source is imported, no new dependency is added, and the project's outbound license is unchanged. Risks remain external API/version changes, registry rules, credentials and provider-side uncertainty; offline fixtures cannot remove those operational risks.
