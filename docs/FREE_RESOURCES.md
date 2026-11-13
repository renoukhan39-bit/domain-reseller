# Build with existing credits: what can actually cost ₹0 extra?

**As checked November 13, 2026.** This is a usage strategy, not a guarantee that every cloud service is free. Always check your own subscription dashboard; no access to your AWS, Azure, Colab or OpenAI billing information was provided.

| Resource | Practical use for this project | Additional cash needed for development? | Limits / caveats |
| --- | --- | --- | --- |
| GitHub public repo | Git history, issues, GitHub Actions, PR reviews | Usually ₹0 at normal open-source usage | Owner must grant connected account write access; paid runners/excess storage or private repository features can add costs |
| Python, Django, PostgreSQL | Web application, data storage, migrations | ₹0 license | Compute, database backups, security and operators are separate |
| Docker, local dev tools | Development and CI parity | ₹0 license | Host resource usage still exists |
| Openprovider sandbox | Real registrar API requests with separate test account | ₹0 for sandbox domain operations | Separate sandbox credentials; cannot perform real registry operations; some TLD limitations |
| Razorpay test mode | Payment orders, webhook, checkout integration | ₹0 for simulated transactions | Real-mode processing fees and KYC/merchant eligibility apply |
| AWS credits ($100,000 reported by owner) | Staging/production servers, RDS, networking, logs, backup | Potentially ₹0 extra **while credits are valid, applicable and unexhausted** | Need to verify actual balance, service eligibility, expiration and payment method; after expiry eligible services bill normally |
| Azure free credit ($200 reported by owner) | Short staging experiments or comparison | Potentially ₹0 extra in eligible trial period | Standard free-account $200 credit is generally valid for **30 days** after activation, not indefinitely |
| Google Colab 10,000 compute units (reported by owner) | Pricing simulations, market analysis, notebook experiments | Potentially ₹0 extra if units already held | Sessions time out; not a safe 24/7 web server; compute units are not transferable to AWS/Azure/registrar payments |
| Existing ChatGPT/Codex subscription | Code generation/review/refactoring/tests | No *additional* fee while within included allowance | **Not unlimited autonomous work**: Work and Codex share a usage allowance and may have weekly and/or window limits; resets vary |
| Existing site domain (excluded) | Website URL | Excluded at request | Does not pay for domains purchased by customers |

## Cost boundary: when does the first unavoidable business cost appear?

**R0/R1 (code + sandbox):** target ₹0 additional spend *under your stated exclusions*. You can write and test real integration code, run PostgreSQL and a staged web service within existing eligible cloud credits, and validate sandbox workflows. This does **not** register any actual domain for a customer.

**R2 (real paid orders):** wholesale domain registration/renewal fees are incurred through the registrar even if your customer funds the sale. Openprovider generally requires prepaid reseller balance. Razorpay transaction fees, refund costs, payment delays, taxes, vendor contracts, business compliance, and support remain. Marketplace/TLDs can require extra agreements. A legitimate merchant/registrar account might require verified adult or business ownership under provider rules; do not circumvent eligibility requirements.

## Recommended low-cost usage plan

1. Use **GitHub + local Docker + Django/PostgreSQL** first; never pay for extra coding tools before exhausting already included usage.
2. Put staging and small production on AWS only if the Activate balance and service eligibility are verified. Add AWS Budgets alerts and separate dev/prod environments. Leave Azure for a short trial comparison or a backup plan.
3. Use **Openprovider sandbox + Razorpay test mode** before enabling any live money path. Never pair test registrar with live payments.
4. Use Colab for supporting analyses, not the production server. Use ChatGPT/Codex to tackle one bounded GitHub issue at a time and commit reviewable changes.
5. Get real supplier quotes and compare live revenue to wholesale prices, gateway fees and taxes before setting prices; default TLD rows in the application are **disabled** until priced by an operator.

## GPT-6 Astra / Codex usage clarification

There is no promise of 24/7 unlimited unattended development. Official OpenAI guidance says Work and Codex share an included allowance on supported plans, are affected by model and task size, and may reset in windows; larger Pro tiers have higher allowances, not infinite compute. You already encountered a Work usage limit and a reset time in the interface. Check **Settings → Usage** for your exact remaining allowance, and **Codex `/status`** while in an active CLI session. More expensive model settings can use allowance faster; use lighter models for routine edits and reserve Astra for architectural/security reviews.

## Primary references (official)

- Openprovider sandbox: https://openprovider.help/books/api-integrations/page/sandbox-testing-environment
- Openprovider API portal: https://developer.openprovider.com/get-started.html
- Razorpay test integration: https://razorpay.com/docs/server-integration/python/test-app/
- Microsoft trial terms: https://learn.microsoft.com/en-us/training/modules/create-an-azure-account
- AWS Activate credits: https://aws.amazon.com/aws-startups/learn/applying-for-aws-activate-credits-a-step-by-step-guide/
- Colab runtime limits: https://research.google.com/colaboratory/faq.html
- OpenAI Astra and Work/Codex usage: https://help.openai.com/en/articles/20001516-managing-usage-with-gpt-6-astra-in-work-and-codex
- OpenAI Pro tiers: https://help.openai.com/en/articles/9793128-about-chatgpt-pro-tiers
