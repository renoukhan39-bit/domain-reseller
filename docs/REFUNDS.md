# Refund requests and read-only reconciliation — M3-09

Refunds are operator-only financial actions. Confirm the registrar did not complete the registration or renewal, check the gateway account and payment, and obtain the required owner approval before any live refund. No customer endpoint or background worker invokes these commands.

## Durable intent and uncertainty

`refund_order <order-uuid> --confirmed-not-registered` accepts eligible `needs_review` orders with a matching captured Razorpay payment. It refuses registrations already linked to a registered/pending domain, prior refund IDs, or any earlier `refund_attempted_at`. Renewal orders must still refer to a domain owned by the order customer. The command verifies the full captured amount, currency, order/payment IDs, and absence of previous refunds using a read-only payment lookup.

The application commits `refund_pending` and a durable attempt timestamp **before** sending the refund POST. Calling the service inside an enclosing database transaction is rejected: a later rollback must never erase the evidence of a financial request. The timestamp is never reset automatically. Concurrent requests can send at most one POST.

Matching gateway evidence can produce `refunded` only for a `processed` full refund. A `pending` refund stays `refund_pending`; `failed`, a timeout, malformed/conflicting evidence, or an uncertain result requires `refund_review`. A process crash also leaves the durable claim in place. None of these states permits another refund POST. The marker blocks a repeated attempt even if an operator mistakenly restores the old `needs_review` status.

Sales may remain disabled during incident refunds. The command uses test keys by default; live keys require `--allow-live`, which acknowledges **separate owner/operator approval**, not a replacement for that approval. Do not run a live refund while validating this code.

## Read-only recovery

Use `python manage.py reconcile_refund <order-uuid>` when a refund ID was recorded. After a timeout that returned no ID, find the refund in the gateway's operator interface, verify its payment, and run `python manage.py reconcile_refund <order-uuid> --refund-id <verified-id>`.

Reconciliation only performs GET requests. It validates refund ID, linked payment ID, exact full amount and currency before changing local state. A supplied ID cannot overwrite an existing different binding. Repeated identical completion is idempotent; conflicting evidence cannot downgrade a completed refund. Partial refunds remain a manual accounting case. The command never captures payments, repeats refunds, changes registrar state, or clears the attempt timestamp.

Do not delete the intent marker or make a second POST after an ambiguous result. Reconcile the gateway's refund ledger first. Missing credentials/network access should be repaired without issuing another financial request. Logs and audit outcomes exclude payment payloads, private customer data, provider exception text and credentials.

## Reuse and verification

**REUSE:** existing `requests` and Django transaction/constraint facilities, with their existing licenses and no copied upstream code. **BUILD:** the application's durable refund-attempt state and operator guardrails; no external payment framework or new dependency is introduced. API paths follow the [official Razorpay refund API](https://razorpay.com/docs/api/refunds/) and read-only [payment/order resources](https://razorpay.com/docs/api/payments/); isolated fixtures do not prove live or sandbox contract compatibility.

Automated tests cover command flags, duplicate attempts, POST timeouts, process-safe claims, PostgreSQL concurrency, domain ownership, false/refunded evidence, and GET-only reconciliation. Real Razorpay test-mode settlement, webhooks, partial-refund accounting, operator drills and live approval remain separate acceptance gates. Apply migration `0003` before using the new state fields. Retain these additive fields and the claim data on rollback; old refund code must not be restored over unresolved attempts.
