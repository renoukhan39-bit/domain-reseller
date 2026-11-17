# Public GitHub repository comparison — domain reseller

**Checked:** 2026-11-13  
**Purpose:** Find publicly accessible repos relevant to `renoukhan39-bit/domain-reseller` and distinguish software that can be reused from reference examples. These repos are **not** guaranteed production-secure or compatible with your Django stack. Review their licenses and dependencies before copying anything.

| Repository | What it actually provides | License (checked when available) | Fit for current project |
| --- | --- | --- | --- |
| [FOSSBilling/FOSSBilling](https://github.com/FOSSBilling/FOSSBilling) | Free self-hosted PHP billing, invoicing, customer management and extensions; project calls itself beta | Apache-2.0 | **Best alternative to building checkout/billing from scratch**, but replacing Django would require a deliberate platform change and an Openprovider registrar adapter |
| [Paymenter/Paymenter](https://github.com/Paymenter/Paymenter) | PHP hosting billing/shopfront with extension system | MIT | Useful free billing/UI reference; domain registrar integration must be specifically verified/built |
| [openprovider/Openprovider-WHMCS-domains](https://github.com/openprovider/Openprovider-WHMCS-domains) | Openprovider's official PHP module for domain registration, renewals, transfers, nameservers, price sync and WHMCS billing hooks | **No root LICENSE located in check**; check repo/module terms before reuse | **Strongest Openprovider integration reference**, but WHMCS itself is a separate commercial billing platform; not directly installable in Django |
| [Osir-Inc/fossbilling-osir](https://github.com/Osir-Inc/fossbilling-osir) | Ready domain registrar plugin, domain operations, DNS client UI, markup/TLD import for FOSSBilling | Apache-2.0 | Attractive free-platform combination if switching registrar to OSIR, **but OSIR has no sandbox; real test purchases cost money**, so not suitable for strict ₹0 domain-operation testing |
| [getnamingo/registrar](https://github.com/getnamingo/registrar) | Registrar management stack with EPP/RDAP/ICANN compliance for accredited registrars | MIT | Educational only; solves running a registrar, **not simply reselling through Openprovider** |
| [codemec-com/domain-reseller-api](https://github.com/codemec-com/domain-reseller-api) | OpenAPI specification and Python, Node.js and PHP example clients for Cloudzaro domain API | MIT on example repository | API contract/example reference, **not** a ready-made customer storefront; provider says no sandbox |

## Recommended approach

**Stay on the existing Django + PostgreSQL implementation for the first five-day sprint.** It is already oriented to Openprovider sandbox and Razorpay test mode, matching the goal of no incremental live-registration spend. Evaluate code patterns and API behaviors in the public repos, but do not mix PHP modules into the Django tree or assume existing code is production-safe.

If you decide instead that rapid delivery matters more than preserving Django, do a short feasibility spike on **FOSSBilling**: install in a separate local environment, evaluate invoicing/hosting billing, confirm availability of a maintained and compatible **Openprovider** adapter, Razorpay support and INR/tax behavior. Do not migrate or promise launch until these checks pass.

**Do not select OSIR solely because its plugin is complete:** vendor docs clearly state there is no sandbox and all live operations use real reseller funding. **Do not select WHMCS as a ₹0 stack:** Openprovider's plugin is free, but WHMCS is a different paid product.

## Reference links and verification

1. FOSSBilling repository and license: https://github.com/FOSSBilling/FOSSBilling ; https://github.com/FOSSBilling/FOSSBilling/blob/main/LICENSE
2. Paymenter repository and license: https://github.com/Paymenter/Paymenter ; https://github.com/Paymenter/Paymenter/blob/master/LICENSE
3. Openprovider registrar module: https://github.com/openprovider/Openprovider-WHMCS-domains ; official integration notes: https://developer.openprovider.com/whmcs.html
4. OSIR's official FOSSBilling registrar plugin: https://github.com/Osir-Inc/fossbilling-osir ; official docs on no-sandbox: https://osir.com/en/integrations/fossbilling/
5. Namingo: https://github.com/getnamingo/registrar
6. Cloudzaro OpenAPI examples: https://github.com/codemec-com/domain-reseller-api
7. Official Openprovider developer portal: https://developer.openprovider.com/

## Developer due diligence before adoption

- Check release dates, open issues, maintenance, vulnerability advisories and test coverage.
- Confirm actual license on each individual repository, preserve required copyright notices and check compatibility of dependencies.
- Verify API support and availability of separate sandbox; review rate limits, price changes, retries and idempotency.
- Audit how contacts, PII, payment tokens, logs and DNS keys are stored.
- Verify registrar support for your intended TLDs, pricing, tax, business eligibility and settlement.
- Do not fork and publicly deploy code before security and compliance review.
