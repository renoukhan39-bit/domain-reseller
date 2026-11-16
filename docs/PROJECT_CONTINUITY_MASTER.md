# DOMAIN RESELLER — MASTER PROJECT CONTINUITY RECORD

**Canonical repository:** https://github.com/renoukhan39-bit/domain-reseller  
**Last consolidated:** 2026-11-16 (Asia/Kolkata)  
**Document purpose:** make the project understandable in a **brand-new ChatGPT, Codex, or human developer session without loading earlier chats**.  
**Information status:** evidence-based snapshot, not an always-current GitHub API response or a production acceptance certificate.

> **NEW DEVELOPER / NEW CHAT START HERE:** Read this document, then [AGENTS.md](../AGENTS.md), [START_HERE.md](START_HERE.md), [TASKS.md](TASKS.md), [FEATURE_MATRIX.md](FEATURE_MATRIX.md), and the latest open PRs. Verify the branch head and code before making changes. Existing code and docs, not remembered chat, are the project source of truth.

## 0. What has and has not been archived

This is a **consolidated record of the project-specific conversation context available when prepared**, including earlier conversation summaries, the owner's detailed master engineering brief, code and research findings, architectural decisions, links, diagrams, completed GitHub actions and remaining work. It **is not a word-for-word export of every previous ChatGPT conversation**: the model cannot access older complete transcripts when they are outside the provided context. Unseen prior messages, images, attachments and private assistant reasoning are not fabricated. Full verbatim archives require the owner to export the original conversations and add their records separately after checking for secrets and personal information.

This document is intentionally durable and redundant **only as a navigation index**: canonical specifications, full test lists, runbooks and long research reports remain in linked files. Do not create competing business rules here. If code or upstream provider contracts change after the snapshot, update the authoritative file and link/summary.

## 1. Project mission, ownership and explicit decisions

**Goal:** Build an independently operated, commercial domain reseller and web-services platform aspiring to GoDaddy/Namecheap customer experience and WHMCS-class backend operations. It is a **reseller integrating existing accredited registrars** initially, **not** an ICANN-accredited registrar. The owner and Codex are the primary development team. The platform should be secure, commercially usable, inexpensive to maintain, expandable, independently branded, and **real—not a mock website or superficial prototype**.

**Independent control means** ownership/control of original source, brand, customer data, deployment, infrastructure, configuration and properly licensed dependencies. It does not mean exclusive ownership of MIT/open-source upstream code, commercial provider APIs, registry infrastructure or third-party software.

### Architecture decision (current approved default)

| Dimension | Selected | Rejected without a new approved ADR |
| --- | --- | --- |
| Backend | Django/Python, existing shop application | PHP/Laravel backend replacement by assumption |
| Database | PostgreSQL | Parallel MySQL source of truth |
| Organization | Modular monolith, single canonical repository | Microservices/Kubernetes by fashion |
| Frontend | Django server-rendered initially | React/SPA rewrite without need |
| Payments | Existing Razorpay Orders + signed payment.captured handling | Duplicated checkout backend |
| Registrar | Existing Openprovider REST adapter over HTTPS /v1 | Copying PHP/WHMCS code into Django |
| Async work | Existing DB-backed fulfillment command/worker | Blind automatic retries on money/registrar writes |
| DevOps | Docker/Compose, GitHub Actions, Python 3.12, PostgreSQL 16 | Live cloud deployment or spending without approval |

**Recommendation from research:** retain Django. PNLCS has broader modules but migration would require legal, billing/data migration, payment-security parity, provider verification, rollback and operations work. No such migration has been approved.

**Absolute safeguards:** keep SALES_ENABLED=false and FULFILLMENT_ENABLED=false by default. Never use live Razorpay with sandbox registrar or test Razorpay with live registrar. Never create, renew, transfer, refund, or retry uncertain financial/registrar writes automatically based on browser evidence. Do not buy domains, top up accounts, deploy paid cloud resources, merge PRs, expose real contact data, or change production settings without explicit authorization appropriate to the action.

## 2. Full provenance: conversation and decision timeline

The project conversation summaries available for this consolidation identify these exchanges:

| Date (IST) | Known conversation/topic | Persisted understanding |
| --- | --- | --- |
| 2026-11-13 ~10:47 | “Domain Reseller Implementation Plan” | Owner asked whether one repository or a combination is best, wanted a **fully owned original software platform** competing with the market leaders, sought public repositories Codex could study to save credits, designated the canonical GitHub repo, and requested a Codex implementation prompt. |
| 2026-11-13 ~12:33 | “Project Goal Strategy” | Asked how to achieve the overall commercial project goal. Key decision became reliable staged construction rather than building every feature at once. |
| 2026-11-14 ~03:28 | “Implementing Domain Reseller” | Asked to inspect activated branch, start implementing, check open PRs and merges, and push a .txt inventory of previously recommended public repositories to the same repo. The tracked inventory is [REPOSITORIES_TO_STUDY.txt](REPOSITORIES_TO_STUDY.txt), compiled 2026-11-15. |
| 2026-11-15 | Long “MASTER ENGINEERING PROMPT — DOMAIN RESELLER PLATFORM” | Owner directed inspection of 15 named repo documents, **exactly two** primary upstream studies (PNLCS and official Openprovider WHMCS domains module), thorough code/security audit, pragmatic roadmap, one focused P0 implementation, tests, docs and a feature-branch PR **without merging**. The directive's requirements are consolidated in sections 3–13 below and in the linked full research reports. |
| 2026-11-15 GitHub changes from prior assistant turn | Focused M5-08 hardening | The nameserver mutation guard, 10 targeted offline tests and three research documents were committed to feature branch and opened as [PR #34](https://github.com/renoukhan39-bit/domain-reseller/pull/34). CI passed; PR remained open/unmerged at last check. |
| 2026-11-16 | “Push all the detail, all the document, all the chart, all the link as a doc file in our GitHub repo” | Owner prioritized **persistent continuity** so a fresh ChatGPT/Codex session does not need prior chat history. This master record and onboarding links satisfy that objective. |

**Important limitation:** these are faithful summaries of the available recent project context, not full verbatim chat logs. No conversation older than the available summaries has been reconstructed.

## 3. Canonical source of truth and complete document directory

**Repository:** [renoukhan39-bit/domain-reseller](https://github.com/renoukhan39-bit/domain-reseller)  
**Snapshot default branch:** main at [6b522210ee47a38abc14868b0f26dcabc910dd83](https://github.com/renoukhan39-bit/domain-reseller/commit/6b522210ee47a38abc14868b0f26dcabc910dd83) (checked 2026-11-16).  
**Outstanding M5-08 branch:** fix/M5-08-nameserver-registrar-identity at [4f65433d27adbffddcc5bfa438cdaaebb4e2ff6a](https://github.com/renoukhan39-bit/domain-reseller/commit/4f65433d27adbffddcc5bfa438cdaaebb4e2ff6a), [PR #34](https://github.com/renoukhan39-bit/domain-reseller/pull/34). The three audit docs below are in **PR #34 branch**, not yet on main. Always inspect the latest state; the pinned snapshot can age.

### Core planning documents (already on main)

- [README](../README.md) — overview and local setup.
- [AGENTS.md](../AGENTS.md) — non-negotiable instructions for all coding agents.
- [START_HERE.md](START_HERE.md) — onboarding and source-of-truth pointers.
- [PROJECT_GOAL.md](PROJECT_GOAL.md) — charter and release definition of done.
- [ROADMAP.md](ROADMAP.md) — releases R0–R4.
- [FEATURE_MATRIX.md](FEATURE_MATRIX.md) — written/tested/missing distinctions.
- [TASKS.md](TASKS.md) — **66 named tasks** across M0–M6 plus **20 release acceptance tests AT01–AT20**.
- [ISSUE_BACKLOG.csv](ISSUE_BACKLOG.csv) — source-backed task backlog and existing IDs.
- [ARCHITECTURE.md](ARCHITECTURE.md) — architecture and trust boundaries.
- [REUSE_FIRST_STRATEGY.md](REUSE_FIRST_STRATEGY.md) — CONFIGURE/REUSE/ADAPT/BUILD guidance.
- [PUBLIC_REPOSITORY_REPORT.md](PUBLIC_REPOSITORY_REPORT.md) — earlier public repository evaluation.
- [REPOSITORIES_TO_STUDY.txt](REPOSITORIES_TO_STUDY.txt) — **13 unique upstream GitHub repositories**, complete list in section 6.
- [CODEX_CLOUD.md](CODEX_CLOUD.md) — agent/Codex workflow and credit-saving instructions.
- [PROVIDER_COMPATIBILITY.md](PROVIDER_COMPATIBILITY.md) — Openprovider URL/version, response validation and remaining sandbox requirements.
- [PAYMENT_RECONCILIATION.md](PAYMENT_RECONCILIATION.md) — signed event replay, checkout uncertainty and payment reconciliation.
- [FULFILLMENT_RECOVERY.md](FULFILLMENT_RECOVERY.md) — one-shot claims, provider identity read-back and uncertain outcomes.
- [REFUNDS.md](REFUNDS.md) — operator-only refund intent and read-only reconciliation.
- [EMAIL_VERIFICATION.md](EMAIL_VERIFICATION.md) — verification resend, single-use tokens, rate limits and SMTP.
- [THROTTLING.md](THROTTLING.md) — shared PostgreSQL throttles.
- [RECONCILIATION_MONITORING.md](RECONCILIATION_MONITORING.md) — backlog monitoring and escalation.
- [BACKUP_RESTORE.md](BACKUP_RESTORE.md) — encrypted backups, synthetic drill, staging limitations.
- [DEPLOYMENT.md](DEPLOYMENT.md) — deployment and security controls.
- [PROVIDER_SETUP.md](PROVIDER_SETUP.md) — credentials and paired environments.
- [FREE_RESOURCES.md](FREE_RESOURCES.md) — credits and hidden/unavoidable costs.
- [5_DAY_EXECUTION_PLAN.md](5_DAY_EXECUTION_PLAN.md) — first-stage sprint (not a full-platform launch promise).
- [PR_HANDOFF.md](PR_HANDOFF.md) — contribution and handoff requirements.
- [OWNERSHIP_AND_LICENSES.md](OWNERSHIP_AND_LICENSES.md) — upstream ownership and software licensing.
- [CONTRIBUTING.md](../CONTRIBUTING.md) and [SECURITY.md](../SECURITY.md) — contributor/security obligations.

### Detailed research completed in outstanding PR #34

- [CODEBASE_AUDIT.md — read on PR branch](https://github.com/renoukhan39-bit/domain-reseller/blob/fix/M5-08-nameserver-registrar-identity/docs/CODEBASE_AUDIT.md): source-by-source audit, evidence/severity, business-state boundaries, vulnerabilities/gaps.
- [TWO_PRIMARY_REPO_COMPARISON.md — read on PR branch](https://github.com/renoukhan39-bit/domain-reseller/blob/fix/M5-08-nameserver-registrar-identity/docs/TWO_PRIMARY_REPO_COMPARISON.md): pinned PNLCS/Openprovider code, license differences, migration decision, exact paths.
- [MASTER_BUILD_PLAN.md — read on PR branch](https://github.com/renoukhan39-bit/domain-reseller/blob/fix/M5-08-nameserver-registrar-identity/docs/MASTER_BUILD_PLAN.md): 4-phase plan plus phase 0, prioritized risks, dependencies, engineer-day **estimates** (not guarantees).
- [PR #34 review and test evidence](https://github.com/renoukhan39-bit/domain-reseller/pull/34).

## 4. Architecture diagrams — browser to ownership and revenue safety

### Diagram A: complete domain purchase (logical trust boundaries)

~~~mermaid
flowchart TD
    U[Customer browser] -->|TLS, login and CSRF| W[Django views and forms]
    W -->|Validate ASCII TLD, nonpremium| A[Openprovider availability]
    W -->|Look up configured INR price| P[(PostgreSQL TLDPrice)]
    W -->|Create UUID order and lock/unique constraints| O[(PostgreSQL DomainOrder)]
    O -->|Create server-priced order| R[Razorpay Orders API]
    R -->|Hosted checkout| U
    R -->|payment.captured webhook| H[Raw HMAC verification + event ID replay]
    H -->|Match amount, currency, gateway order + captured ID| E[(PaymentEvent and order paid)]
    E -->|Paid claim committed before API write| F[Controlled fulfillment worker]
    F -->|Create/lookup customer contact; one register/renew POST| OP[Openprovider HTTPS /v1]
    OP -->|GET identity, owner handle, status, expiry| F
    F -->|Verified active or manual review| D[(ManagedDomain + audit trail)]
    D -->|Owner-filtered dashboard| U
    F -->|Timeout, pending, mismatch| M[needs_review: read-only reconciliation; never blind retry]
~~~

### Diagram B: order life cycle and idempotency

~~~mermaid
stateDiagram-v2
    [*] --> awaiting_payment: Local order reserved
    awaiting_payment --> paid: Signed captured webhook, strict match
    awaiting_payment --> needs_review: Gateway creation uncertain
    paid --> processing: Durable worker claim
    processing --> active: Registrar identity + status + expiry verified
    processing --> needs_review: Timeout/pending/mismatch
    needs_review --> active: Operator read-only verified registration reconciliation
    needs_review --> refund_pending: Explicit verified refund attempt
    refund_pending --> refunded: Provider confirms full processed refund
    refund_pending --> refund_review: Failure/uncertainty
    refund_review --> refunded: Read-only refund reconciliation
    active --> [*]
    refunded --> [*]
~~~

Note: this is a **conceptual overview** of the existing state transitions, not a substitute for reading exact Django model and service code. Uncertain outcomes must never auto-retry a possibly successful registrar POST, payment order POST or refund POST.

### Diagram C: feature prerequisites and milestone gates

~~~mermaid
flowchart LR
    P0["Phase 0: audited Django/PG foundation"] --> P1["Phase 1: verified payment + registrar sandboxes"]
    P1 --> P2["Phase 2: margins, taxes, ledger, security, support, recovery"]
    P2 --> G{"Owner legal/ops/finance sign-off?"}
    G -->|Approved| L["Supervised limited live pilot"]
    G -->|Not approved| S["Sales/fulfillment remain OFF"]
    L --> P3["Phase 3: transfer, DNS, premium, multi-registrar, reseller API"]
    P3 --> P4["Phase 4: hosting/VPS/email/SSL/builder/ecosystem"]
~~~

## 5. Actual codebase component index

| Source path | What it does | Known gaps and recommended action |
| --- | --- | --- |
| config/settings.py | Strict Django settings, test/live pairing inputs, disabled-by-default sales gates, PostgreSQL/SQLite dev policy | CONFIGURE: TLS/proxy/SMTP/secrets/staging |
| config/urls.py, shop/urls.py | Routes for account, storefront, dashboard, payments and health | ADAPT only as feature grows |
| shop/models.py and migrations 0001–0003 | Durable contact, order, payment event, refund intent, managed-domain and audit records; uniqueness constraints | BUILD invoices/ledger and future portfolio state |
| shop/forms.py | Signup/profile, ASCII domain normalization, nameserver validation | ADAPT TLD-specific validation; don't guess IDN support |
| shop/views.py and shop/templates | Signup/login, search, buy, renew, nameserver management, user-isolated dashboard, webhook endpoint | ADAPT: PR #34 identity-read guard; invoices/support future |
| shop/email_verification.py | Single-use verification/resend tokens, SMTP helpers | CONFIGURE actual provider; no real SMTP verification yet |
| shop/middleware.py and shop/throttling.py | Shared PostgreSQL request budget counters | CONFIGURE production edge/WAF and proxy behavior |
| shop/payments.py | Razorpay Orders/refund/read-only GET, HMAC verification | REUSE, validate in test-mode |
| shop/payment_events.py | Signed captured-payment evidence, replay safety, audit, order match | ADAPT operational alerting; no browser success-as-payment |
| shop/services.py | Checkout idempotency, paid state, durable worker claims, registrar identity/read-back, no-blind-retry | ADAPT provider lifecycle as contracts verified |
| shop/providers.py | Strict Openprovider HTTPS /v1 endpoints, token cache, nonpremium availability, contact/register/renew/NS/GET | ADAPT only with official schema and sandbox tests |
| shop/refunds.py | Operator-only financial intention and reconciliation | ADAPT invoice/ledger integration, real provider settlement |
| shop/management/commands | process_orders, reconcile_payment(_events), reconcile_registration, reconcile_refund, refund_order, mark_stale_orders, check_reconciliation_backlog | CONFIGURE schedules, alerts and operator drills |
| shop/admin.py | Operator configuration and read-only financial state | ADAPT granular permissions / support |
| scripts/database_backup.py and backup_restore_drill.py | Encrypted backup tooling and isolated synthetic recovery | CONFIGURE offsite staging and real recovery drills |
| compose.yaml, Dockerfile | web, worker and PostgreSQL containers | CONFIGURE repeatable deployment and restricted DB networking |
| .github/workflows/ci.yml | PostgreSQL 16 Django checks/migrations/tests/compile and backup job | Preserve and extend verified regression tests |

**Existing proof is narrower than production readiness:** main previously passed GitHub CI and local test reports. PR #34's branch-head CI later passed **184 Django application tests**, but real gateway delivery, actual Openprovider sandbox writes, production SMTP, legal approval and live deployment have **not** been demonstrated.

## 6. All 13 previously recommended public repositories

The official list is [docs/REPOSITORIES_TO_STUDY.txt](REPOSITORIES_TO_STUDY.txt). These links are research inventory, **not** approval to copy their source or run paid services.

| # | Repository | Primary purpose | Status / caveat |
| --- | --- | --- | --- |
| 01 | [Panelica/pnlcs](https://github.com/Panelica/pnlcs) | Hosting/domain reseller platform, invoices, tickets, Razorpay and registrars | **PRIMARY DEEP STUDY #1**; MIT; Laravel/PHP, not a Django backend |
| 02 | [FOSSBilling/FOSSBilling](https://github.com/FOSSBilling/FOSSBilling) | Hosting billing, invoices and customers | Additional catalog entry only; PHP; earlier Apache-2.0 note, revalidate |
| 03 | [Paymenter/Paymenter](https://github.com/Paymenter/Paymenter) | Hosting billing/storefront and extensions | Catalog only; MIT previously noted |
| 04 | [openprovider/Openprovider-WHMCS-domains](https://github.com/openprovider/Openprovider-WHMCS-domains) | Official registrar WHMCS module | **PRIMARY DEEP STUDY #2**; root LICENSE not located in pinned tree |
| 05 | [Osir-Inc/fossbilling-osir](https://github.com/Osir-Inc/fossbilling-osir) | OSIR registrar module for FOSSBilling | Catalog only; prior research reports no OSIR sandbox |
| 06 | [getnamingo/registrar](https://github.com/getnamingo/registrar) | ICANN/EPP/RDAP registrar operations | Catalog only; not needed for ordinary reseller MVP |
| 07 | [codemec-com/domain-reseller-api](https://github.com/codemec-com/domain-reseller-api) | Cloudzaro OpenAPI/example clients | Catalog only; not a storefront |
| 08 | [upmind/provision-provider-domain-names](https://github.com/upmind/provision-provider-domain-names) | Domain provider adapter architecture | Catalog only; GPL-3.0 source reuse caution |
| 09 | [umami-software/umami](https://github.com/umami-software/umami) | Analytics | Future optional separate integration |
| 10 | [louislam/uptime-kuma](https://github.com/louislam/uptime-kuma) | Uptime/status monitoring | Future optional separate service |
| 11 | [chatwoot/chatwoot](https://github.com/chatwoot/chatwoot) | Support/chat | Future optional; enterprise licensing differs |
| 12 | [PowerDNS/pdns](https://github.com/PowerDNS/pdns) | Authoritative DNS | Later optional separate infrastructure; GPL license |
| 13 | [certbot/certbot](https://github.com/certbot/certbot) | ACME/TLS automation | Configure where useful; Apache-2.0 previously noted |

**Strict upstream study rule from the owner:** the two primary repositories are PNLCS and the official Openprovider WHMCS module; do not start a third major research investigation without a specific justified gap.

### Pinned research and key lessons

**PNLCS pinned SHA:** [beaa7ea7c91972c3380bbd233610da938c871959](https://github.com/Panelica/pnlcs/tree/beaa7ea7c91972c3380bbd233610da938c871959) (observed 2026-11-15). [MIT license](https://github.com/Panelica/pnlcs/blob/beaa7ea7c91972c3380bbd233610da938c871959/LICENSE). Source pointers:

- [RegistrarModuleInterface.php](https://github.com/Panelica/pnlcs/blob/beaa7ea7c91972c3380bbd233610da938c871959/app/Contracts/RegistrarModuleInterface.php) — per-provider operations and capabilities.
- [GatewayModuleInterface.php](https://github.com/Panelica/pnlcs/blob/beaa7ea7c91972c3380bbd233610da938c871959/app/Contracts/GatewayModuleInterface.php) — payment adapter design.
- [GatewayEvent.php](https://github.com/Panelica/pnlcs/blob/beaa7ea7c91972c3380bbd233610da938c871959/app/Models/GatewayEvent.php) — durable webhook claims and recovery.
- [ProvisionOrderedService.php](https://github.com/Panelica/pnlcs/blob/beaa7ea7c91972c3380bbd233610da938c871959/app/Jobs/ProvisionOrderedService.php) — separate jobs, one-attempt policy.
- [DomainSyncCommand.php](https://github.com/Panelica/pnlcs/blob/beaa7ea7c91972c3380bbd233610da938c871959/app/Console/Commands/DomainSyncCommand.php) — authoritative registrar state; billing due date is separate.
- [InvoiceService.php](https://github.com/Panelica/pnlcs/blob/beaa7ea7c91972c3380bbd233610da938c871959/app/Services/InvoiceService.php) and [TaxRule.php](https://github.com/Panelica/pnlcs/blob/beaa7ea7c91972c3380bbd233610da938c871959/app/Models/TaxRule.php) — future billing architecture study.
- [OpenProviderRegistrar.php](https://github.com/Panelica/pnlcs/blob/beaa7ea7c91972c3380bbd233610da938c871959/modules/Registrars/OpenProvider/OpenProviderRegistrar.php) — **do not copy** legacy HTTP sandbox, /v1beta, or locally derived renewal expiry assumptions.
- [RazorpayModule.php](https://github.com/Panelica/pnlcs/blob/beaa7ea7c91972c3380bbd233610da938c871959/modules/Gateways/Razorpay/RazorpayModule.php) — processor-specific minor units; Django should continue integer paise for INR.

**Official Openprovider WHMCS module pinned SHA:** [9bcd5198fa2c09db61faa854d029474013d7464f](https://github.com/openprovider/Openprovider-WHMCS-domains/tree/9bcd5198fa2c09db61faa854d029474013d7464f) (observed 2026-11-15). No root LICENSE was located; bundled vendor dependencies have their own separate licenses. Source pointers:

- [API/ApiV1.php](https://github.com/openprovider/Openprovider-WHMCS-domains/blob/9bcd5198fa2c09db61faa854d029474013d7464f/modules/registrars/openprovider/OpenProvider/API/ApiV1.php) — API client/transport and wrapper behavior.
- [advanced-module-configurations.php](https://github.com/openprovider/Openprovider-WHMCS-domains/blob/9bcd5198fa2c09db61faa854d029474013d7464f/modules/registrars/openprovider/configuration/advanced-module-configurations.php) — HTTPS hosts, TLD policy and sync settings.
- [DomainSyncController.php](https://github.com/openprovider/Openprovider-WHMCS-domains/blob/9bcd5198fa2c09db61faa854d029474013d7464f/modules/registrars/openprovider/Controllers/System/DomainSyncController.php) — ACT/FAI/DEL/TRAN and provider expiry.
- [NameserverController.php](https://github.com/openprovider/Openprovider-WHMCS-domains/blob/9bcd5198fa2c09db61faa854d029474013d7464f/modules/registrars/openprovider/Controllers/System/NameserverController.php) — NS workflow.
- [TldPricingController.php](https://github.com/openprovider/Openprovider-WHMCS-domains/blob/9bcd5198fa2c09db61faa854d029474013d7464f/modules/registrars/openprovider/Controllers/System/TldPricingController.php) — supplier prices and **sandbox lack of pricing** warning.
- [EppController.php](https://github.com/openprovider/Openprovider-WHMCS-domains/blob/9bcd5198fa2c09db61faa854d029474013d7464f/modules/registrars/openprovider/Controllers/System/EppController.php), [TransferSyncController.php](https://github.com/openprovider/Openprovider-WHMCS-domains/blob/9bcd5198fa2c09db61faa854d029474013d7464f/modules/registrars/openprovider/Controllers/System/TransferSyncController.php), [DnsController.php](https://github.com/openprovider/Openprovider-WHMCS-domains/blob/9bcd5198fa2c09db61faa854d029474013d7464f/modules/registrars/openprovider/Controllers/System/DnsController.php) — missing competitive functions.

**API contract authority:** [Openprovider developer portal](https://developer.openprovider.com/) (new integrations /v1), [Openprovider getting started](https://developer.openprovider.com/get-started.html), [Razorpay developer documentation](https://razorpay.com/docs/). The project's [PROVIDER_COMPATIBILITY.md](PROVIDER_COMPATIBILITY.md) records legacy /v1beta migration work and trusted sandbox HTTPS host. **Real API request/response acceptance is outstanding.**

## 7. Current implementation maturity — preserve the distinction

| Feature | Implemented in current source? | Offline tests or CI? | Real external sandbox verified? | Launch status |
| --- | --- | --- | --- | --- |
| Django / PostgreSQL, Docker/CI | Yes | Yes, GitHub Actions | N/A; independent clean Docker reproduction remains useful | Foundation, not public deployment |
| Signup, verified email and contacts | Yes | Yes | **No** real SMTP provider verification | Blocked for real user onboarding |
| ASCII supported TLD search + admin INR prices | Yes | Provider fixtures | **No** real Openprovider end-to-end run shown | No true supplier-margin proof |
| Signed Razorpay captured-payment webhook | Yes | HMAC and concurrency fixtures | **No** actual test webhook/settlement shown | Not ready for money |
| Gateway order and refund reconciliation | Partial, existing read-only tooling | Offline fixtures | **No** external acceptance shown | Manual operations/ledger required |
| Domain registration and renewal | Yes | Adapter/fulfillment fixtures | **No** real sandbox proof | Do not enable live |
| Domain owner/registrar identity read-back | Yes in fulfillment; NS hardening in PR #34 | Offline fixtures; PR CI passed | **No** live/provider acceptance shown | PR unmerged |
| Registrar NS management | Yes | Offline tenant and provider fixtures | **No** real sandbox PUT shown | Restrict until verified |
| Backups/recovery monitoring | Local tools and synthetic CI | Yes | **No** offsite staging/on-call drill | Release gate open |
| Taxes, invoice/ledger, supplier funding | Not complete | No end-to-end accounting acceptance | N/A | P0 before launch |
| Transfers, DNS records, DNSSEC, premium/IDN, reseller API | Not implemented / future scope | No accepted feature tests | No | Later phases |
| Hosting/VPS/email/SSL/site builder | Future scope | No accepted features | No | Phase 4 |

### Exact known test and GitHub evidence

- Starting main SHA: [6b522210ee47a38abc14868b0f26dcabc910dd83](https://github.com/renoukhan39-bit/domain-reseller/commit/6b522210ee47a38abc14868b0f26dcabc910dd83).
- [main push CI run 43740926271](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43740926271) — successful baseline on 2026-11-15.
- [feature branch push run 43745054673](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43745054673) — succeeded for PR #34 code and doc head; logs recorded **184 shop tests, OK**, with PostgreSQL migrations, system checks and compileall.
- [PR #34 workflow run 43745160078](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43745160078) — completed **success** for the same head; both test and backup-recovery jobs succeeded.
- [Earlier documented 166-test local PostgreSQL run](THROTTLING.md) is historical evidence and **not** a new command executed during this handoff.
- No proof was produced of a real domain registration, real Razorpay capture, real SMTP delivery, live cloud deployment, supplier-margin review or applicable legal approval. Never equate mocks with actual external integrations.

### Prior M5-08 implementation — exact files and limitation

[PR #34](https://github.com/renoukhan39-bit/domain-reseller/pull/34) adds a **focused** nameserver guard (not the entire M5-08 security audit): shop/views.py now reuses fulfillment_ready() and the existing _registrar_identity() read-back validation for NS updates. It requires matching domain ID/name/customer registrant handle/active status before the provider PUT. The new shop/test_nameserver_safety.py covers 10 paths: valid update, disabled sales, disabled fulfillment, wrong environment pairing, missing handle, wrong handle, wrong provider name/ID, pending record, provider timeout, and another user's 404. No migration or new runtime dependency. Risk: GET then PUT can race with a subsequent change at the registrar; separate maintenance-management gating is future design work.

**Branch** fix/M5-08-nameserver-registrar-identity; **head** 4f65433d27adbffddcc5bfa438cdaaebb4e2ff6a; **PR open/unmerged** at snapshot. M5-08 as a whole remains incomplete.

## 8. Top ten P0/P1 gaps and safe next actions

| Rank | Issue ID / risk | Why it matters | Dependency / acceptance |
| --- | --- | --- | --- |
| 1 | M5-08: registrar NS ownership drift (high) | Local owner alone was insufficient for current registrar state | Review/merge PR #34 only with owner approval; validate provider GET contract in sandbox |
| 2 | M0-09: repeatable clean foundation | Historical CI does not prove each new environment | Independent Docker/PG16 clean checks, migrations, test suite, startup and CI evidence |
| 3 | M4-07: Openprovider sandbox | No real end-to-end customer-owned registration/renewal and NS acceptance | Credential-controlled sandbox tests, exact IDs/handles/dates, pending and error behavior |
| 4 | M3-08/M3-09: Razorpay test mode | Real signed delivery, early/duplicate events and refunds not externally proven | Test keys, webhook secret and read-only reconciliation evidence |
| 5 | M2-07/M6-02: wholesale economics | Fixed price without validated supplier margin risks loss and failed fulfillment | Supplier price snapshot, fees, supported TLD and funding approval |
| 6 | M3-10/M6-01: legal/tax/invoicing | No approved statutory invoice, customer terms, KYC and settlement policy | Owner chooses jurisdiction, gets professional sign-off, adds immutable ledger |
| 7 | M5-09/M4-08: actionable review queue | Uncertain registrar/payment writes need staffed investigation | Scheduler, alerts, privacy-safe SOP and on-call drill |
| 8 | M5-05/M5-06/M5-08: production security | Need WAF/edge controls, secret vault, TLS, dependency and auth/provider penetration review | Protected staging and evidence; no live sales |
| 9 | M5-07/M0-10/M6-04: recovery staging | Synthetic backup tests are not offsite restoration success | Restore under staging with key rotation, access controls and rollback drill |
| 10 | M4-10 and M6-07: domain lifecycle/DNS | Missing expiry sync/reminders, transfers, DNS edit and DNSSEC | Implement read-only sync first, then narrowly authorized writes |

These are **priority and dependency recommendations**, not findings that the unavailable external systems were compromised.

## 9. Milestones, effort and operating costs

The estimates are indicative **one-engineer hands-on days**, **not dates or commitments**. They do not include waiting for provider credentials, legal reviews or external lead times. The canonical plan is [MASTER_BUILD_PLAN.md in PR #34](https://github.com/renoukhan39-bit/domain-reseller/blob/fix/M5-08-nameserver-registrar-identity/docs/MASTER_BUILD_PLAN.md).

| Phase | Scope and prerequisites | Rough incremental effort | Definition of done |
| --- | --- | --- | --- |
| 0 — audited verified foundation | Source audit, tests, migrations, CI, Docker, security defect fixes | 2–8 days | Clean PostgreSQL16 checks/tests and independent startup, defaults OFF |
| 1 — sandbox domain-selling | Phase 0 + Openprovider/Razorpay test access; signup→search→payment→registrar→dashboard + renew/NS/recovery | 10–30 days | Real provider sandbox acceptance, duplicate/timeout/concurrency/identity evidence |
| 2 — controlled business readiness | Phase 1 + wholesale costs, margins, taxes, invoices, support, settlement, backups, TLS, alerts, legal sign-off | 25–60 days + external approvals | AT01–AT20 verified where applicable, owner-approved limited go-live only |
| 3 — competitive reseller portfolio | Safe pilot + transfer, DNSSEC, premium/IDN, sync, multiple registrars, tiers, APIs and reporting | 45–110 days staged | Each new registrar/TLD/role has tested policies and financial reconciliation |
| 4 — web services | Proven core + hosting/VPS/email/SSL/site-builder/affiliate/localization/auditing | 60–180+ days iterative | Service provisioning, billing, abuse prevention and rollback demonstrated |

**Cost reality:** open source code can have no purchase price while domains need wholesale funding; payments incur processor fees; hosted email, backups, compute, monitoring, taxes/legal review and operations may cost money. AWS/Azure promotional credits, existing subscriptions or owned domains do **not** guarantee a zero-cost commercial service. No paid resources were provisioned during this research.

## 10. Security and correctness invariants

1. **Customer isolation:** authenticated owner-scoped Django queries, CSRF on customer state-changing requests, no tenant A data exposure to B. Current model is per-user ownership, not a mature organization-level multitenant product.
2. **Server price only:** use integer paise, INR and validated enabled TLD; no browser-supplied price.
3. **Payment proof:** raw-body Razorpay HMAC; exact captured state, payment/order IDs, currency and amount. Duplicate/out-of-order events and unknown orders must not fulfill.
4. **Checkout uncertainty:** local order reserved first; gateway POST timeout means manual read-only lookup by receipt. No duplicated gateway Orders POST.
5. **Registrar ownership:** customer-specific contact/owner handle; never substitute reseller's generic handle.
6. **Registrar uncertainty:** durable paid→processing claim commits before external POST; ambiguous result/pending status enters needs_review; read-only identity recovery, no automatic duplicate registration/renewal.
7. **Renewal expiry:** compare provider-verified original and new expiry; do not add a local year as proof.
8. **Refund uncertainty:** operator-only, durable attempt timestamp before gateway POST; never automatically repeat uncertain refund; match returned payment, amount, currency, status by GET.
9. **Environment trust:** HTTPS Openprovider trusted origins only, redirects disallowed, bounded timeouts, compatible test/live pairing.
10. **Customer nameservers:** local owner/status + registrar ID/name/handle/active verification before PUT (proposed PR #34); caution GET→PUT timing race.
11. **Operational security:** no credentials or PII in Git, logs/PRs or chat; trusted TLS proxy, vault/secret rotation, edge throttling, backups, alerts and legal review before launch.
12. **No overstated assurance:** CI mocks/fixtures and provider sandboxes are different; actual successful paid checkout, domain ownership and compliant invoices need explicit evidence.

Read [CODEBASE_AUDIT.md on the PR branch](https://github.com/renoukhan39-bit/domain-reseller/blob/fix/M5-08-nameserver-registrar-identity/docs/CODEBASE_AUDIT.md) for confirmed findings and proof. Do not report a hypothetical issue as a confirmed exploit.

## 11. Release acceptance test catalog — existing IDs unchanged

The complete full statements are in [TASKS.md](TASKS.md) and are open until their own named evidence is recorded. Short labels below are only a map:

| Test | Short acceptance objective | Test | Short acceptance objective |
| --- | --- | --- | --- |
| AT01 | Clean PG16 CI and checks | AT11 | Reject invalid signature/amount/currency/order |
| AT02 | Empty DB migrations; no fake pricing | AT12 | Duplicate, out-of-order and replay safety |
| AT03 | Real email activation; inactive login blocked | AT13 | Real sandbox registration, correct owner ID |
| AT04 | Invalid/expired activation rejected | AT14 | Uncertain registrar write never blind-retried |
| AT05 | Login/logout/reset using email | AT15 | Pending domain cannot display active |
| AT06 | Cross-user order/domain isolation | AT16 | Verified renewal expiry from registrar |
| AT07 | Real availability; taken cannot buy | AT17 | Owned NS change; unauthorized blocked |
| AT08 | No premium/unknown fixed-price checkout | AT18 | Refund intent + gateway settlement reconciliation |
| AT09 | Server pricing and checkout idempotency | AT19 | Encrypted restore in clean staging |
| AT10 | Razorpay test gateway order and amount | AT20 | HTTPS/monitoring/finance/legal/rollback approvals |

Do not mark AT01–AT20 complete merely because a unit test with a mock exists; full criteria include external operational proofs.

## 12. Exact safe verification command sequence

After checking out the intended feature branch and creating a **nonproduction** .env with secrets supplied securely (never commit .env):

~~~bash
cp .env.example .env
# Set a private POSTGRES_PASSWORD and DJANGO_SECRET_KEY;
# leave SALES_ENABLED=false and FULFILLMENT_ENABLED=false.
docker compose build
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py collectstatic --noinput
docker compose run --rm web python manage.py test shop --verbosity 2
docker compose run --rm web python -m compileall -q config shop
docker compose up -d
# Verify health and customer pages in a restricted development environment.
~~~

For PR #34 specifically:

~~~bash
docker compose run --rm web python manage.py test shop.test_nameserver_safety -v 2
~~~

**Do not claim these were run locally by the author of this continuity document**. They are reproducible instructions; the concrete passing GitHub Actions evidence is linked in section 7.

## 13. Decisions and blockers that must remain open

- **Owner approval required:** merging PRs, live sales/fulfillment, live credentials, purchase/renew/transfer/refund operations, account prefunding, paid infrastructure, production changes, architecture migration.
- **Repository license governance:** [issue #29](https://github.com/renoukhan39-bit/domain-reseller/issues/29) tracks outbound licensing and contributor terms. Public repository visibility ≠ blanket permission to reuse code.
- **External access required:** dedicated Openprovider sandbox credentials and valid TLD test cases; Razorpay test keys and webhook secret; real SMTP; staging and monitoring; finance/legal/supplier account approval. Store credentials in approved secrets, never docs.
- **Unverified:** Openprovider /v1 vs historic /v1beta endpoint schemas in a real sandbox, actual checkout and registrar writes, real settlement, TLD-specific policies, production TLS/backup/on-call drill.
- **Document drift:** HEAD may move after this snapshot; prefer fetching main, open PRs and recent Actions logs over assuming these exact SHAs remain latest.

## 14. Immediate three tasks for the next developer or Codex session

1. **Reconcile and review open PR #34**, check latest head CI and ownership guard against current provider schema; merge only if the owner explicitly approves. In parallel, independently repeat clean Docker/PG16 checks for M0-09.
2. **M4-07 Openprovider sandbox**: approve isolated credentials; validate availability, customer-specific handle, registration, owner/ID/status/expiry, renewal, nameservers, pending and uncertainty; capture privacy-safe real evidence. If blocked, choose next independent P0 test, not a paid live request.
3. **M3-08/M3-09 Razorpay test mode**: real signed webhook delivery and replay, strict currency/amount/order, race/concurrency, read-only reconciliation and refund state; preserve no-blind-retry semantics.

Then implement supplier costs/margins, invoice/ledger, financial approvals and operator alerts before any live pilot. Transfers, DNSSEC, white-label APIs and hosting are valuable **later**, not excuses to bypass payment safety.

## 15. Copyable prompt for a completely new ChatGPT/Codex conversation

> You are continuing the independently operated **domain-reseller** project in https://github.com/renoukhan39-bit/domain-reseller. **Do not depend on prior ChatGPT chat context.** First inspect current main HEAD, branches, open PRs, GitHub Actions, issues and actual tests. Then read docs/PROJECT_CONTINUITY_MASTER.md, AGENTS.md, docs/START_HERE.md, docs/TASKS.md, docs/FEATURE_MATRIX.md, docs/REPOSITORIES_TO_STUDY.txt and the research docs linked in the master continuity file. Retain Django/Python/PostgreSQL modular monolith and existing Razorpay/Openprovider code. **Do not migrate to Laravel or copy the WHMCS module**, and do not use a third major reference repository without specific reason. Protect signed payment evidence, user isolation, idempotency, provider ownership, one-shot registrar and refund operations, secrets and fail-closed switches. **Never merge PRs, enable live payments/fulfillment, spend real money or perform production changes without explicit owner approval.** Choose **one** currently open high-impact P0 task, search code/tests first, implement a minimal meaningful feature on a feature branch, run actual available checks and tests, update canonical docs and this continuity log, and create a detailed unmerged PR. Record exactly what passed or was blocked. Finish with an architecture/status assessment, changed files, tests, PR/commit link, risks and next three tasks. Reduce Codex credits by avoiding repeated research and speculative frameworks.

## 16. Workflow to keep this record current after every future session

For each meaningful coding/research turn, the assistant/developer should:

1. Open this document and current GitHub state; **never assume** historical chat text remains loaded.
2. Append a dated entry to [PROJECT_SESSION_LOG.md](PROJECT_SESSION_LOG.md) with task IDs, scoped request, branch/base/head commits, PRs, links, test evidence, unresolved risks, blocked work, exact source docs changed and three next steps.
3. Update the authoritative [TASKS.md](TASKS.md), [FEATURE_MATRIX.md](FEATURE_MATRIX.md), [ROADMAP.md](ROADMAP.md), [CODEBASE_AUDIT.md when available](https://github.com/renoukhan39-bit/domain-reseller/pull/34), etc. **Only when real evidence or decisions change.**
4. Keep one focused PR per task and preserve source URLs/SHAs. Distinguish **source written**, **fixture-tested**, **CI-tested**, **real sandbox verified**, **operator/finance approved**, and **production operational**.
5. Avoid archiving secrets, real registrant PII, webhook bodies/tokens, payment-card details, undocumented claims, hidden reasoning or copyrighted third-party code.
6. When the owner exports old ChatGPT conversations, add any missing public/nonsecret factual decisions as a dated addendum to the session log, not as invented reconstructed quotations.

**Bottom line:** this GitHub repository and these linked documents are the project memory. A future session should build from the actual last verified commit/PR, not restart market research or architecture planning.
