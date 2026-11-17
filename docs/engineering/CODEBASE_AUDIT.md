> Recovery note (17 November 2026): recovered from `4f65433d27ad`. The original text below is retained as historical project work; old PR states, verification counts and proposed changes are snapshots, not current status. Current recovery evidence and handoff are in `../AnalyseFuture/REPOSITORY_AUDIT.txt` and `../AnalyseFuture/NEXT_DEVELOPER_INSTRUCTIONS.txt`. The nameserver ownership fix is being recovered with its tests in this task; use the current validation report for results. Direct main delivery is explicitly authorized for this task.

# Codebase audit — evidence-led snapshot (2026-11-15)

**Scope:** `renoukhan39-bit/domain-reseller` at default-branch commit `6b522210ee47a38abc14868b0f26dcabc910dd83`. The nameserver hardening in branch `fix/M5-08-nameserver-registrar-identity` is a **proposed change**, not a production deployment. This review inspected the GitHub source tree, key application files, the migrations/test inventory, CI workflow, and project documentation; it is **not** a complete line-by-line penetration test, dependency CVE audit, or external integration acceptance test.

## Architecture decision

**Retain Django 5.2/Python 3.12 + PostgreSQL + server-rendered modular monolith.** `config/` configures Django; `shop/` implements the domain workflow; PostgreSQL provides locks and uniqueness; the separate `process_orders` command acts as a controlled worker. `compose.yaml` supplies PostgreSQL, web, and worker containers; GitHub Actions tests on PostgreSQL 16. No ADR approves a PHP/Laravel/MySQL migration.

The model is not yet a multi-tenant wholesale/reseller platform: isolation currently uses individual Django user ownership. Do not describe customer-user ownership as full future organization/tenant isolation.

## Main source inventory, responsibilities, dependencies, evidence and next action

| Source | Responsibility / dependency | Present and automated evidence | Gaps, risk and disposition |
| --- | --- | --- | --- |
| `config/settings.py`, `config/urls.py` | Security, database, integration settings; Django | Fail-closed `SALES_ENABLED`, `FULFILLMENT_ENABLED`, HTTPS and cookie settings exist | Deployment headers, real secrets, TLS and DB policy are unverified; **CONFIGURE** |
| `shop/models.py`, migrations `0001`–`0003` | Customers' registrant contacts, TLD prices, managed domains, orders, signed event digests/evidence, audit | PostgreSQL partial uniqueness and amount/currency constraints; tests cover many races | No tax invoice, settlement ledger, provider price snapshot, comprehensive lifecycle; **BUILD incrementally** |
| `shop/forms.py`, `shop/accounts/verification.py`, `shop/middleware.py`, `shop/security/throttling.py` | Signup/profile, email activation/resend, domain/NS input, shared DB request budgets | `shop/tests/accounts/test_verification.py`, `shop/tests/security/test_throttling.py` | SMTP end-to-end, identity-policy review, production edge/WAF unverified; **REUSE Django + CONFIGURE email/edge** |
| `shop/views.py`, `shop/urls.py`, `shop/templates/` | Customer pages, checkout, renewal, NS, HMAC webhook | `shop/tests/test_core.py` and specialized tests include cross-account 404s and webhook failures | Before this branch, NS POST verified local owner only, not current registrar identity; proposed guard in branch; no full cart, invoice, support; **ADAPT** |
| `shop/domains/openprovider.py` | HTTPS Openprovider /v1 adapter and conservative response validation; Requests | `shop/tests/domains/test_openprovider.py` uses fake HTTP for endpoints, statuses, tokens, premium ambiguity | Real sandbox schemas/TLD rules remain unverified; registration contact writes have external uncertainty; **ADAPT** |
| `shop/commerce/gateway.py` | Razorpay Orders/refunds/GET, signature HMAC; Requests | `shop/tests/commerce/test_payments.py`, `shop/tests/commerce/test_refunds.py` | Test-mode delivery, gateway reconciliation and settlement unverified; **REUSE transport / ADAPT business policy** |
| `shop/commerce/events.py` | Signed event minimal evidence, single-payment attribution and replay | Unique event ID, digest collision guard, strict captured status/amount/currency and DB locking tested with fixtures | Gateway receipt provenance and replay/operational monitoring require live test evidence; **ADAPT** |
| `shop/commerce/orders.py` | Guarded order creation, payment binding, registrar fulfillment; Django transactions | Durable paid→processing claim, external identity read-back, no auto-retry on uncertain writes; `shop/tests/commerce/test_fulfillment.py` | Payment + registration cannot be one ACID transaction; cross-system reconciliation is essential; **ADAPT** |
| `shop/commerce/refunds.py` + refund/reconcile commands | Durable operator refund intent and read-only recovery | `shop/tests/commerce/test_refunds.py`; retains attempt marker before POST | Tax/accounting/settlements, partial refunds and provider-side evidence outstanding; **ADAPT** |
| `shop/management/commands/` | Worker, stale order escalation, registration/payment/refund recovery, monitoring | `shop/tests/operations/test_reconciliation_backlog.py`, `shop/tests/commerce/test_fulfillment.py` | External alert routing, scheduling, on-call rehearsal missing; **CONFIGURE / ADAPT** |
| `shop/admin.py` | Operator screens | Admin definitions exist; financial records protected by source-level read-only design | Operator permission review, financial workflows/role separation unverified; **ADAPT** |
| `scripts/backups/database_backup.py`, `scripts/backups/backup_restore_drill.py`, `scripts/backups/test_database_backup.py` | Encrypted PostgreSQL backup and synthetic restore validation | Offline backup/drill tests and separate GitHub Actions job defined | Real offsite restore, retention, key recovery, staging drill remain unverified; **CONFIGURE** |
| `.github/workflows/ci.yml`, `pyproject.toml`, `Dockerfile`, `compose.yaml` | Python CI, PostgreSQL 16, packaging and compose | CI includes Django check, migration check, migrate, collectstatic, tests, compilation and backup job | Runtime Docker locally not independently reproduced in this session; dependencies not pinned to a fully locked graph; **CONFIGURE** |

The tests are discovered from `shop/tests/test_core.py`, `shop/tests/domains/test_openprovider.py`, `shop/tests/commerce/test_payments.py`, `shop/tests/commerce/test_fulfillment.py`, `shop/tests/commerce/test_refunds.py`, `shop/tests/accounts/test_verification.py`, `shop/tests/security/test_throttling.py`, and `shop/tests/operations/test_reconciliation_backlog.py`. Migration 0003 adds payment evidence and concurrent operation constraints. Inspect full tests before altering their state assumptions.

## Purchase workflow and transaction boundaries

1. **Customer:** inactive signup is verified before login. RegistrantContact must exist for checkout. `shop/views.py` filters orders/domains by `owner=request.user`.
2. **Search/pricing:** form normalizes ASCII one-label TLD domains; `TLDPrice` is an admin-maintained INR catalog; `Openprovider.check` requires an exact single match and explicit non-premium free status. Retail price is **not** synchronized to live wholesale costs.
3. **Order:** `create_checkout_order` validates price and owner, saves the local UUID order before requesting a Razorpay Order. Per-user checkout keys, PostgreSQL partial unique constraints and renewal owner checks limit duplicate unresolved operations.
4. **Payment boundary:** gateway order creation happens **outside** the initial DB transaction. Timeout/unknown POST outcome marks a manual-review state; do not issue another order POST under a new key. On returned gateway ID, the service binds it under a row lock and replays early signed events.
5. **Verified webhook:** raw HMAC-SHA256, event ID/digest uniqueness, captured status, payment ID, order ID, exact integer amount and currency are required. Invalid/unmatched signed messages cannot set `paid`. Duplicate deliveries are safe; unknown order events are stored for operator review/replay.
6. **Worker claim:** `fulfill_one` requires both switches and compatible test/live pairing, then commits the `paid → processing` claim with `transaction.atomic(durable=True)` **before** the external registrar write. A second worker sees no `paid` row to claim.
7. **Openprovider:** the worker creates/uses a customer-owned contact handle, performs one register/renew POST, then GET-verifies domain ID/name/owner/status/authoritative expiry. It does not infer renewed dates locally.
8. **Uncertainty:** provider timeout or pending/mismatch moves to `needs_review`; `mark_stale_orders` escalates blocked processing; reconciliation GETs never automatically repeat a registrar mutation. Refunds use their own irreversible claim and external verification.
9. **Dashboard:** local managed domains and orders are scoped to the current user. Local display is not proof of current registry ownership; this branch adds a live provider identity check prior to customer nameserver PUT.

**Critical boundary:** a charge and registrar registration cannot be rolled back atomically across both APIs. Preserve manual review and immutable evidence; never retry an ambiguous registrar or financial write automatically.

## Findings (evidence, severity, likelihood, remedy)

| Finding | Evidence | Severity / likelihood | Corrective action |
| --- | --- | --- | --- |
| **F-01 Confirmed:** local ownership but no registrar identity read before customer NS PUT | `shop/views.py::nameservers` originally calls `Openprovider().update_nameservers(domain.provider_id, ...)` directly after local row owner/status check | **High** impact if registrar ownership changed externally; likelihood depends on stale records/transfers | Proposed branch: read registrar record; match ID, exact domain, customer contact handle and active status; never mutate on ambiguous read; regression tests |
| **F-02 Confirmed:** weak NS enablement guard | `shop/views.py::nameservers` originally checks only `FULFILLMENT_ENABLED`, while order worker uses `fulfillment_ready()` | **High** impact under misconfiguration; likelihood operational | Proposed branch: require both switches, valid credentials and test/live provider/payment pairing for customer NS mutations |
| **F-03 Confirmed:** legacy architecture documentation is contradictory | `docs/engineering/ARCHITECTURE.md` says throttle is per-process cache, but `shop/security/throttling.py` and `docs/operations/THROTTLING.md` use shared DB rows; `docs/engineering/TASKS.md` header disclaims all CI runs despite recent green CI | **Medium** operational confusion; likely | Reconcile docs; distinguish local fixtures, CI, external sandboxes |
| **G-01 Acceptance gap, not a confirmed exploit:** end-to-end payment + registrar sandbox | No supplied credentials/evidence for actual signed Razorpay delivery or Openprovider write/read | **Launch-blocking / unknown** | M3-08 + M4-07; operator-led test evidence |
| **G-02 Acceptance gap:** tax/invoice/ledger/supplier cash | No invoice/tax/settlement model in `shop/models.py` | **Launch-blocking / certain missing feature** | M2-07, M3-10, M6-02; approved policy and verified ledger |
| **G-03 Acceptance gap:** production security and recovery | No successful restricted staging/TLS/WAF/offsite restore/on-call drill shown | **Launch-blocking / unverified** | M5-05/06/07/08/09; M6-04/06 |
| **G-04 Acceptance gap:** domain transfers, DNSSEC, IDN, registry-specific attributes | Source implements first-release ASCII one-label TLD only, no full transfer/DNSSEC service | **P1 later / missing** | M2-09, M4-09, M6-07 after launch controls |

**No claim** is made of a confirmed payment HMAC bypass, tenant-data leak, SQL injection, dependency CVE or provider compromise. Such conclusions require separate evidence.

### Nameserver hardening operational caveat

A registrar GET immediately before PUT narrows stale-ownership exposure but does not make the provider operation atomic with a subsequent transfer or registry change. The current documented `get_domain` response shape must be validated in the **real sandbox**. Temporarily stopping sales also blocks customer NS changes after this conservative fix; later maintenance availability should use a separately reviewed and explicit registrar-management gate rather than silently bypassing safety controls.

## Verification evidence and limitations

- **Observed prior main CI:** `https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43744046697` completed **success** for commit `6b522210...`; the workflow runs Django system/migration checks, PostgreSQL 16 migrations, shop tests and compileall. The action has a separate backup recovery job. CI **success is not external provider verification**.
- Existing `docs/operations/THROTTLING.md` records a 166-test local PostgreSQL 16 run; treated as **historical documented evidence**, not rerun here.
- This research session's container could **not resolve github.com**, so no clean checkout, local Docker startup, PostgreSQL migration or Django test command was performed here. Branch-side GitHub Actions are the relevant repeatable verification.
- No credentials, cloud deployment, real payment, registry mutation or sandbox tests were used.
- **New targeted fixture command (after checking out the branch):** `python manage.py test shop.test_nameserver_safety -v 2`.
- **Full checks:** `python manage.py check && python manage.py makemigrations --check --dry-run && python manage.py test shop && python -m compileall -q config shop`; run with PostgreSQL 16 and the CI environment.

## Documentation cleanup debt

`docs/START_HERE.md` still suggests independent Docker verification was absent while `README.md` and `docs/operations/THROTTLING.md` record a previous local Docker-based test run. Clarify that historical tests do not prove the current branch nor a production deployment. `docs/engineering/ARCHITECTURE.md` references an in-memory throttle despite DB-backed throttle code. Preserve existing issue IDs and historical run links rather than resetting checkboxes or treating mocked tests as sandbox evidence.
