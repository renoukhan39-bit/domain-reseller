# START HERE — new developer / Codex onboarding

**Current local validation (18 November 2026)** covers 219 PostgreSQL application tests, 17 backup tests, encrypted synthetic recovery, locked packaging and headless Chromium account flows. See [current evidence and remaining gates](../AnalyseFuture/TEST_AND_VALIDATION_REPORT.txt).

**Official repo:** https://github.com/renoukhan39-bit/domain-reseller. This file replaces the need to know any previous chat.

## Mission
Develop our own independently operated, branded, domain and web-services platform aspiring to GoDaddy/Namecheap customer experiences and WHMCS-class administration. Start as a **reseller using accredited registrar APIs** (not an ICANN-accredited registrar). Build a reliable business before expanding to hosted email, website builder, SSL, hosting, AI-assisted domain discovery, multi-registrar routing and white-label wholesale reseller APIs.

## Current foundation and architecture
- **One repo**, original Django/Python modular application, PostgreSQL, container setup, server-rendered pages. Keep a modular monolith until scaling requires services. No PNLCS/Laravel migration is approved.
- Code includes a first draft of signup/login and registrant profiles, TLD catalog, Openprovider integration, Razorpay order/webhook verification, safe fulfillment worker, domain dashboard, nameserver management, admin screens, migration and test cases.
- **Verified locally:** cloud onboarding built and started the Docker/PostgreSQL 16 workflow, passed Django checks, migrations, static collection and all 174 application tests, and verified HTTP readiness and service restarts. All 17 backup guard tests and the isolated encrypted restore drill with synthetic data also passed. The initial [GitHub Actions Python CI run](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43452225170) is separate historical CI evidence; it does not establish CI success for later commits.
- **Not verified externally:** protected staging or production deployment, registrar sandbox compatibility, Razorpay real test webhooks/settlement, real SMTP delivery, financial/legal compliance, production offsite backups and recovery. **Not complete:** DNS editing, transfers, tax invoices, multi-registrar routing, public reseller APIs, hosting/email/SSL/website-builder. Existing payment/refund reconciliation tooling has local fixture coverage; actual gateway acceptance remains open. See `FEATURE_MATRIX.md` and `TASKS.md`.
- **Repository layout:** the Django application remains the active product. Upstream PNLCS and WHMCS source is preserved under `AnalyseFuture/` for future analysis and is not part of the running application. Read [the repository map](history/REPOSITORY_STRUCTURE.md) before moving files.
- Sales and fulfillment disabled by default. Never perform real domain purchase or paid cloud provisioning without explicit owner approval.

## Read next
Read the recovered [continuity master](continuity/PROJECT_CONTINUITY_MASTER.md) and [session log](continuity/PROJECT_SESSION_LOG.md) to retain prior decisions. The later [master recovery audit](../AnalyseFuture/REPOSITORY_AUDIT.txt), [feature inventory](../AnalyseFuture/FEATURE_INVENTORY.txt) and [handoff](../AnalyseFuture/NEXT_DEVELOPER_INSTRUCTIONS.txt) describe branch recovery and consolidation; earlier reports remain evidence for their own commits.

1. `README.md` — setup and first tests.
2. `AGENTS.md` — mandatory Codex safety and development rules.
3. `docs/product/PROJECT_GOAL.md` — requirements and acceptance criteria.
4. `docs/engineering/ARCHITECTURE.md` and `docs/product/FEATURE_MATRIX.md` — architecture and status.
5. `docs/engineering/TASKS.md` and `docs/planning/ISSUE_BACKLOG.csv` — 66 item checklist and importable task backlog.
6. `docs/product/ROADMAP.md` and `docs/research/REUSE_FIRST_STRATEGY.md` — long-term product differentiation and reuse assessment.
7. `docs/continuity/CODEX_CLOUD.md`, `docs/operations/DEPLOYMENT.md`, `docs/planning/FREE_RESOURCES.md`, `CONTRIBUTING.md`, `SECURITY.md` — operations.
8. [Repository structure](history/REPOSITORY_STRUCTURE.md) and [detailed project idea and future roadmap](PROJECT_IDEA_AND_FUTURE_ROADMAP.txt) — active files, preserved references, practical delivery stages and speculative future features.

## First developer steps
```sh
cp .env.example .env   # set non-production secrets; never commit .env
docker compose build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py test shop
docker compose up -d
```
Use the issue checklist as a queue: first prove CI and clean startup, then validate payment and registrar flows in sandboxes. Link actual test evidence in PRs, not claims. Only tick tasks complete once acceptance criteria pass.

## Goal boundaries
Public open-source projects provide inspiration and permitted components, not a license to combine all sources. Adapt ideas from PNLCS, FOSSBilling, Paymenter, Upmind and Namingo only after checking license/security. The copyright holder retains upstream ownership; our repository, brand, original work, configurations and operations remain under our control. Commercial ownership and contribution licensing require separate legal consideration.
