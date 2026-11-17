# Contributing

Read [`docs/START_HERE.md`](docs/START_HERE.md), `AGENTS.md`, `SECURITY.md` and `docs/TASKS.md` before editing code. No knowledge of prior conversations is necessary.

1. Choose one task ID and create a feature branch (`feat/M2-08-price-sync`, `fix/M3-08-webhook`).
2. Keep PRs focused, test Django authorization and financial/registrar invariants, and document any migration.
3. Run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py test shop` with local Docker/Postgres; report actual results, including skipped/unrun tests.
4. Submit PR using `.github/PULL_REQUEST_TEMPLATE.md`, linking task ID, change, tests, license audit, deployment/rollback notes.
5. Never upload secrets, `.env`, real customer data, cloud keys or provider tokens. Do not enable live sales or trigger purchases.
6. Public source does not imply permission to copy unrelated code. Ask maintainers about license and contribution terms before substantial outside contributions.
