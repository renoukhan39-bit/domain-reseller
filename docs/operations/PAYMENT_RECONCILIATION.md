# Payment reconciliation — M3-09 / issue #9

## Implemented boundaries

The server reserves a local order before creating a Razorpay order. PostgreSQL partial unique indexes permit one unresolved registration per domain and one pending renewal per managed domain, across customers, workers, and checkout keys. The original per-customer idempotency constraint remains. Invalid operations, nonpositive prices, inactive/wrong-owner renewals and malformed gateway responses fail closed. The checkout UI also honors the sales switch.

Only a correctly signed `payment.captured` webhook with matching gateway order, captured status, full integer amount, currency and payment identifier can mark an order paid. Authorized, failed, partial, malformed or conflicting events cannot fulfill an order. Later events never move a paid/processing/completed/refund order back to awaiting payment.

New webhook records retain only gateway order ID, payment ID, amount, currency and captured status alongside the original digest; raw customer payloads are not stored. Early events become `waiting_order`. Binding the gateway order after checkout automatically replays retained signed evidence. Identical webhook redelivery is safe, including simultaneous requests; a changed body under the same event ID is rejected. Payment IDs cannot be assigned to two customers' orders.

If gateway creation times out, the order goes to manual review and the original checkout key never issues another POST. Find its gateway order using the local UUID as the Razorpay receipt; do not create a replacement order blindly.

## Operator commands

Run from the application directory with the correct environment and migrations applied:

```sh
# Only local, previously verified signed evidence; no external calls:
python manage.py reconcile_payment_events
python manage.py reconcile_payment_events --order-id <local-order-uuid>

# Read-only gateway GET, strict receipt/amount/currency/ID matching:
python manage.py reconcile_payment <local-order-uuid> --gateway-order-id <order_id>
```

`reconcile_payment` may restore an uncertain *checkout-initiation* order to awaiting payment only if it has no captured-payment, registrar or refund evidence. A fetched gateway status of `paid` is not sufficient to mark the local order paid: retained signed capture evidence is still required. There is no browser/operator shortcut to bypass that requirement. Live-key reads require an explicit `--allow-live` operator acknowledgement after appropriate approval; no live operation was performed during development.

For older ignored events that retained only a digest, request actual Razorpay webhook redelivery. The matching fresh HMAC and digest allow the upgraded handler to retain and replay evidence. A digest alone cannot reconstruct a capture. Unmatched/mismatched payments remain manual review rather than guessed successful payments. Reconcile refunds separately using [REFUNDS.md](REFUNDS.md).

## Migration and operations

Migration `0003` adds refund-attempt state, minimal event evidence and database constraints. It checks existing order conflicts before installing constraints and stops without deleting/changing orders if conflicts exist. An operator must reconcile duplicates, invalid amounts or unsupported currencies before retrying migration. Do not resolve financial collisions by deleting paid orders. Old refund rows without an attempt marker require manual review; do not invent historical intent.

Monitor waiting/unmatched/conflicting events and review orders. Replay commands can be scheduled, but they never retry a registrar write, gateway order creation, charge, or refund. Database uniqueness remains effective across multiple workers. Keep sales/fulfillment disabled until actual test-mode webhook and registrar sandbox acceptance passes.

## Reuse and verification

**REUSE:** existing Django transactions, row locks and unique constraints (BSD-3-Clause) and the existing Requests transport (Apache-2.0); no new runtime dependency or copied upstream code. **BUILD:** application-specific reconciliation/state-transition policy. Razorpay's documented read-only order/refund APIs remain behind the current adapter, with TLS verification, bounded timeouts, safe identifiers and no redirects. No new payment SDK or separate backend is introduced.

Automated fixtures exercise duplicate/out-of-order events, malformed signatures/payloads, early captures, timeout recovery, tenant isolation and PostgreSQL races. These validate application logic, not actual Razorpay sandbox delivery or settlement. Production approval, financial/legal review and live reconciliation remain outside this change.

Local evidence: Django checks and migration checks passed; the complete PostgreSQL 16 suite executed **100 tests with zero failures or skips**, including payment, checkout, refund and email-verification concurrency tests. Compilation and diff checks passed. Actual gateway sandbox settlement remains unverified.
