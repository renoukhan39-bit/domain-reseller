# Developer checklist — 66 tasks, 20 release acceptance tests

**Status legend:** `[x]` = source/configuration written in this package (not equivalent to successful sandbox or production testing); `[ ]` = not complete. **No end-to-end provider, payment, cloud or CI test is claimed as executed.** Each task has an owner (ENG engineer, OPS operations, BIZ business owner) and a concise exit condition. Priority P0 blocks launch, P1 is needed before scale, P2 is expansion.

## M0 — Foundation (10)

- [x] **M0-01** (ENG/P0) Set up Django 5.2-based application and dependency manifest — project starts with `manage.py`.
- [x] **M0-02** (ENG/P0) Add PostgreSQL configuration — runtime requires Postgres outside local debugging.
- [x] **M0-03** (ENG/P0) Add Dockerfile and local Compose — web, DB, worker defined.
- [x] **M0-04** (ENG/P0) Add environment template and secret exclusions — no actual secrets in Git.
- [x] **M0-05** (ENG/P0) Add fail-closed payment and fulfillment feature switches — defaults false.
- [x] **M0-06** (ENG/P0) Add database schema migration — initial tables and constraints included.
- [x] **M0-07** (ENG/P0) Add automated GitHub Actions pipeline — install, checks, migrations, tests.
- [x] **M0-08** (ENG/P0) Add product goal, architecture and runbook — docs in `docs/`.
- [ ] **M0-09** (ENG/P0) Run CI successfully after GitHub push — [main-branch CI passed](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43452225170); confirm the required PR check also runs green before marking fully accepted.
- [ ] **M0-10** (OPS/P0) Provision secure stage in eligible cloud — stage TLS URL and restricted DB verified.

## M1 — Customer identity and registrant data (9)

- [x] **M1-01** (ENG/P0) Sign-up with email and strong password — account stays inactive until verified.
- [x] **M1-02** (ENG/P0) Time-limited signed email verification — expired/forged link denied.
- [x] **M1-03** (ENG/P0) Sign-in/sign-out using Django authentication — no anonymous order access.
- [x] **M1-04** (ENG/P0) Email-based password reset — reset token uses Django auth.
- [x] **M1-05** (ENG/P0) Collect actual registrant identity/address/phone — profile saved per user.
- [x] **M1-06** (ENG/P0) Enforce domain/order ownership in views — cross-account detail returns 404.
- [x] **M1-07** (ENG/P0) Create real registrar customer handle — registrant owns their domain.
- [ ] **M1-08** (ENG/P0) Add email verification resend and provider-backed email delivery — resend, single-use expiring tokens, database throttles and SMTP configuration implemented; real provider delivery remains unverified. See `EMAIL_VERIFICATION.md`; retain this open acceptance gate until real SMTP is tested.
- [ ] **M1-09** (ENG/P0) Provide lawful data export/correction/erasure workflows and privacy notices — jurisdiction-reviewed process.

## M2 — Search, prices and storefront (9)

- [x] **M2-01** (ENG/P0) Validate supported ASCII domains — reject bad names and unsupported multi-part suffixes.
- [x] **M2-02** (ENG/P0) Query Openprovider availability live — no fabricated search results.
- [x] **M2-03** (ENG/P0) Reject premium-priced names from fixed-price checkout — no below-cost premium sale.
- [x] **M2-04** (ENG/P0) Configure TLD registration and renewal pricing in admin — disabled until operator enables.
- [x] **M2-05** (ENG/P0) Display INR price in simple responsive pages — user sees price before paying.
- [x] **M2-06** (ENG/P0) Compute order amount on server — no browser-submitted amount trusted.
- [ ] **M2-07** (BIZ/P0) Collect real wholesale costs, payment fees and taxes for each TLD — profit margin verified.
- [ ] **M2-08** (ENG/P1) Sync price/currency changes from supplier and detect premium restrictions — mismatches alert operator.
- [ ] **M2-09** (ENG/P1) Handle IDNs and multi-part suffixes after registry-specific validation — tests for `.co.uk`, etc.

## M3 — Checkout, payment and refunds (10)

- [x] **M3-01** (ENG/P0) Create local UUID orders with per-user idempotency key — retries identify same purchase.
- [x] **M3-02** (ENG/P0) Create Razorpay Orders server-side — gateway gets verified server amount.
- [x] **M3-03** (ENG/P0) Display Razorpay checkout button — customer pays through hosted payment UI.
- [x] **M3-04** (ENG/P0) Verify raw-body webhook HMAC — invalid signatures blocked.
- [x] **M3-05** (ENG/P0) Match captured payment order, amount and currency — mismatches never fulfill.
- [x] **M3-06** (ENG/P0) Store webhook event IDs and prevent duplicate capture — unique event constraint.
- [x] **M3-07** (ENG/P0) Build manual refund command, restricted by status — explicit external reconciliation required.
- [ ] **M3-08** (ENG/P0) Prove sandbox webhook delivery, retries and out-of-order events — test-mode evidence.
- [ ] **M3-09** (ENG/P0) Add explicit gateway reconciliation for stuck/unmatched payments and refund states — local signed-event replay, receipt-checked gateway lookup and durable refund lifecycle implemented; real test-mode gateway evidence remains outstanding. See `PAYMENT_RECONCILIATION.md` and `REFUNDS.md`.
- [ ] **M3-10** (BIZ/P0) Add tax-compliant receipts/invoices, refund/terms pages, business/KYC approvals — sign-off.

## M4 — Registrar operations (10)

- [x] **M4-01** (ENG/P0) Authenticate Openprovider via HTTPS bearer token — cache token securely.
- [x] **M4-02** (ENG/P0) Register domain after paid status with owner handle — provider ID stored locally.
- [x] **M4-03** (ENG/P0) Process renewals for owned domains only — expiry fetched from registrar.
- [x] **M4-04** (ENG/P0) Allow authenticated nameserver updates — registry PUT, audit entry.
- [x] **M4-05** (ENG/P0) Require explicit worker enablement — no automatic live calls by default.
- [x] **M4-06** (ENG/P0) Avoid blind retries on uncertain registrar response — manual review state.
- [ ] **M4-07** (ENG/P0) Prove Openprovider sandbox availability/contact/register/renew/NS workflow — verified IDs.
- [ ] **M4-08** (OPS/P0) Add API timeout/crash reconciliation and monitor stuck `processing` orders — durable claims, stale escalation and read-only registration reconciliation implemented with local fixtures; sandbox/operator drills outstanding. See `FULFILLMENT_RECOVERY.md`.
- [ ] **M4-09** (ENG/P1) Support transferred-in domains and EPP auth codes — ownership verified.
- [ ] **M4-10** (ENG/P1) Add domain lifecycle synchronization, expiry notices and renewability checks — schedule tested.

## M5 — Security, ops and reliability (9)

- [x] **M5-01** (ENG/P0) Secure cookies, TLS redirects and CSRF production settings — default protections present.
- [x] **M5-02** (ENG/P0) Record account/payment/registrar actions in audit table — traceable events.
- [x] **M5-03** (ENG/P0) Add basic input and per-process request throttles — code present; not sufficient for distributed prod.
- [x] **M5-04** (ENG/P0) Add DB-backed health check — non-200 if database down.
- [ ] **M5-05** (OPS/P0) Implement shared Redis/WAF throttling including login, SMTP abuse and bots — shared PostgreSQL application budgets implemented and concurrency-tested for login/reset/verification/customer actions; production edge/bot controls and load acceptance remain outstanding. See `THROTTLING.md`.
- [ ] **M5-06** (OPS/P0) Configure secret storage, role access, encryption, network rules and TLS — security review passes.
- [ ] **M5-07** (OPS/P0) Set up encrypted backups, recovery drills, alerts and provider incident monitoring — encrypted local PostgreSQL backup/empty-target restore tooling and isolated synthetic-data recovery drill verified; production offsite retention, alerts and clean staging acceptance remain outstanding. See `BACKUP_RESTORE.md`.
- [ ] **M5-08** (ENG/P0) Conduct adversarial auth/payment/provider review and dependency scanning — no critical findings.
- [ ] **M5-09** (OPS/P0) Add multi-worker crash recovery/manual review alerts and a reconciliation SOP — read-only JSON backlog monitor with nonzero alert exit and privacy-safe operator SOP added; deployment alert routing and actual on-call drill remain pending. See `RECONCILIATION_MONITORING.md`.

## M6 — Production and scale (9)

- [ ] **M6-01** (BIZ/P0) Validate registrar reseller and merchant eligibility, contracts and customer identity policy — approvals recorded.
- [ ] **M6-02** (BIZ/P0) Establish supplier funding and money-flow settlement plan — no negative-margin orders.
- [ ] **M6-03** (OPS/P0) Confirm cloud credit validity, quotas, AWS Budgets notifications and domain/DNS TLS — no surprise spend.
- [ ] **M6-04** (ENG/P0) Pass 20 release acceptance tests below — artifacts and screenshots attached to PR.
- [ ] **M6-05** (OPS/P0) Run supervised real customer payment and live registration only after sign-off — reconcile both providers.
- [ ] **M6-06** (OPS/P0) Rehearse disable/rollback, webhook replay and refund incident — operations sign off.
- [ ] **M6-07** (ENG/P1) Add DNS records dashboard, DNSSEC controls and proper propagation checks — no unauthorized changes.
- [ ] **M6-08** (ENG/P1) Build support, reporting, customer receipts and admin reconciliation dashboards — accurate ledger.
- [ ] **M6-09** (BIZ/P2) Expand eligible TLDs, currencies, localizations and transfer support — reviewed launch gates.

---

## 20 release acceptance tests — all require execution evidence

- [ ] **AT01:** CI clean checkout installs and all Django checks pass on PostgreSQL 16.
- [ ] **AT02:** Empty DB migrates forward and new deploy creates no test pricing.
- [ ] **AT03:** Sign-up sends real email and unverified user cannot log in.
- [ ] **AT04:** Expired or tampered activation link is rejected.
- [ ] **AT05:** Login, logout and password reset work with real email delivery.
- [ ] **AT06:** User B cannot read or modify User A's orders/domains.
- [ ] **AT07:** Search supported free name returns provider result; taken name cannot be ordered.
- [ ] **AT08:** Premium/unknown/unsupported domain response cannot start fixed-price checkout.
- [ ] **AT09:** Tampered client amount or repeated checkout request does not reduce payable amount / duplicate charges.
- [ ] **AT10:** Razorpay test-order checkout returns a valid gateway order ID and amount.
- [ ] **AT11:** Wrong webhook signature, wrong amount, wrong currency and unknown order do not fulfill.
- [ ] **AT12:** Duplicate/replayed/out-of-order payment events do not provision twice.
- [ ] **AT13:** Paid sandbox registration creates real registry ID and correct customer registrant handle.
- [ ] **AT14:** Registrar timeout/uncertainty never triggers blind duplicate registration.
- [ ] **AT15:** Registry `REQ`/pending response does not falsely display an active completed purchase.
- [ ] **AT16:** Renew a domain and verify expiry from Openprovider, not locally derived.
- [ ] **AT17:** Change two nameservers as owner; other users rejected; registrar confirms change.
- [ ] **AT18:** Refund command requires external reconciliation; refund ID and settlement are reconciled.
- [ ] **AT19:** Restore encrypted PostgreSQL backup in clean staging, validate ownership and orders.
- [ ] **AT20:** Live deployment passes HTTPS, monitoring, rate limit, email, legal/finance approval and rollback drills.

## Developer handoff rules

Each incomplete task must result in: a focused branch/PR, tests for success+failure, updated docs and an explicit risk statement. Do not enable live payment or registration in a development PR. Start with **M0-09**, then M1-08, M3-08, M4-07 and the remaining P0 launch blockers. The task list is a roadmap and is not evidence of a completed production integration.
