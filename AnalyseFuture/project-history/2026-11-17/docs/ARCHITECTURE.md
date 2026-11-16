# Architecture and trust boundaries

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

Django CSRF for all customer POSTs; secure cookies in production; HSTS; HTTP->HTTPS redirect; ORM query ownership filters; default-deny sales and fulfillment; secrets from environment; payment webhooks signed over raw bytes; user account activation; password reset; admin read-only financial state; explicit audit records.

### Remaining critical production work

1. Use hosted Postgres with encrypted storage and network restrictions; no public database access. Set managed TLS (`POSTGRES_SSLMODE=require/verify-full`) and verify CA.
2. Shared Redis/edge throttling for login, search, email verification, purchase and webhook; the current in-memory cache throttle is **per worker**, not distributed.
3. Wrap multi-worker reconciliation and provider retries in a reviewed operator workflow. A crash after sending a registrar request can leave `processing` indefinitely — this is intentionally not retried, but MUST alert an operator.
4. Credential rotation and IAM least privilege; use AWS Secrets Manager or Azure Key Vault, never GitHub code/secrets in plain text.
5. Configure TLS termination with trusted headers, bot protection, secure SMTP, structured logs (redact PII), error metrics, backups and restore drills.
6. TLD-specific registry restrictions, registrant verification, financial taxes/GST, refund policy, availability race handling, actual DNS propagation checks.
7. Complete provider reconciliation: an unknown `payment.captured` event is recorded but cannot auto-fulfill. Review each unmatched event.
8. Implement stock/price change process, provider balance thresholds, refund status reconciliation and a robust ledger before broad launch.

This is a deployable codebase but **not a production-certified finished service**. A third-party security review is recommended before handling live money and personal data.
