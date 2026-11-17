# Functional project structure

Updated 17 November 2026. The existing product is a Django/PostgreSQL domain
reseller, with a future AI-assisted digital-presence vision. This reorganization
groups files by their actual responsibility; it does not replace the product,
introduce a second backend, or assert that proposed AI features already exist.

```text
domain-reseller/
├── README.md / PROJECT_STRUCTURE.md       Entry points and this functional map
├── AGENTS.md / CONTRIBUTING.md / SECURITY.md
├── manage.py / pyproject.toml              Django CLI and Python package contract
├── Dockerfile / compose.yaml               Web, DB and guarded worker setup
├── .env.example / .gitignore / .dockerignore
├── .github/                               Active repository automation/templates
├── config/                                Settings, routing, ASGI/WSGI adapters
├── shop/                                  One Django application and schema
│   ├── accounts/verification.py            Verification/resend/token lifecycle
│   ├── commerce/
│   │   ├── gateway.py                      Razorpay transport and identifier policy
│   │   ├── events.py                       Signed evidence and payment-event replay
│   │   ├── orders.py                       Checkout, fulfillment, identity rules
│   │   └── refunds.py                      Guarded refund/reconciliation lifecycle
│   ├── domains/openprovider.py             Registrar contract and domain operations
│   ├── security/throttling.py              Shared request-budget policy
│   ├── models.py / migrations/             Persistent identities and schema history
│   ├── forms.py / views.py / urls.py        Validated HTTP and framework adapters
│   ├── admin.py / middleware.py / exceptions.py
│   ├── management/commands/                Operator CLI adapters (Django convention)
│   ├── templatetags/                       Presentation helpers
│   ├── templates/
│   │   ├── shop/{layouts,storefront,accounts,commerce,domains,portfolio}/
│   │   ├── shop/*.html                     Compatibility names, no duplicate pages
│   │   └── registration/                   Django auth names and verification pages
│   ├── tests/
│   │   ├── accounts/                       Email identity/verification coverage
│   │   ├── commerce/                     Payment/refund/fulfillment coverage
│   │   ├── domains/                        Provider and nameserver coverage
│   │   ├── security/                       Shared-throttle coverage
│   │   ├── operations/                     Reconciliation monitor coverage
│   │   ├── test_core.py                    Original cross-feature journey tests
│   │   └── test_compatibility.py            Template/helper compatibility coverage
│   └── legacy service modules              Thin import aliases; see below
├── scripts/
│   ├── backups/                            Encrypted backup, recovery, guard suite
│   └── github/                             Backlog-to-issue tooling
├── docs/
│   ├── START_HERE.md / README.md            Developer entry and categorized index
│   ├── product/                            Charter, capabilities and product stages
│   ├── engineering/                        Architecture, code audit, tasks/build plan
│   ├── operations/                         Setup, provider/payment/email/recovery SOPs
│   ├── governance/                         Ownership and license boundaries
│   ├── research/                           Pinned comparisons and reuse analysis
│   ├── planning/                           Backlog, initial sprint and resource plans
│   ├── continuity/                         Prior decisions, sessions and handoff
│   └── history/                            Earlier cleanup evidence (own revision scope)
└── AnalyseFuture/
    ├── references/
    │   ├── registrar-integrations/Openprovider-WHMCS-domains-master/
    │   └── billing-platforms/pnlcs-main/
    ├── historical-implementations/          Exact pre-change and branch versions
    ├── project-history/                    Earlier preserved documentation versions
    ├── *_INVENTORY.txt / *_REPORT.txt / *_SUMMARY.txt
    ├── SECURITY_AUDIT.txt / DUPLICATE_ANALYSIS.txt / TECHNICAL_DEBT.txt
    ├── PROJECT_VISION_AND_FUTURE_ROADMAP.txt Canonical full product vision
    ├── PRESERVATION_MANIFEST.json           Earlier upstream subtree identities
    └── WORK_PROGRESS.txt / NEXT_DEVELOPER_INSTRUCTIONS.txt
```

## Feature ownership and dependencies

Accounts owns email verification and activation policy. Commerce owns trusted
amounts, payment evidence, order state transitions, fulfillment and refunds.
Domains owns the Openprovider protocol, identifiers and provider facts. Security
owns shared abuse budgets. HTTP forms/views, operator commands and middleware
call those implementations; they are adapters, not competing feature copies.
The schema stays in `models.py` and immutable migrations because relationships,
app labels and migration history form one Django persistence boundary.

The nameserver handler recovers an existing branch safeguard: environment pairing,
customer registrant handle, provider id/name and active status must match before
a registrar write. This is preserved prior work, not a speculative new integration.
Real provider acceptance remains unverified.

Tests mirror these responsibilities. Original cross-feature tests stay together
as journey coverage. Templates are grouped by customer task rather than their
`.html` extension. Registration names remain where Django expects them; customer
reset routes explicitly select the project's account templates to avoid admin
template-loader collisions. No test was discarded because of the new layout.

## Compatibility, packaging and references

`shop.email_verification`, `shop.payments`, `shop.payment_events`, `shop.refunds`,
`shop.services`, `shop.providers` and `shop.throttling` remain thin aliases to
canonical module objects. Private helpers and legacy patch targets still have one
implementation. Existing source consumers can migrate gradually; new code imports
the functional packages. These aliases are intentional compatibility homes.

Old `shop/*.html` template names delegate to functional templates. The layout
alias extends the canonical layout, while ordinary pages include their canonical
page. Active routes/template inheritance use the new names directly. Python
package data includes the new template depth. CLI paths and CI backup references
follow `scripts/backups/`; issue import resolves the planning CSV from the repo root.

Root files and `.github`, `config`, migrations and management commands remain in
their framework-discovered homes. Moving them merely to make all directory names
look similar would break discovery or require unnecessary wrappers. All remaining
root files are build, framework, governance or navigation entry points.

## Preserved material and uncertain code

The independent PHP projects have functional containers, but their internals are
not flattened. Their Composer autoload roots, dependency versions, assets, notices,
executable modes and PNLCS themes symlink are part of their own project structure.
Preserving those relationships is their correct home. No PHP code was installed
or executed. Confirmed dormant TLS problems are documented in the security audit;
moving code does not make it safe.

`AnalyseFuture` is excluded from Docker contexts and the Python package discovery
allowlist. Nested historical workflows are not root GitHub Actions workflows.
Historical Python files are under non-importable snapshot directory names and
must not be used as runtime packages. Sensitive live credentials would require
private evidence storage, never public archival; none were knowingly added here.

Every starting file is accounted for in `AnalyseFuture/COMPLETE_FILE_INVENTORY.txt`.
The path map records functional moves, compatibility aliases, preserved originals
and recovered branch work. The archived manifest explains provenance and purpose.
Git history and a verified all-ref external bundle retain the recovery baseline.
Full path/byte inspection is not a line-by-line security certification of every
vendored dependency or binary asset.

## Validation and continuation

The owner subsequently authorized runtime testing on 17 November 2026. The
restructured application now passes **189 PostgreSQL tests**, **17 backup tests**,
the encrypted synthetic recovery drill, installed-wheel checks and live headless
Chromium account flows. See [the full validation report](AnalyseFuture/TEST_AND_VALIDATION_REPORT.txt)
for commands, the verification-page fix, template compatibility correction,
production warning and external prerequisites.

The earlier no-tests restriction applied to the reorganization commit, not this
later validation phase. Existing source, migration history and preserved upstream
snapshots remain intact. Real registrar/payment/SMTP/staging and production
acceptance are still unverified; local test results do not establish those gates.

Use `AnalyseFuture/NEXT_DEVELOPER_INSTRUCTIONS.txt` to continue. Rebuild images
after source changes. Sales and fulfillment remain disabled; testing does not
authorize purchases, deployment or irreversible registrar retries. No force push,
history rewrite or branch/tag deletion is part of delivery.
