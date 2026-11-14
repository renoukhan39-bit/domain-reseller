# M5-09 — Reconciliation backlog monitoring and operator response

Status: **application command and synthetic database tests implemented**; alert delivery, production scheduling and on-call drills are **not yet verified**. This is a focused read-only addition on top of `feat/P0-payment-registrar-hardening`. It does not enable sales/fulfillment or make payment or registrar calls.

## Purpose and output contract

`check_reconciliation_backlog` emits one JSON line, with `schema_version=1`, UTC-aware `checked_at`, `minimum_age_minutes`, `status` (`ok` or `alert`), `counts` and `alert_categories`. With an alert it exits **nonzero** by default so an external scheduler/monitor can trigger a page. `--warn-only` exits zero for adoption/dashboards but still reports `status=alert`.

It deliberately excludes domain names, owner identifiers, email addresses, bank/payment identifiers, gateway tokens and provider exception strings. Do not publish operational logs or wire them into a customer-facing endpoint; counts can still reveal business activity. The report is a set of sequential read-only database counts, **not** an atomic financial ledger or a provider balance.

| JSON count | Meaning | Operator response |
| --- | --- | --- |
| `manual_review_orders` | Orders in `needs_review` at any age | Determine if the uncertainty concerns gateway initiation, registration or renewal; use the relevant read-only reconciliation runbook |
| `stale_paid_orders` | Paid but unfulfilled longer than threshold | Check worker health and feature switches; verify whether provider action was attempted before any retry |
| `stale_processing_orders` | Registrar worker still processing beyond threshold | Run stale escalation and verify provider state; do **not** automatically repeat registration or renewal |
| `refund_review_orders` | Refund outcome uncertain | Inspect gateway refund ID/state with the approved read-only command |
| `stale_refund_pending_orders` | Refund submitted but unresolved beyond threshold | Read-only refund lookup; never send a second POST blindly |
| `stale_waiting_payment_events` | HMAC-verified early captured event without a matched local gateway order | Check receipt/order binding; use retained-event replay or authentic gateway redelivery |
| `payment_event_conflicts` | Payment evidence mismatched or assigned elsewhere | Investigate amount, currency, payment identifier and owning order without overwriting records |
| `legacy_ignored_captures` | Older captured event had no retained evidence | Require a fresh valid signed delivery or separate operator reconciliation |
| `stale_unprocessed_payment_events` | Stored event has no completed processing outcome | Inspect failed processing and event integrity; never forge a signature |

An order may move between categories between counts. Recent `awaiting_payment` customer checkouts are **not** alerts because customers may abandon checkout. `paid` orders will alert if stale even when fulfillment is deliberately disabled, so the operator can account for outstanding customer commitments.

## Usage

Run in the deployment application environment with PostgreSQL and migrations completed:

```bash
# Non-mutating alert check; default age threshold = 30 minutes.
python manage.py check_reconciliation_backlog --minutes 30

# Adoption/synthetic drills: JSON still says alert but exit is zero.
python manage.py check_reconciliation_backlog --minutes 30 --warn-only

# A separate, explicit state transition to manual review (never a registrar retry):
python manage.py mark_stale_orders --minutes 30 --limit 100
```

Valid age is from 5 minutes to 7 days. A failing run should cause a scheduler/agent to alert the responsible operator. Configure **actual** alert routing in the deployment monitoring system (e.g. existing cloud scheduler/log and alarm rules) rather than writing email/API credentials into this repository. Define review ownership, acknowledge alerts, maintain escalation coverage, and collect a drill artifact before closing M5-09. Check data protection settings for operational log retention/access.

### Operator escalation SOP

1. Verify the application database and monitoring command itself are healthy; a database connection/command error is **not** an all-clear.
2. Run `check_reconciliation_backlog --warn-only` and record the timestamp/counts in a restricted incident log. Identify the category. Use read-only admin filters and service-specific reconciliation commands from `PAYMENT_RECONCILIATION.md`, `REFUNDS.md`, and `FULFILLMENT_RECOVERY.md` to obtain record details within authorized staff systems.
3. For stale registrar processing, run `mark_stale_orders` separately and review the matching `stale_fulfillment_review` audit records. Confirm actual provider state and customer's registrar handle before deciding on any refund or manual state correction.
4. For payment events, use `reconcile_payment_events` only with retained valid signed evidence, or read-only `reconcile_payment` using a verified gateway order ID. Do not fake a webhook or assume checkout JS callback proves capture.
5. For refunds, use `reconcile_refund` GET with the known verified refund ID. Do not automatically re-submit an uncertain refund.
6. Continue monitoring until the backlog is resolved. Escalate unresolved items to the authorized business/payment/registrar operator; document the provider evidence and recovery decision outside the source repository.

### Privacy and safety

The checker neither locks workflow rows nor changes order/event status, and it never uses provider adapters or outbound HTTP. It can run while sales and fulfillment are off. No database migration or runtime library is required. It makes no attempt to deduplicate alerts or deliver notifications itself; existing monitoring should handle retry, suppression, grouping, escalation and on-call routing.

Tests cover a healthy database, recent versus stale workflow thresholds, every alert class, nonzero monitoring exit, `--warn-only`, input validation, absence of customer data in output, no external requests, and no mutations. Run:

```bash
DJANGO_DEBUG=true python manage.py test shop.test_reconciliation_backlog
DJANGO_DEBUG=true python manage.py test shop
DJANGO_DEBUG=true python manage.py check
DJANGO_DEBUG=true python manage.py makemigrations --check --dry-run
```

**Acceptance remains open** until an operator demonstrates a real scheduled alarm, acknowledges it, safely reconciles a synthetic staging incident, and verifies the result. No customer data or real payments are needed for that drill.

## Reuse/architecture decision

**REUSE / CONFIGURE:** Django 5.2's management commands, ORM filters and PostgreSQL (already used; Django BSD-3-Clause) plus whichever existing infrastructure log/alert agent the operator chooses. **BUILD:** only the application-specific status/age classification and non-PII JSON contract. No second backend, Celery, paid monitoring SDK, copied upstream source, or unsafe provider calls.
