# Reuse-First Strategy — Domain Reseller Competitor

Updated: 2026-11-13

## Decision to make before Codex writes more code

There are two mutually exclusive primary application foundations:

1. **Fastest broad feature coverage (recommended if credit/time saving is priority):** adopt `Panelica/pnlcs` as the single **main application** in a separate comparison branch or new repository after an audit. PNLCS is Laravel/PHP/MySQL and MIT licensed. Keep its license/copyright notices. Do not claim exclusive ownership of the upstream code. Avoid importing an old Django application into it as though it were a library.
2. **Original Django code ownership (recommended if independent implementation is priority):** retain `renoukhan39-bit/domain-reseller` as Django/PostgreSQL and use PNLCS, FOSSBilling, Namingo, and Upmind only as **functional references**. Reuse appropriately licensed Python dependencies, official APIs and external services. This will need substantially more implementation effort.

**Hard gate:** before migrating, the owner must approve an Architecture Decision Record (ADR) selecting option 1 or 2. Codex must not maintain both production backends in parallel.

## Use what exists; stop reimplementing commodity features

| Feature | Preferred ready-made choice | Reuse mode | Immediate status | License/constraint |
|---|---|---|---|---|
| Storefront, cart, domain catalogue, customer portal | [Panelica/PNLCS](https://github.com/Panelica/pnlcs) | **Adopt as base** if using Laravel | Audit and smoke-test first | MIT; preserve notices |
| Invoicing, tax rules, customer support, affiliate dashboard, notifications | PNLCS built-in | Use existing modules | Run tests and verify use cases | MIT upstream |
| Domain registration / renewal / transfers | PNLCS `modules/Registrars/OpenProvider`, `Namecheap`, `ResellerClub` | Built-in adapters, sandbox test | Check API versions and integration correctness | Provider commercial terms and wholesale charges |
| Payment checkout and signed webhooks | PNLCS `modules/Gateways/Razorpay` | Built-in integration | Test-mode payment + signature/duplicate verification | Provider processing fees on live payments |
| Domain provider multi-adapter design | [Upmind provision-provider-domain-names](https://github.com/upmind/provision-provider-domain-names) | Read documentation/architecture; **do not copy GPL code** into proprietary app casually | Reference only | GPL-3.0 |
| Advanced domain lifecycle & compliance | [Namingo Registrar](https://github.com/getnamingo/registrar) | Domain expertise/reference; not required for ordinary reseller | Later | MIT; registrar accreditation is separate |
| Website analytics | [Umami](https://github.com/umami-software/umami) | Integrate separately via script/container | Optional after core works | MIT |
| Availability & status page | [Uptime Kuma](https://github.com/louislam/uptime-kuma) | Separate container and status page | Good early addition | MIT |
| Live chat / omnichannel support | [Chatwoot](https://github.com/chatwoot/chatwoot) | Separate application and widget, **only if** PNLCS tickets are insufficient | Defer until justified | Core MIT; `enterprise/` separately licensed |
| Authoritative DNS under your control | [PowerDNS](https://github.com/PowerDNS/pdns) | Separate DNS service integrated via API | **Not needed on day 1** if registrar DNS works | GPL-2.0; operational burden |
| HTTPS certificates for own services | [Certbot](https://github.com/certbot/certbot) / ACME | Existing tool/service | Configure now for hosting | Apache-2.0 |
| Hosting/VPS provisioning | PNLCS cPanel, HestiaCP, Proxmox server modules | Connect when offering hosting | Defer until domain commerce reliable | Separate panels/cloud may cost money |

## What should still be custom (your competitive advantage)

- Brand, customer experience, search relevancy, transparent retail/renewal pricing and offers.
- Unique selling proposition; plan for customer niches, language and market.
- White-label **domain** reseller API, scoped API keys, quotas, price tiers, reseller ledgers and reconciliation, **if not already covered and proven by base app**.
- Registrar routing/risk controls: provider health checks, price/availability reconciliation, TLD rules, premium pricing, manual reviews, expiry notices.
- Fraud checks and abuse policies; evidence/audit logs; customer support operations.
- Security hardening and compliance with registrar agreements, domain registrant-data obligations, taxes, privacy, consent and dispute handling.

## Known high-priority audit finding — PNLCS and Openprovider

At audit time, `Panelica/pnlcs/modules/Registrars/OpenProvider/OpenProviderRegistrar.php` hardcodes `https://api.openprovider.eu/v1beta` and sandbox `http://api.sandbox.openprovider.nl:8480/v1beta`. Openprovider's current developer portal documents `https://api.openprovider.eu/v1` with HTTPS-only production traffic. Do not switch endpoints by string replacement without inspecting endpoint schemas, sandbox support, and integration tests. Track a blocking provider-compatibility task before live sales.

- PNLCS module: https://github.com/Panelica/pnlcs/blob/main/modules/Registrars/OpenProvider/OpenProviderRegistrar.php
- Official current portal: https://developer.openprovider.com/get-started.html
- Older docs may still show v1beta: https://docs.openprovider.com/

## Codex credit-preservation rules

1. Before every feature, search the chosen base app's existing code/tests, its module registry, official SDKs, and open-source packages.
2. Produce **REUSE / CONFIGURE / ADAPT / BUILD** decision with reason, license and proof link. Prefer configuration over code.
3. Never write a second auth, order, checkout, ticket or invoicing service when the base already has one.
4. No parallel framework rewrite (Laravel + Django), premature microservices, bespoke DNS server, SMTP server, CA, credit-card vault, or ICANN registrar implementation.
5. Scope one reviewable issue per task; implement the smallest tested change. Stop after one PR and report exact tests, failures, costs and blocker questions.
6. Use test providers only; sandbox order paths must be verified end-to-end and financial operations fail closed.
7. Only propose new external software after checking security history, upkeep, active maintainer status, license, dependencies, memory/runtime footprint and integration complexity.
8. Never claim a feature is production-ready based on a README. Verify code, automated tests, sandbox operations and recovery behavior.

## Immediate phased execution (without live purchasing)

**Task A — 1st Codex task: inventory and architecture decision (no code rewrite)**
- Compare existing Django repo with PNLCS and produce a feature matrix `present / tested / missing / risky`.
- Include license inventory and dependency CVE scans. Verify PHP/MySQL/Docker runtime requirements.
- Audit Openprovider v1 API compatibility, Razorpay webhook verification and idempotency, domain lifecycle state machine, tenant isolation and queue semantics.
- Give a recommendation: migrate to PNLCS or stay Django, with effort/risk tradeoffs; seek approval before rewriting.

**Task B — staged foundation if owner selects PNLCS**
- Keep the owner's repository as the main brand/source; create a feature branch before touching main.
- Import upstream source at pinned commit with intact LICENSE/NOTICE, record provenance and upstream remote, avoid importing prior Django source into Laravel internals.
- Run the existing tests, fix failing setup, build and deploy a protected staging environment, no live sales.
- Configure pre-existing registrar/payment modules in test mode, verify webhooks, refunds, renewal, domain states and order failure handling.
- Add only missing features with acceptance tests. Introduce Umami and Uptime Kuma as **separate services** when useful.

**Task C — core business gate**
- Customer logs in -> searches domain -> gets an attributable, current provider price -> creates checkout -> signed test-mode payment -> sandbox registrar registers domain exactly once -> customer views/updates nameservers -> renewal/transfer and failure paths recorded -> admin reconciles.
- Document and gate live enablement on technical, legal, financial and support readiness.

## Cost reality

Free open-source code != zero live-service cost. Self-hosted platforms consume resources; AWS credits apply only to eligible consumption/periods. Customer domains have wholesale acquisition/renewal fees; live payment gateways charge processing fees. Provider APIs may require approval or reseller contracts. Codex/Astra usage is limited by the user's plan/allowance; there is no guaranteed unlimited background build.
