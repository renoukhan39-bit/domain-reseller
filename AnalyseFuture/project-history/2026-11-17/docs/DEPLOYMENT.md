# Developer and operations runbook

## Development (local Compose)

1. Copy `.env.example` to `.env`, generate a fresh random `DJANGO_SECRET_KEY`, set a long random `POSTGRES_PASSWORD`; never commit `.env`.
2. `docker compose build`
3. `docker compose run --rm web python manage.py migrate`
4. `docker compose run --rm web python manage.py createsuperuser`
5. `docker compose up -d`
6. Visit `http://127.0.0.1:8000/admin/`, configure only the TLDs with verified supplier prices and your safe selling prices. No sample prices are loaded.
7. `docker compose exec web python manage.py test shop`

## Sandbox integrations

- Openprovider: create a separate account at `https://cp.sandbox.openprovider.nl/signup`, enable its API user, use `https://api.sandbox.openprovider.nl/v1beta` with separate credentials. Keep live registrar account unfunded during initial tests.
- Razorpay: create test key ID/secret, set a **separate** webhook secret, register `https://staging.example.com/webhooks/razorpay/` for `payment.captured`, and trigger real test-mode webhook deliveries; synthetic headers are only for unit tests.
- Email: configure verified SMTP and test sign-up and password reset end to end.
- Starting state: `SALES_ENABLED=false` and `FULFILLMENT_ENABLED=false`. Set sales true only in controlled test environments after inspecting gateway/registrar identity. Enable fulfillment only after verifying signed webhook delivery.
- **Never mix live payment credentials with sandbox registrar credentials**; customers could pay real money for non-existent domains.

## Real live deployment (after acceptance)

- Recommended: AWS ECS/Fargate or a small EC2 + RDS PostgreSQL + ALB/TLS, private database, IAM roles, secrets manager, encryption/retention, CloudWatch alarms and AWS Budgets. An equivalent Azure setup is possible (App Service/Container Apps + PostgreSQL + Key Vault). Select ONE primary cloud to simplify operations.
- Use a managed HTTPS reverse proxy, TLS cert, secure SMTP, a CDN/WAF or rate limiter, and a process runner for both `web` and `worker`.
- Set `DJANGO_DEBUG=false`, generated secret, `POSTGRES_HOST` and strong database credentials, `POSTGRES_SSLMODE=require`, exact `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`; choose trusted proxy handling only if configured correctly.
- Run `python manage.py migrate`, `python manage.py collectstatic --noinput`, `python manage.py check --deploy`, `python manage.py test shop` in CI/staging.
- Configure Razorpay test webhook with exact HTTPS route, correct signing secret. Enable only **test mode** initially.
- For live account, change Openprovider to `https://api.openprovider.eu/v1`, enable API, sign registry contracts, maintain prepaid balance, reconcile wholesale and selling price, switch gateway to live keys only after legal/KYC approval.
- Change live toggles in a reviewed change window, one at a time; perform one authorized small real purchase only when ready.

## Rollback and incidents

- Stop new sales: `SALES_ENABLED=false`. Stop provider actions: `FULFILLMENT_ENABLED=false`.
- Preserve database backup and webhook delivery metadata; never force an order from `processing` to `paid` without checking the supplier.
- Investigate `needs_review` and `processing` older than 10 minutes. Reconcile the provider's actual domain and Razorpay's captured/refund status before taking action.
- Run database backups daily; keep encrypted offsite snapshots. Quarterly restore drill required.
- A payment captured but domain unavailable requires manual refund according to your reviewed policy.

## Cost controls

- AWS Budgets: set spending/credit-balance alerts and billing notifications; credit depletion can create real charges. Verify credit expiration and which AWS services qualify.
- Azure: $200 free-trial balance commonly lasts 30 days; verify account-specific expiration and don't assume it can be used for third-party fees.
- Colab: use notebooks only for data experiments, price analysis or development — runtimes time out and cannot serve a 24/7 storefront reliably.

## Important unresolved deployment facts

No registrar account, payment gateway credentials, AWS account, Azure subscription, SMTP credentials, domain DNS or live deployment was accessed during preparation. No production or sandbox transaction has been executed from this package.
