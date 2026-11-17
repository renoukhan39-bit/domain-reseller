# Email verification — M1-08 / issue #3

## Customer flow and safeguards

Signup creates an inactive user and an explicit `EmailVerification` pending record. The sign-in and signup pages link to `/accounts/verification/resend/`. Submitting a valid email always redirects to the same generic confirmation, including unknown, already active, administratively disabled, throttled, and failed-delivery cases. The form requires CSRF and GET never sends mail.

Links use Django timestamp signing with a 24-hour default lifetime, the current email address, and a random nonce. Resending rotates the nonce and invalidates earlier links. GET displays a confirmation form; a CSRF-protected POST activates the account and deletes its pending record atomically. Email scanners following GET links cannot activate an account. Activation does not log anyone in. Replaying an already consumed link cannot log in or reactivate a subsequently disabled account. Invalid/expired links offer resend. Verification responses disable caching and referrers.

PostgreSQL counters limit requests to five per minute per source IP, one per minute per normalized email, and three per hour per normalized email. Signup's initial send shares these budgets with resends. Counters use HMAC keys, not raw addresses, and row locks serialize requests across workers. The IP comes from `REMOTE_ADDR`; forwarded headers are ignored. Configure the trusted reverse proxy/edge to enforce its own abuse limits; shared proxy/NAT addresses may encounter the IP limit. These limits apply to verification delivery, not the rest of the application's existing in-memory throttles.

SMTP has a bounded timeout; transport failures retain the inactive account and allow retry after the cooldown. Audit rows record sent/failed/verified outcomes without recipient addresses, tokens, or provider exception text. A delivery exception is not logged verbatim. A send accepted by SMTP is not proof of inbox delivery. Delivery runs synchronously, so the generic response does not guarantee identical timing for eligible versus unknown addresses; a durable mail queue and edge abuse protection remain follow-ups. A racing activation/resend can deliver a superseded link, which fails closed and offers resend.

## Configuration

Reuse Django's maintained SMTP backend; no new application dependency or paid email SDK is required.

| Setting | Purpose |
| --- | --- |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` for a real provider; console only for local development |
| `EMAIL_HOST`, `EMAIL_PORT` | Provider's documented SMTP hostname/port |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Credentials injected securely; never commit or paste values |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | STARTTLS or implicit TLS; enable only the provider-required option, never both |
| `EMAIL_TIMEOUT` | Socket timeout, defaults to 10 seconds |
| `DEFAULT_FROM_EMAIL` | Sender authorized by the provider |
| `EMAIL_VERIFICATION_BASE_URL` | Explicit public origin, e.g. `https://accounts.example.com`; mandatory HTTPS outside debug; no path, credentials, query, or fragment |
| `EMAIL_VERIFICATION_MAX_AGE` | Link lifetime in seconds, defaults to 86400 |

Links use the configured origin, never the request's Host header. Set that origin before enabling production signup. Use proper CA trust and TLS verification. Configure SPF/DKIM/DMARC and verify delivery/bounce behavior with the chosen provider before accepting M1-08. Configure production access logs/error monitoring to redact `/verify/<token>/` paths and avoid logging mail bodies. Debug console email intentionally prints links and must not be used with real customer data.

Run `python manage.py migrate --noinput` before starting the new version. Schedule `python manage.py cleanup_verification_throttles` daily to remove hashed counters older than a day. It retains every live throttle window.

## Existing accounts and rollback

Migration `0002` adds two tables and deliberately does not treat every old inactive user as a pending signup: inactive can also mean an administrator suspended an account. Old links are rejected. For an older unverified signup, an operator must confirm that it is a legitimate pending signup and not a suspended account, then create its `EmailVerification` record through a controlled Django shell (`EmailVerification.objects.get_or_create(user=confirmed_pending_user)`). The customer can then use resend. Never bulk-enroll inactive users or re-enable suspended accounts. New signups need no manual step.

Application rollback can leave the additive tables intact. Avoid reverting to the old reusable activation links; disable signup/verification at the proxy until a reviewed fix is deployed if activation safety is in doubt. No payment or registrar feature flags change.

## Reuse decision

**CONFIGURE / REUSE:** Django 5.2's [email backends](https://docs.djangoproject.com/en/5.2/topics/email/) and [timestamp signing](https://docs.djangoproject.com/en/5.2/topics/signing/), already installed; BSD-3-Clause ([upstream license](https://github.com/django/django/blob/stable/5.2.x/LICENSE)). Django is the repository's maintained framework; no upstream source is copied. SMTP transport/auth/TLS remains delegated to Django/Python. Integration adds two small tables and a migration. **BUILD:** application-specific pending-signup eligibility, single-use nonce consumption, and database send budgets; password/login/session handling stays with Django. Risks are SMTP availability, abuse, legacy-account review, and database contention; focused tests exercise failure and concurrent requests. No new license or outbound project-license decision.

## Verification boundaries

Local automated tests cover activation, expiration, replay, account eligibility, CSRF, trusted origins, transport failures, and shared-counter/token concurrency on PostgreSQL 16. Docker validation uses a cloud-only BuildKit CA mount rather than disabling TLS. Real provider inbox delivery, registrar/payment sandbox contracts, production approval, and backup/restore are separate acceptance work; this change does not close issue #3 or tick its full checklist gate.

Evidence from 13 November 2026: `manage.py check`, `makemigrations --check --dry-run`, `migrate --noinput`, `test shop` (39 passed, zero skips including three concurrency tests), compilation, dependency consistency, and diff checks passed on local PostgreSQL 16. The same migration/check/test commands passed in Docker with a mounted cloud CA. Containerized Gunicorn passed resend GET, missing-CSRF rejection, and valid-CSRF generic POST checks. Chromium passed sign-in → resend → generic confirmation. [Push CI passed](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43459853138) for implementation commit `7c8489dfcfeacf9281776d9417f47b09710095df`; PR CI is not yet verified.
