# START HERE — new developer / Codex onboarding

**Official repo:** https://github.com/renoukhan39-bit/domain-reseller. This file replaces the need to know any previous chat.

## Mission
Develop our own independently operated, branded, domain and web-services platform aspiring to GoDaddy/Namecheap customer experiences and WHMCS-class administration. Start as a **reseller using accredited registrar APIs** (not an ICANN-accredited registrar). Build a reliable business before expanding to hosted email, website builder, SSL, hosting, AI-assisted domain discovery, multi-registrar routing and white-label wholesale reseller APIs.

## Current foundation and architecture
- **One repo**, original Django/Python modular application, PostgreSQL, container setup, server-rendered pages. Keep a modular monolith until scaling requires services. No PNLCS/Laravel migration is approved.
- Code includes a first draft of signup/login and registrant profiles, TLD catalog, Openprovider integration, Razorpay order/webhook verification, safe fulfillment worker, domain dashboard, nameserver management, admin screens, migration and test cases.
- **Not verified:** actual Django test execution, deployment, registrar sandbox compatibility, Razorpay real test webhooks, real SMTP, financial compliance and recovery drills. **Not complete:** DNS editing, transfers, invoice reconciliation, multi-registrar routing, public reseller APIs, hosting/email/SSL/website-builder. See `FEATURE_MATRIX.md` and `TASKS.md`.
- Sales and fulfillment disabled by default. Never perform real domain purchase or paid cloud provisioning without explicit owner approval.

## Read next
1. `README.md` — setup and first tests.
2. `AGENTS.md` — mandatory Codex safety and development rules.
3. `docs/PROJECT_GOAL.md` — requirements and acceptance criteria.
4. `docs/ARCHITECTURE.md` and `docs/FEATURE_MATRIX.md` — architecture and status.
5. `docs/TASKS.md` and `docs/ISSUE_BACKLOG.csv` — 66 item checklist and importable task backlog.
6. `docs/ROADMAP.md` and `docs/REUSE_FIRST_STRATEGY.md` — long-term product differentiation and reuse assessment.
7. `docs/CODEX_CLOUD.md`, `docs/DEPLOYMENT.md`, `docs/FREE_RESOURCES.md`, `CONTRIBUTING.md`, `SECURITY.md` — operations.

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
