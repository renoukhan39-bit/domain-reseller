# Shared application request budgets — M5-05

Authentication and customer-operation counters now use PostgreSQL row locks through `shop/throttling.py`. They reuse the existing `EmailVerificationThrottle` table; no Redis dependency or new migration is required. The historical table name and HMAC salt are retained so existing verification windows remain valid. Keys contain HMAC digests rather than raw email addresses, usernames, user IDs or IP addresses. Namespaced scopes separate actions.

## Defaults and HTTP behavior

| Action | Budgets |
| --- | --- |
| Customer/admin login POST | 10/minute and 60/hour per source IP; 20/hour per normalized username, shared across IPs |
| Password-reset POST | 5/minute and 30/hour per source IP; 3/hour per normalized email, shared across IPs |
| Signup POST | 5/minute per unauthenticated source IP |
| Supported domain search | 20/minute per authenticated user or source IP |
| Purchase POST | 8/minute per authenticated user |
| Renewal POST | 8/minute per authenticated user |
| Nameserver mutation | 5/minute per authenticated user |
| Verification sends | Existing 5/minute per IP, 1/minute and 3/hour per email |

Throttled authentication/customer requests return HTTP 429 with `Retry-After` and `Cache-Control: no-store`. Budgets are consumed before looking up an authentication account, so throttled responses do not disclose whether an account exists. Unknown identifiers consume the same budgets as known ones. The middleware's `process_view` runs after Django CSRF validation; rejected CSRF submissions do not consume authentication budgets. The source IP comes from `REMOTE_ADDR`; untrusted forwarded headers are ignored. Configure a trusted proxy to supply the correct source address and add edge controls. Shared NAT/proxy addresses can encounter shared limits.

Budget database failures fail closed with a generic HTTP 503 and retry hint, without logging query details or identities. Health checks and static assets remain available when they do not require these counters. Payment webhooks are deliberately excluded from application throttling so legitimate gateway retries reach signature and state validation. Gateway replay/amount/order checks remain responsible for financial correctness.

Login identifiers use the same Unicode NFKC normalization as Django before case folding, so equivalent fullwidth/compatibility usernames share the same cross-IP budget.

Existing customer views retain their boolean `rate_limited` helper, now backed by shared counters. Middleware converts all denied cases into explicit 429 responses, including domain search, which previously only displayed a message with HTTP 200.

## Password reset and operations

`SafePasswordResetForm` retains Django's eligible-user selection, password-reset token generation, expiry and confirmation views. Reset links use the configured `EMAIL_VERIFICATION_BASE_URL` origin instead of request Host headers. HTTPS is required outside debug. SMTP and configuration failures produce the same public reset confirmation; logs contain only a fixed redacted delivery/origin message, not provider exceptions, reset links or recipients. Synchronous delivery can still have timing differences; a durable email queue and external SMTP verification remain follow-up work.

Run `python manage.py cleanup_verification_throttles` daily. It removes counters older than a day, preserving every active window (the longest is one hour). Secret-key rotation changes HMAC keys and effectively starts new windows; plan edge protection during rotation. There is no automatic permanent account lockout.

## Tradeoffs and reuse

**REUSE:** Django's existing middleware, CSRF, password-reset forms/token generator, ORM transactions and signing facilities; existing BSD-3-Clause Django dependency. **BUILD:** small application-specific budget selection and generic HTTP responses. No external source was imported and no new dependency or outbound license decision was added.

Shared database counters provide correctness across application workers but add database contention and row growth under abusive traffic. Global username/email budgets also permit temporary targeted denial of a known identifier; use bounded windows, monitoring and edge challenge/bot rules rather than treating these limits as a complete defense. PostgreSQL locking behavior is covered by concurrency tests. This milestone does not configure Redis, a WAF, production bot challenges, distributed load capacity, external SMTP, or production approval; M5-05's full acceptance gate remains open until those deployment checks pass.

Local verification: the complete PostgreSQL 16 suite ran **166 tests with zero failures or skips**, including 20 throttle/reset tests, concurrency tests, and the payment/registrar/email regressions. Django checks, migration checks, compilation and diff checks passed. The dependency advisory audit checked all 14 installed application dependencies with zero skips and reported no known advisories; that is an advisory snapshot, not a full security review.

Clean-image verification also passed all 166 tests with no runtime asset preparation. Docker now collects static files while building; CI collects them before testing. Explicit customer password-reset template names prevent admin templates from taking precedence. Gunicorn HTTP checks and Chromium customer resend/reset flows passed.
