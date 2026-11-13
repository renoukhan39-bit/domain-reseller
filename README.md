# Domain Reseller

A real Django + PostgreSQL domain reseller codebase designed for a guarded, incremental production rollout. The application implements customer authentication and email verification, registrant profiles, live registrar availability lookups, INR TLD catalog, Razorpay Orders checkout, signed payment-captured webhooks, database-backed paid-order fulfillment, Openprovider registration and renewal, nameserver changes, administration, audit trails, and tests.

**Current status: implementation foundation, NOT a launched or verified live service.** Registrar/payment credentials have not been provided; real sandbox end-to-end testing, billing/legal reviews, transaction reconciliation, deployment and backup drills remain outstanding. There are no simulated checkout paths in the application. Settings fail closed: sales and fulfillment are disabled by default.

## New developer / Codex? Start here

Read **[`docs/START_HERE.md`](docs/START_HERE.md)** for the complete mission, development workflow, feature inventory and roadmap. No prior chat is needed. This is the official project home.

## Quick start (local development, no domain purchase)

1. Install Docker + Docker Compose.
2. `cp .env.example .env` and set a private `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY` in `.env`.
3. `docker compose build`
4. `docker compose run --rm web python manage.py migrate`
5. `docker compose run --rm web python manage.py createsuperuser`
6. `docker compose up -d`
7. Open http://127.0.0.1:8000 (customer app) and http://127.0.0.1:8000/admin/ (admin).
8. Add eligible TLD prices through Django admin. Use **actual** supplier cost + margin + payment fees + taxes; no invented demo pricing is loaded.
9. Use `docker compose exec web python manage.py test shop` to run the test suite.

With `SALES_ENABLED=false` all orders are blocked. For **sandbox testing**, obtain separate Openprovider sandbox credentials, set `OPENPROVIDER_BASE_URL=https://api.sandbox.openprovider.nl/v1beta`, and Razorpay **test** keys and webhook secret. Only when setup is correct set `SALES_ENABLED=true` to exercise the payment sandbox. Set `FULFILLMENT_ENABLED=true` only after checking webhook delivery and registrar credentials. Do **not** use live Razorpay keys with sandbox registrar credentials.

## Production readiness status

- **Implemented:** core Django application, database schema, profile/email verification, authenticated customer pages, registrar API adapter, Razorpay Orders + signed webhook, manual refund command, guarded fulfillment worker, nameserver updates, unit/integration-style tests, PostgreSQL compose, CI workflow.
- **Verified:** [GitHub Actions Python CI passed](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43452225170) on the initial source import (Django checks, migration checks, migrations and test suite). Local PostgreSQL 16 and Docker validation with the cloud CA override passed all 39 tests for M1-08; see [verification evidence](docs/EMAIL_VERIFICATION.md#verification-boundaries).
- **Not verified:** registrar sandbox contract, real Razorpay sandbox webhook, real email delivery, deployment, cloud security, rate limits across workers, backup restore, financial and legal compliance.
- **Email verification:** [resend and SMTP configuration](docs/EMAIL_VERIFICATION.md) are implemented with single-use expiring links and database send throttles; external provider delivery remains unverified.
- **Not implemented:** customer invoices/tax calculations, supplier price sync, web-based support/refund system, transfers, automated expiries/renewal reminders, DNS record editor, reconciliation dashboard, reporting/ledger, production rate limiting for other endpoints, data deletion/export, observability alerts. These are explicit tasks, **not** silently called complete.

## Important business safeguards

1. Only authenticated users can see their own domains and orders. Customer registry handles are created using each person's own registrant details.
2. Browser success alone never marks orders paid: only a valid HMAC-verified **payment.captured** webhook with matching gateway order, currency, and amount does that.
3. The worker never automatically repeats a registrar call with an uncertain outcome. A human must reconcile any `needs_review` order with Openprovider before retrying or refunding.
4. In admin, order and payment records are read-only. Use `python manage.py refund_order <order-uuid> --confirmed-not-registered` **only after** verifying that no domain/renewal was processed and gateway state is correct.
5. Use **sandbox** first. The platform can cost ₹0 in software/license fees, but live registrations need supplier balance and checkout carries processing fees.

## Documents

- [`docs/PROJECT_GOAL.md`](docs/PROJECT_GOAL.md) — scope, user stories, definition of done.
- [`docs/TASKS.md`](docs/TASKS.md) — developer checklist and acceptance test matrix.
- [`docs/FREE_RESOURCES.md`](docs/FREE_RESOURCES.md) — credits, limits, remaining unavoidable costs.
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — build, cloud rollout, sandbox/live gates.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — data flow, security, known risks.
- [`docs/PR_HANDOFF.md`](docs/PR_HANDOFF.md) — how to commit to GitHub and continue with Codex.
- [`docs/5_DAY_EXECUTION_PLAN.md`](docs/5_DAY_EXECUTION_PLAN.md) — five-day implementation sprint with test evidence and exit gates.
- [`docs/PUBLIC_REPOSITORY_REPORT.md`](docs/PUBLIC_REPOSITORY_REPORT.md) — public open-source alternatives and licensing/cost caveats.

**Do not paste passwords, API keys, contact personal data, AWS access keys or subscription tokens into GitHub, pull requests, screenshots, or this chat.**

## Additional project handoff docs

- [`docs/START_HERE.md`](docs/START_HERE.md) — onboarding and scope
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — long-term competitive product stages
- [`docs/FEATURE_MATRIX.md`](docs/FEATURE_MATRIX.md) — written vs missing vs unverified
- [`docs/CODEX_CLOUD.md`](docs/CODEX_CLOUD.md) — cloud AI instructions
- [`docs/OWNERSHIP_AND_LICENSES.md`](docs/OWNERSHIP_AND_LICENSES.md) — code ownership and third-party license boundaries
- [`docs/PROVIDER_SETUP.md`](docs/PROVIDER_SETUP.md) — safe supplier/payment setup
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — new developer rules
