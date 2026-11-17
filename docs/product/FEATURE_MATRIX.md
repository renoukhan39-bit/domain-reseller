# Feature matrix — truthful implementation status

Current local validation after restructuring: **219 application tests**, **17 backup tests**, encrypted synthetic recovery, installed-wheel checks and live browser account flows passed. See the [current report](../../AnalyseFuture/TEST_AND_VALIDATION_REPORT.txt); real external acceptance remains open.

See the [complete feature inventory](../../AnalyseFuture/FEATURE_INVENTORY.txt) for recovered branch work and reference-only PHP modules. This recovery restores existing nameserver registrar-identity safeguards and tests; current-run results are in [the validation report](../../AnalyseFuture/TEST_AND_VALIDATION_REPORT.txt).

**Written/unverified** means code/configuration exists but full runtime, sandbox and CI evidence is not available. No feature is production-verified merely because source is present.

| Capability | Status | Location / follow-up |
| --- | --- | --- |
| Django project + PostgreSQL + Docker + CI definition | CI passed; deployment unverified | `config`, `compose.yaml`, `.github/workflows/ci.yml`; [green CI](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43452225170) |
| Accounts, verification, profile, login/reset | Local browser flows and automated tests passed; external SMTP unverified | `shop/forms.py`, `shop/views.py` |
| Verification resend, single-use links, shared send throttles | Implemented; automated local verification; external SMTP unverified | `shop/accounts/verification.py`, migration `0002`; `docs/operations/EMAIL_VERIFICATION.md`; M1-08 remains open |
| Shared login/reset/search/checkout abuse budgets and safe reset email errors | Implemented; local concurrency and endpoint tests; production load/edge controls unverified | `shop/security/throttling.py`, `shop/middleware.py`; `docs/operations/THROTTLING.md` |
| Domain search + basic TLD pricing | Written/unverified | `shop/domains/openprovider.py`, `shop/models.py` |
| Razorpay Orders + signed captured-payment webhooks | Local fixtures/signature/replay/concurrency tests passed; real gateway unverified | `shop/commerce/gateway.py`, `shop/commerce/orders.py` |
| Payment replay, uncertain checkout/refund reconciliation, duplicate-operation constraints | Implemented; local fixtures; real gateway verification outstanding | `shop/commerce/events.py`, `shop/commerce/refunds.py`, migration `0003`; `docs/operations/PAYMENT_RECONCILIATION.md` |
| Openprovider register/renew/NS + worker | Local contract/safety/concurrency tests passed; real registrar unverified | `shop/domains/openprovider.py`, `shop/management/commands` |
| Registrar identity validation, durable claims, stale escalation and read-only registration recovery | Implemented; local fixtures; sandbox acceptance outstanding | `docs/operations/PROVIDER_COMPATIBILITY.md`, `docs/operations/FULFILLMENT_RECOVERY.md` |
| Basic dashboard and operator admin | Dashboard browser verified; financial evidence and registrar identity are view-only in admin; deletion and concurrent-write regressions passed; deployed operator acceptance open | `shop/templates`, `shop/admin.py` |
| Database email identity and race handling | Local PostgreSQL migration, duplicate preservation, signup/admin concurrency and legacy lookup tests passed | `shop/accounts/identity.py`, migration `0004`, account/admin tests |
| Locked Python dependencies and least-privilege CI | Hash-required install and 16-package audit passed; current remote CI pending | `requirements.lock`, `Dockerfile`, `.github/workflows/ci.yml` |
| Domain transfers, DNS record editor, DNSSEC | Missing | R3 |
| Premium domains, IDNs, price sync | Missing | R3 |
| Full tax invoices, automated refunds and reconciliation | Missing | R2 |
| Scheduled renewals/reminders | Missing | R2 |
| Multi-registrar routing and reseller API | Missing | R3 |
| Hosting/VPS/email/SSL/website builder | Missing | R4 |
| Support portal, monitoring and advanced analytics | Missing | R4 |
| Verified staging, backup restore, real sandbox credentials | Unverified external work | R0–R2 |
| Encrypted local PostgreSQL backup and isolated recovery drill | Local tool/guard tests and synthetic ownership/payment restore verified; production offsite/staging unverified | `scripts/backups/database_backup.py`, `scripts/backups/backup_restore_drill.py`; `docs/operations/BACKUP_RESTORE.md` |

**Rule:** Promote a row to tested only with linked CI/sandbox/review evidence. The 66-task checklist is planning data, not verified release status.
