# Codex/Astra engineering instructions for this repository

## Goal
Build an actual, secure domain reseller service, NOT a mock or demo. Read `docs/PROJECT_GOAL.md`, then `docs/TASKS.md`; complete one P0 task at a time.

## Non-negotiable safety rules
- NEVER commit credentials, personal customer data, cloud IAM keys, `.env`, test card details or webhook secrets.
- NEVER deploy, turn on `SALES_ENABLED` or `FULFILLMENT_ENABLED`, switch live Razorpay keys, top up registrar credit, or perform live domain purchases without the repository owner's explicit approval and appropriate operator review.
- Do not use a test payment provider against a live registrar or live payment with sandbox registrar.
- Never mark orders paid from checkout JS callback; only Razorpay signed captured webhook and matching server-side order amount.
- Never auto-retry a registration/renewal with an uncertain registrar result. Reconcile first.
- Never set a customer domain's owner handle to the reseller's generic handle.
- Ensure Django authorization and CSRF checks for every state-changing customer endpoint.
- All paid workflow changes must have tests for duplicates, timeouts, race conditions, and tenant isolation.

## Definition of a completed PR
One task ID + focused diff + migration if needed + test coverage + docs update + reported risks + evidence that `python manage.py test shop` and CI passed. Mark a checkbox `[x]` only after acceptance criteria actually pass and document which environment was used. If dependencies/network are missing, say tests are unrun; do not claim passing results.

## Suggested first sequence
M0-09 (run CI), M1-08 (email resend), M3-08 (sandbox webhook), M4-07 (sandbox registrar), M5-05 (distributed throttle), M5-07 (restore), M3-09 (payment reconciliation), M3-10 (invoices/tax policy), M6-04 (acceptance suite).

## Reuse-first instruction: reduce Codex credit usage
Read `docs/REUSE_FIRST_STRATEGY.md` before creating any major feature. Search the selected foundation for existing code and connectors. For every proposed feature explicitly classify it as `CONFIGURE`, `REUSE`, `ADAPT`, or `BUILD`; include upstream link, license, risk and evidence. Do not rewrite a mature built-in module just to produce more code.

**Architecture decision gate:** the current repository is Django. A potential PNLCS adoption would switch to Laravel and MySQL, NOT combine two incompatible backends. Before such a migration, write an ADR comparing the paths and request the owner's explicit approval. Never claim an upstream module is production-ready without sandbox and security validation. Flag Openprovider `/v1beta` vs current `/v1` compatibility as a blocking verification task.

## Current official repository

`renoukhan39-bit/domain-reseller` is canonical. Read `docs/START_HERE.md` first. The default architecture is the existing Django modular application; adopting PNLCS or merging upstream source requires an explicit owner-approved decision.
