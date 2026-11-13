# M3-08 — signed Razorpay webhook redelivery safety

Status: **local implementation and synthetic test coverage only**. M3-08 remains open until the actual Razorpay test-mode delivery, retry, and out-of-order flow is exercised and recorded. No live purchases, provider credentials, or registrar operations are part of this change.

## Why this was necessary

An authenticated `payment.captured` message can arrive while its gateway order ID is not yet attached to the local `DomainOrder` (for example after an interrupted checkout creation or an unexpected event ordering). Previously an unknown capture was permanently stored with outcome `ignored`; a repeat of the same signed event could not recover the payment record. Invalid but correctly signed JSON structures could also cause unhandled exceptions.

The webhook now preserves an unmatched event with `unmatched_payment_review`, and accepts a **byte-identical, correctly signed** replay of an event with the same event ID if its previous outcome was unmatched. Historical captured events with outcome `ignored` are also eligible for an authentic replay. A replay with the same event ID but a different body digest is refused.

The replay must **still** satisfy the local order ID, captured status, **server-stored** INR amount and currency, and gateway payment ID checks. The only automatic change allowed is `awaiting_payment -> paid`, accompanied by one audit entry. The webhook never initiates domain fulfillment. An exact repeat after successful capture returns `duplicate`; the same payment on a second event ID returns `already_recorded` with no second capture. A different payment ID on an already-paid order is flagged for review.

Malformed signed JSON/shape returns HTTP 400 before writing a payment event. The original HMAC validation, event ID uniqueness and SHA-256 checks remain in effect.

## How operators investigate

1. Search read-only Django admin's `PaymentEvent` list for `unmatched_payment_review`. Determine whether the gateway order ID was ever persisted and whether the order is still awaiting payment. Do not infer a successful payment from the browser callback.
2. Independently verify the payment and its correct gateway order/amount/currency in the **Razorpay test dashboard/API**. Wrong amounts, second payment IDs, missing local orders or refunded/in-flight operations require separate financial reconciliation.
3. If the original signed event is genuinely redelivered by Razorpay, it can now reconcile the local awaiting order. The same signed body and event ID must be used for the replay case; a different Razorpay-generated event ID is handled by normal payment-idempotency checks.
4. Never manufacture a webhook signature, force-update `DomainOrder.status`, or register a domain to resolve uncertainty. If an authentic event cannot be redelivered or the gateway order is unknown, escalate to the M3-09 manual gateway-reconciliation workflow. Record the gateway evidence in an access-controlled incident ticket, not this repository.
5. Keep `FULFILLMENT_ENABLED=false` during testing. A paid status is *not* registration confirmation.

**Limitation:** only the signed body hash and event metadata are stored, not full webhook bodies or payment identifiers for unknown orders. The application cannot replay a historical event by itself. There is no automatic poller or payment state transition from the Razorpay REST API in this change. Rate limiting, finance ledgers, refunds, real test-mode delivery and out-of-order webhook evidence remain separate tasks.

## Tests and review gate

```bash
DJANGO_DEBUG=true python manage.py test shop.test_webhook_replay
DJANGO_DEBUG=true python manage.py test shop
DJANGO_DEBUG=true python manage.py check
DJANGO_DEBUG=true python manage.py makemigrations --check --dry-run
```

The new test suite has synthetic valid HMAC fixtures for:
- capture arriving before local order mapping and its exact signed redelivery;
- missing/incorrect amount, currency or captured status;
- malicious event ID reuse with different bytes; second event ID with the same payment;
- a second **different** payment on the same order;
- authorized event before captured event;
- malformed signed JSON, bad signatures and missing event headers through the actual HTTP endpoint;
- simultaneous capture delivery against PostgreSQL row locks.

**External release verification:** In a dedicated Razorpay test account, capture and record a genuine webhook with confidential credentials securely configured, then test retry/out-of-order behavior under a staging URL with no live domain registrations. Verify exactly one paid transition, only one audit entry, correct provider event IDs, and no registrar API call. Link test-mode logs/CI run to the issue and only then consider M3-08 complete. This documentation does not claim any external delivery occurred.

## Reuse assessment

**REUSE:** Django 5.2 transactional row locks, uniqueness constraints, Django test client and built-in HMAC utilities already in the repository. **ADAPT:** the existing application-specific webhook state machine rather than importing a second payment stack or external webhook library. Django is BSD-3-Clause, as recorded in the project dependency/license review. The change introduces no new packages, infrastructure or stored personal data.
