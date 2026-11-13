# Fulfillment recovery — M4-08 / issue #12

## State and identity rules

The worker commits a durable `paid → processing` claim before any registrar write. A second worker cannot repeat the operation. Running inside a caller's ordinary transaction is rejected before external calls. Provider initialization failures, malformed responses, transport uncertainty and unverifiable identity/date results move the order to manual review with sanitized audit evidence.

Contact-handle creation is serialized per customer so different paid domain orders do not concurrently create conflicting handles. The handle remains that customer's own registrant handle. Registration retains any known returned registrar ID before the subsequent GET. Completion requires a read-back matching domain name, registrar ID and owner handle; `ACT` and a valid returned expiry are required for active completion. Pending status remains review. No local expiry is guessed.

Renewal requires a known baseline expiry and matching ownership before the POST. It becomes complete only after an authoritative GET confirms the same domain/ID/owner, active status and an expiry strictly greater than the baseline. Missing, unchanged or decreasing dates and explicit pending results remain review. Neither a timeout nor review state automatically reissues a registration/renewal.

## Stale worker escalation

```sh
python manage.py mark_stale_orders --minutes 30 --limit 100
```

Schedule this command and alert on its `stale_fulfillment_review` audit rows. It locks and escalates only stale `processing` orders; it never moves orders to paid or calls a provider. Minimum age is five minutes and maximum batch size is 1,000. Choose a threshold longer than normal provider timeouts. Re-running does not duplicate an escalation.

A worker returning after escalation cannot silently mark the order active. Known result IDs are retained for an operator; the order remains review. A late success or a stalled process is not evidence that refunding is safe. Confirm the actual registrar transaction before any refund.

## Read-only registration reconciliation

```sh
python manage.py reconcile_registration <local-order-uuid> --provider-id <verified-registrar-id>
```

This command requires a captured-payment registration in review, the customer's known handle, no refund attempt and a consistent registrar ID. It performs GET only and validates the active registrar identity/expiry before creating or updating the local managed-domain record. It rejects cross-customer collisions, wrong domains/handles, conflicting IDs and unconfirmed results. Repeated completed reconciliation makes no new provider request. Live-origin lookup requires explicit `--allow-live` after appropriate approval; development used no live credentials or requests.

An uncertain renewal without adequate dated evidence still requires a human to reconcile before changing local state. There is no generic reset-to-paid/retry command. Do not invent provider IDs, dates or registry status to complete a workflow.

## Reuse and remaining verification

**REUSE:** Django durable transactions, row locks and ORM constraints (BSD-3-Clause), the existing Requests adapter (Apache-2.0), and Openprovider's official response contract. **BUILD:** application-specific claim/escalation/identity policy; no separate queue framework, backend or new paid dependency. See [provider compatibility evidence](PROVIDER_COMPATIBILITY.md).

Fixtures exercise provider initialization failure, registration/renewal timeouts, pending/malformed/mismatched results, expiry checks, concurrent workers, serialized customer handles, late completion and read-only recovery. Real Openprovider sandbox acceptance, operator alert routing/on-call drills, and production deployment remain unverified; M4-07/M4-08/M5-09 remain acceptance gates.

Local checkpoint: the complete PostgreSQL 16 suite executed **142 tests with zero failures or skips**, including 19 adapter tests and 23 fulfillment/recovery tests. Migration checks, compilation and diff checks passed. No actual domain was registered or renewed.
