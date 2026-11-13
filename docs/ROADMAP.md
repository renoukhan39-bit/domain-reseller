# Product roadmap — GoDaddy-class ambition, evidence-based delivery

The goal is a competitive domain and web-services platform, **not** an assertion of current market parity or ICANN accreditation. Prioritize financial correctness and customer safety over feature count.

## R0: verified foundation (P0)
- [ ] Clean local Docker boot, migrations, Django checks, test suite and green GitHub Actions run.
- [ ] Secrets excluded, authorizations tested, fail-closed toggles verified.
- [ ] CI output attached to task/PR. No paid operations.

## R1: verified sandbox sales (P0)
- [ ] Customer signup, verified email, contact/registrant details and tenant boundaries.
- [ ] Availability, pricing, premium/TLD restrictions and clear first-year/renewal costs.
- [ ] Razorpay test payments and signed webhook replay protection.
- [ ] Openprovider current-version sandbox contact, registration, renewal, NS, error reconciliation.
- [ ] Full controlled checkout end-to-end acceptance tests; no real money.

## R2: controlled live pilot (P0, requires explicit owner approval)
- [ ] Tax-compliant invoices, refunds, payment/registrar ledger and payout reconciliation.
- [ ] Registry policies, consumer terms, privacy, customer support, abuse response and compliance review.
- [ ] Renewal reminders and scheduled renewal workflow; prevent duplicate registrar requests.
- [ ] TLS staging, alerting, audit logs, distributed rate limits, backup/restore drill, rollback.
- [ ] Registrar agreement, prefunding/cashflow evaluation, valid production credentials and supervised rollout.

## R3: competitive registrar/reseller platform
- [ ] Multi-registrar adapters and safe provider-routing policies.
- [ ] Domain transfers, DNS editor, DNSSEC, IDN, bulk domain portfolio management.
- [ ] Price sync, currency/tax rules, premium domains, notifications.
- [ ] White-label wholesale reseller accounts, scoped API keys, developer API and webhooks.
- [ ] Reporting, dashboards and organization roles.

## R4: expanded web-services portfolio
- [ ] Web hosting and VPS control-panel/API integration.
- [ ] SSL lifecycle automation, business email and website builder integrations.
- [ ] Support desk/live chat, knowledge base, analytics, status and uptime monitoring.
- [ ] Customer self-service, multilingual storefront, marketing, affiliates.
- [ ] Independent security audit, availability and disaster recovery targets.

**Releases are evidence-based, not time promises.** The 5-day plan is an initial staging sprint, not a 5-day full competitor build. See `TASKS.md` for detailed work IDs, owner and acceptance tests.
