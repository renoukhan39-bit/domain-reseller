# Architecture and trust boundaries

The active product is the existing Django/PostgreSQL application. See [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md) for its file map. Upstream material under `AnalyseFuture/` is preserved for analysis and is not an additional running backend. The [detailed project idea and future roadmap](PROJECT_IDEA_AND_FUTURE_ROADMAP.txt) proposes later capabilities; those concepts are not implemented merely because they appear in that document.

```
Customer browser --TLS--> Django templates/auth/CSRF --> PostgreSQL
                                  |                    |
                                  v                    v
                    Razorpay Orders API      TLDPrice / Order / Domain / Audit
                                  |
                             Razorpay checkout
                                  |
                    Razorpay signed captured webhook --HMAC--> DB order = paid
                                                              |
                      separate controlled worker --> Openprovider REST API
                                                      | 
                                                  contact + domain ID
                                                              |
                                                        customer dashboard
```

### Key code paths

- `shop/forms.py`: input validation and registrant data.
- `shop/views.py`: authenticated endpoints, signed verification links, checkout, webhook.
- `shop/models.py`: durable records and unique constraints.
- `shop/payments.py`: gateway API and constant-time webhook verification.
- `shop/providers.py`: registrar REST methods and conservative availability parsing.
- `shop/services.py`: payment state transitions and at-most-one automatic registrar attempt.
- `shop/management/commands/process_orders.py`: scheduled worker, safe by default.
- `shop/management/commands/refund_order.py`: explicit operator reconciliation before refunds.

### System boundaries

- **Browser** is untrusted: amount, ownership, webhook success, registry status, and order IDs must never be accepted from it as proof.
- **Razorpay** is authoritative for captured payment confirmation; verify HMAC and cross-check payment order ID, currency, and amount.
- **Openprovider** is authoritative for registration, renewal and dates. No inferred expiry and no blind external API retry.
- **Database** is authoritative for local ownership and workflow transitions. Unique indices restrict duplicate events, payment IDs, names, and per-user order keys.

### Current security controls

Django CSRF for all customer POSTs; secure cookies in production; HSTS; HTTP->HTTPS redirect; ORM query ownership filters; default-deny sales and fulfillment; secrets from environment; payment webhooks signed over raw bytes; user account activation; password reset; admin read-only financial state; explicit audit records; shared database-backed authentication/customer-action throttles; durable fulfillment claims, stale-order escalation and read-only reconciliation backlog monitoring.

Cloud onboarding verified local Docker/PostgreSQL 16 startup and restarts, Django checks/migrations/static collection, all 174 application tests, 17 backup guard tests and an isolated encrypted restore drill with synthetic data. These checks cover local behavior and concurrency. They do not prove real registrar/payment/SMTP compatibility, staging or production operation, or recovery of production data.

### Remaining critical production work

1. Use hosted Postgres with encrypted storage and network restrictions; no public database access. Set managed TLS (`POSTGRES_SSLMODE=require/verify-full`) and verify CA.
2. Validate production load, edge rate limits and bot protection. Application throttles already share PostgreSQL state across workers and have local concurrency coverage; that does not replace infrastructure-level abuse controls. See [THROTTLING.md](THROTTLING.md).
3. Schedule and verify stale-order escalation and operator alerts. Durable claims, `mark_stale_orders` and `check_reconciliation_backlog` are implemented; actual alarm delivery and on-call drills remain unverified. A crash after an uncertain registrar request still requires reconciliation before any retry. See [FULFILLMENT_RECOVERY.md](FULFILLMENT_RECOVERY.md) and [RECONCILIATION_MONITORING.md](RECONCILIATION_MONITORING.md).
4. Credential rotation and IAM least privilege; use AWS Secrets Manager or Azure Key Vault, never GitHub code/secrets in plain text.
5. Configure TLS termination with trusted headers, secure SMTP, structured logs (redact PII), error metrics, offsite encrypted backup retention and production recovery drills. Existing local encrypted backup/restore tooling and synthetic drills do not verify the deployment's backup policy.
6. TLD-specific registry restrictions, registrant verification, financial taxes/GST, refund policy, availability race handling, actual DNS propagation checks.
7. Validate reconciliation with real gateway test-mode delivery. Retained, HMAC-verified early capture evidence can replay when a matching local gateway order becomes bound; unmatched/conflicting events remain for operator review. Digest-only legacy events require authentic signed redelivery. See [PAYMENT_RECONCILIATION.md](PAYMENT_RECONCILIATION.md).
8. Validate the implemented refund reconciliation against real test-mode gateway responses. Implement supplier price-change controls, provider balance thresholds and a robust financial ledger before broad launch; see [REFUNDS.md](REFUNDS.md) for the existing guarded lifecycle.

This is a deployable codebase but **not a production-certified finished service**. A third-party security review is recommended before handling live money and personal data.
