# Feature matrix — truthful implementation status

**Written/unverified** means code/configuration exists but full runtime, sandbox and CI evidence is not available. No feature is production-verified merely because source is present.

| Capability | Status | Location / follow-up |
| --- | --- | --- |
| Django project + PostgreSQL + Docker + CI definition | CI passed; deployment unverified | `config`, `compose.yaml`, `.github/workflows/ci.yml`; [green CI](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43452225170) |
| Accounts, verification, profile, login/reset | Written/unverified | `shop/forms.py`, `shop/views.py` |
| Verification resend, single-use links, shared send throttles | Implemented; automated local verification; external SMTP unverified | `shop/email_verification.py`, migration `0002`; `docs/EMAIL_VERIFICATION.md`; M1-08 remains open |
| Domain search + basic TLD pricing | Written/unverified | `shop/providers.py`, `shop/models.py` |
| Razorpay Orders + signed captured-payment webhooks | Written/unverified | `shop/payments.py`, `shop/services.py` |
| Openprovider register/renew/NS + worker | Written/unverified | `shop/providers.py`, `shop/management/commands` |
| Basic dashboard and operator admin | Written/unverified | `shop/templates`, `shop/admin.py` |
| Domain transfers, DNS record editor, DNSSEC | Missing | R3 |
| Premium domains, IDNs, price sync | Missing | R3 |
| Full tax invoices, automated refunds and reconciliation | Missing | R2 |
| Scheduled renewals/reminders | Missing | R2 |
| Multi-registrar routing and reseller API | Missing | R3 |
| Hosting/VPS/email/SSL/website builder | Missing | R4 |
| Support portal, monitoring and advanced analytics | Missing | R4 |
| Verified staging, backup restore, real sandbox credentials | Unverified external work | R0–R2 |

**Rule:** Promote a row to tested only with linked CI/sandbox/review evidence. The 66-task checklist is planning data, not verified release status.
