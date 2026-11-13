# Project charter — domain reseller platform

**Project:** Domain Reseller  
**Repository:** https://github.com/renoukhan39-bit/domain-reseller  
**Owner:** repository owner; engineering lead TBD  
**Build strategy:** real hosted service incrementally enabled behind explicit payment and provisioning gates.

## One-sentence goal

Build and operate a secure, maintainable, branded domain reseller website where eligible customers can search for supported domain names, understand registration and renewal prices, create verified accounts, submit registrant details, pay through Razorpay, and manage domains registered via Openprovider — with all money and registrar actions auditable and safely reversible where possible.

## Non-negotiable outcomes

1. Real customer accounts, isolated per tenant. Unauthorized access to another customer's orders/domains must fail.
2. Server-computed prices, with no ability to spoof an amount from a browser.
3. Domain search via actual registrar availability endpoint, not generated/mock data.
4. A paid order only transitions after trusted payment confirmation. Never trigger registration from a browser callback alone.
5. Correct customer registrant handle, not a single reseller-owned handle for all purchases.
6. A domain or renewal API call must never be automatically duplicated following a timeout or ambiguous result.
7. Public launch must not occur before financial/legal, tax, privacy, security, supplier and recovery gates have passed.

## Product scope by release

- **R0 — code & controlled sandbox (current development):** repository setup, accounts, pricing, payment flow, API integrations, worker, unit tests, CI, backend/admin and minimal responsive customer UI.
- **R1 — sandbox acceptance:** verify real sandbox register / renew / change nameservers, test-mode payment signatures, webhook replay, auth, ownership, database restore, deployment to a non-public staging endpoint.
- **R2 — supervised small live pilot:** approved legal entity and registrar account, compliant checkout, known margin, tax receipts/invoices, financial reconciliation, monitoring and manual customer support, limited TLDs and low volumes.
- **R3 — expanded production:** expiry lifecycle and reminders, automated reconciliation, registrar price sync, DNS management, domain transfers, customer support portal, reporting, refunds, incident playbooks.

## Target user journeys

- Visitor searches `name.com`: sees availability from the registrar and an INR registration price maintained in admin.
- New visitor signs up: receives email activation and enters registrant contact details.
- Verified customer buys an available domain: server creates a priced order; Razorpay checkout collects payment; verified webhook marks it paid; worker calls Openprovider and stores registry ID; dashboard updates.
- Customer renews an existing domain: a separate signed payment is captured and renewal expiry is fetched from the registrar.
- Customer changes NS: authorized user sends new nameservers and receives a result, with an audit entry.
- Operator reviews an ambiguous or failed registration and reconciles external state before refund, manual correction or retry.

## Explicit exclusions at initial release

Hosting/compute charges under existing AWS/Azure credits, the already-owned site domain, current ChatGPT/Codex subscription costs, developer wages (self-build), and Colab balance are excluded from the *incremental build budget*. They are not guaranteed free forever and they do **not** cover registrar inventory costs, tax, card fees, an email provider, KYC or support requirements.

## Definition of done (public production launch)

All release-blocking tasks and all 20 acceptance tests in `TASKS.md` pass with evidence; no outstanding critical security defects; backup restore proven; actual payment and registrar ledger reconciliation proven; customer legal terms and complaint channels live; final go-live reviewed by owner. Simply running `docker compose up` is **not** done.
