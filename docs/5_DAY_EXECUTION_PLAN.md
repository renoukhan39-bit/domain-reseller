# Domain Reseller — 5-day execution plan

**Project:** https://github.com/renoukhan39-bit/domain-reseller  
**Prepared:** 2026-11-13  
**Goal:** Turn the current production-oriented Django source package into a **verified, deployed, non-public staging release candidate** using existing eligible credits and test services. **Five days is a sprint target, not a promise of production readiness.**

## Starting facts and constraints

- This repository is the official project home; verify actual GitHub commits and CI status before work.
- Repository access must be verified for each developer. Do not work around repository permissions.
- Initial project: Django + PostgreSQL + Openprovider + Razorpay. Keep this architecture for the first sprint; compare alternatives in `PUBLIC_REPOSITORY_REPORT.md` before considering any rewrite.
- `SALES_ENABLED` and `FULFILLMENT_ENABLED` stay disabled until explicitly verified in test environments. Never pair live payment credentials with a sandbox registrar.
- Never commit API keys, credentials or customer personal data. Use secret management and environmental configuration. Check Openprovider's current supported endpoint versions; official production docs now recommend `/v1` over retiring `/v1beta`.
- Expense target: ₹0 **incremental development spend** under the owner's specified exclusions, contingent on eligibility/expiry of existing AWS/Azure credits. Real registrations, payment processing, compliance and operator time are outside that promise.

## Day 1 — Repo, local runtime and CI

**Tasks:** Fix GitHub permissions; push source package on a new branch via authorized account; open a PR; configure `.env` with non-production values; build Docker; run PostgreSQL migrations; execute Django checks and test suite; inspect CI failures. Prioritize `M0-09`.

**Developer commands (once source is checked out):**

```bash
cp .env.example .env
# Set unique local values for POSTGRES_PASSWORD and DJANGO_SECRET_KEY in .env
# Never commit .env
docker compose build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py test shop
docker compose up -d
```

**Exit evidence:** PR link, green CI run, clean migration log, login/admin page accessible locally, no secrets in PR. **Tests:** AT01–AT02.

**Blocker if missing:** Authorized GitHub write access or local Docker runtime. Continue local testing if GitHub access is not available; clearly note upload blocked.

## Day 2 — Customer identity, pricing and registrar sandbox

**Tasks:** Review tests for sign-up, login, reset, ownership and registrant profile; configure safe email delivery for staging; test verification email; confirm real TLD wholesale cost, fees and tax before enabling any fixed price; set up Openprovider sandbox account; verify search and contact creation; confirm API path/version in provider docs. Prioritize `M1-08`, `M2-07`, first half of `M4-07`.

**Exit evidence:** Evidence of email activation, account isolation, supported domain availability response from sandbox, no invented prices or premium-domain checkout. **Tests:** AT03–AT08.

**Blocker if missing:** Sandbox/API or email-provider access. Do not fake a passed external integration: mark tests blocked and attach mocked unit-test results separately.

## Day 3 — Test money flow and registrar fulfillment

**Tasks:** Configure Razorpay **test keys** and webhook test secret; verify payment amount/currency/order ID and raw-body HMAC; test duplicate, replayed, malformed and out-of-order webhooks; validate a **sandbox** registration; exercise renewal and nameserver updates on sandbox-created domain; ensure uncertain responses become manual review, never blind retries. Prioritize `M3-08`, `M3-09`, `M4-07`, `M4-08`.

**Exit evidence:** Recorded webhook scenarios, test gateway IDs, sandbox registrar IDs, no duplicate charges/provisioning, reconciliation cases documented. **Tests:** AT09–AT18 (only those actually executed).

**Blocker if missing:** Provider sandbox support/credentials. Never submit live domain orders merely to clear the checklist.

## Day 4 — Cloud staging, protections and recovery

**Tasks:** Verify AWS Activate balance, eligible services and expiry in account console; set budgets/alerts and restrictive permissions; provision a TLS-protected staging environment; configure database, secrets and logs; add cross-process rate limiting, mail controls and alerting; perform encrypted PostgreSQL backup and restore drill; document rollback. Prioritize `M0-10`, `M5-05`–`M5-09`, `M6-03`.

**Exit evidence:** Restricted staging URL, HTTPS/security headers verified, alarms configured, backup restored successfully, no production credentials or live money. **Tests:** AT19, portions of AT20.

**Blocker if missing:** Verified cloud credit access or deployment permissions. Run staging locally until cloud access is approved.

## Day 5 — Acceptance, defects, review and handoff

**Tasks:** Execute the complete acceptance matrix in `TASKS.md`; mark each test **pass/fail/blocked** with evidence; fix highest-risk defects; review ownership/payment/provider paths, dependencies and logging; write an operator runbook; prepare a PR and issue ownership for unfinished tasks. Prioritize `M6-04`, `M6-06`, outstanding P0 blockers.

**Exit evidence:** CI logs, staging demonstration, test matrix, defect list, security gaps, incident/recovery report, documented go/no-go for restricted staging only. **Tests:** AT01–AT20, with honest status.

**Blocker if missing:** Do **not** declare production ready unless legal, business/KYC, live registrar funding, real-payment reconciliation, tax/invoices, privacy/terms, security and restoration are separately approved (`M6-01`–`M6-06`).

## End-of-sprint dashboard

| Check | Definition of done | Expected stage |
| --- | --- | --- |
| Repo | All files committed; PR/CI visible | staging |
| App | Migrations, customers, searches, checkout UI work | staging |
| Providers | Real API interactions verified against sandbox/test providers | staging |
| Safety | No active live payment or registrar operations; bad input and retries blocked | staging |
| Infra | TLS, secrets, backups, logs, quotas and rollback tested | staging |
| Release | All acceptance tests marked honestly with evidence and unresolved issues | staging |

## Beyond 5 days (not optional for public launch)

- Production-level distributed throttling, security testing and incident monitoring.
- Customer invoice and applicable tax handling, lawful privacy/data workflows, business eligibility and agreements.
- Payment/registrar ledger reconciliation and live trial approval.
- Renewal notices, registrar price sync, domain lifecycle/transfer features and DNS editor.
- Verified customer support and refund operations.

## Reusable prompt for a developer or Codex

> Read `AGENTS.md`, `docs/PROJECT_GOAL.md`, `docs/TASKS.md` and `docs/5_DAY_EXECUTION_PLAN.md`. Work on the earliest incomplete P0 task that is not blocked by unavailable credentials. Add relevant positive/negative tests, run local checks, update the checklist only when code is verified, and commit a focused PR. Do not use live money, change provider accounts, expose credentials or claim unrun tests pass. Report any blockers explicitly.
