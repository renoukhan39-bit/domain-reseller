# Repository audit and preserved structure

Audit date: 17 November 2026. Baseline: `594d2907ca3aaf65c1bba3491b0cd72a5c0be083`.
The purpose is to organize existing work without deleting it or replacing the
application. This change follows the owner's request to push directly to `main`;
it does not reset Git history, remove existing features, or authorize deployment.

## Findings and limits of the audit

The baseline contains 5,129 tracked files/links. A complete tracked-path inventory,
file-type and symlink review, automated scan for several strong credential
patterns, and targeted review of application boundaries, setup, CI and project
documents were performed. This is a structure and development-readiness audit,
not a line-by-line forensic or independent application security audit.

The active Django files, documentation, scripts and CI match pre-upload merge
`6b52221`. Commit `9b21435` uploaded two ZIP files; commit `594d290` extracted them
at the owner's request in this conversation. Those two snapshots account for
5,019 tracked files and almost all root-level clutter. The extraction was our
earlier requested action, not evidence of a malicious actor.

No strong private-key, AWS access-key, GitHub-token or live-provider-key pattern
was found in tracked contents by the limited scan. This does not rule out other
secrets, encoded payloads, vulnerable dependencies, earlier history exposure or
unauthorized account access. Local `.env` remains ignored and outside the commit.
Clearly labeled upstream testing templates are preserved; they must never become
production credentials.

Git contents alone cannot establish who controlled an account. GitHub audit logs,
sessions, collaborators, installed apps and credential access were not inspected.
No author has been labeled an attacker. The repository owner should review those
account controls, revoke unknown access and rotate any credentials shown to be
exposed through secure settings. No account settings were changed by this audit.

## Active layout

```text
domain-reseller/
  AGENTS.md                         Repository-specific engineering/safety rules
  README.md                         Developer entry point and current status
  CONTRIBUTING.md / SECURITY.md      Contribution and disclosure guidance
  manage.py                         Django command entry point
  pyproject.toml                    Python package/dependency declarations
  Dockerfile / compose.yaml          Web, PostgreSQL 16 and guarded worker
  .dockerignore / .gitignore         Build context and local-file exclusions
  .env.example                      Variable names and safe defaults, no secrets
  .github/                          Active CI and contribution templates
  config/                           Django settings, URLs, ASGI and WSGI
  shop/                             Current application, migrations and tests
  scripts/                          Backup/recovery tooling and issue import
  docs/                             Product, architecture, tasks and runbooks
    PROJECT_IDEA_AND_FUTURE_ROADMAP.txt  Detailed product idea and future attempts
    REPOSITORY_STRUCTURE.md          This audit, boundaries and navigation
  AnalyseFuture/                    Preserved reference material and originals
    README.md
    PRESERVATION_MANIFEST.json
    Openprovider-WHMCS-domains-master/
    pnlcs-main/
    project-history/2026-11-17/
```

The conventional Django paths stay in place because imports, package discovery,
Docker COPY statements, settings paths, templates, migrations, test commands and
existing links depend on them. A new `src/` hierarchy would add migration work
without resolving the actual clutter. The new build exclusions keep the archive,
Git metadata, local environment files and virtual environment out of Docker build
contexts. They do not delete those files or change application dependencies.

## Inventory and responsibilities

Counts below refer to the baseline before the reorganization, not to new reports.

| Original group | Tracked files/links | Treatment and responsibility |
| --- | ---: | --- |
| Root project files | 10 | Keep active entry points, safeguards, packaging and setup |
| `.github/` | 3 | Keep repository CI and templates active |
| `config/` | 5 | Keep Django configuration and entry points |
| `shop/` | 63 | Keep models, migrations, forms, views, providers, payment/recovery/throttle logic, templates and tests |
| `scripts/` | 4 | Keep backup/recovery tools, guard tests and issue import |
| `docs/` | 25 | Retain all project history, requirements, roadmaps and operator runbooks; clarify stale statements |
| `Openprovider-WHMCS-domains-master/` | 3,252 | Move intact into `AnalyseFuture/` |
| `pnlcs-main/` | 1,767 | Move intact into `AnalyseFuture/` |

`shop/` includes the original domain models and three migrations, authentication
and email verification, registrant contacts, catalogue/pricing, signed payment
handling, fulfillment and reconciliation commands, shared database throttling,
administration, customer templates and the existing test suite. None of that
substantial work is discarded or rewritten by the structure change.

Local-only setup state includes `.venv`, `.env`, generated outputs and Docker
volumes. These are not project source or material to publish in `AnalyseFuture`.
No provider credentials, admin user or invented catalogue prices are introduced.

## Preservation contract

Every tracked upstream file is relocated unchanged, including vendored dependency
files, notices and executable bits. PNLCS's internal themes symlink is preserved.
Their nested `.github` files remain reference files; they are not root-level
GitHub Actions workflows. Upstream installers and application code are not run.

The original README and the four edited documents (`START_HERE`, `TASKS`,
`DEPLOYMENT`, `ARCHITECTURE`) are also copied unchanged to
`AnalyseFuture/project-history/2026-11-17/` before clarification. Other existing
documents remain at their established paths. No substantive previous document is
deleted because a newer idea differs from it.

`AnalyseFuture/PRESERVATION_MANIFEST.json` records the original Git tree identities:

```text
Openprovider-WHMCS-domains-master: f73a2e623464ef6ab41de89ea15e06cb65d4db38
pnlcs-main:                       655e3889f74d2a0ed3fa0f2743c055d85da7c90f
```

Comparing each old subtree with its new subtree proves recursive names, contents,
file modes and links are unchanged. Comparing archived document blobs proves their
original text is retained. An automated baseline-to-new-tree comparison additionally
requires every original tracked path either to remain or to map to its preserved
destination. Empty directories are not tracked by Git; file content is the
preservation unit. No history rewrite or force push is part of this work.

## Reading and development order

1. `START_HERE.md`, `../AGENTS.md`, `PROJECT_GOAL.md`, `TASKS.md`: mission and gates.
2. `PROJECT_IDEA_AND_FUTURE_ROADMAP.txt`: detailed proposal and time horizons.
3. `FEATURE_MATRIX.md`, `ARCHITECTURE.md`: current implementation and constraints.
4. `PROVIDER_COMPATIBILITY.md`, `PAYMENT_RECONCILIATION.md`, `REFUNDS.md`,
   `FULFILLMENT_RECOVERY.md`: financially sensitive integration behavior.
5. `EMAIL_VERIFICATION.md`, `THROTTLING.md`, `BACKUP_RESTORE.md`,
   `RECONCILIATION_MONITORING.md`, `DEPLOYMENT.md`: operating and validation guidance.
6. `ROADMAP.md`, `REUSE_FIRST_STRATEGY.md`, `OWNERSHIP_AND_LICENSES.md`,
   `PUBLIC_REPOSITORY_REPORT.md`: future scope and reuse/license decisions.

Stay with Django/PostgreSQL unless a separate approved architecture decision
changes the foundation. The PNLCS and WHMCS snapshots are study material. They do
not make hosting, invoicing or other PHP functionality available in this app.

## Validation and release boundaries

Required checks for the reorganization include preservation identity comparisons,
unmodified active application/configuration blobs, Docker build with the reduced
context, Django checks, migration checks, static collection, the PostgreSQL `shop`
suite, and representative HTTP requests after service startup. Results are recorded
in `RESTRUCTURE_VALIDATION.txt` after execution. Backup tools receive their existing
guard tests and the isolated synthetic-data restore drill.

Keep `SALES_ENABLED=false` and `FULFILLMENT_ENABLED=false`. Local automated tests
do not verify real Openprovider registration, Razorpay test webhooks, SMTP delivery,
tax/legal readiness, production security or recovery. This reorganization is not
a launch, a registrar-accreditation claim, or proof that GitHub compromise has been
resolved. Current-run evidence is distinct from historical CI links; a new remote
CI result must be checked independently after the push.
