# Preserved references, history and recovery records

This directory is outside the active Django build/package/deployment. Moving
code here does not make it safe. Do not run archived installers or integrations.

- `references/registrar-integrations/Openprovider-WHMCS-domains-master/`: entire WHMCS registrar snapshot, unchanged internals and notices.
- `references/billing-platforms/pnlcs-main/`: entire Laravel/MySQL billing platform, including MIT notice and internal themes symlink.
- `historical-implementations/`: exact main-before-change and accessible branch versions, with source identities recorded in the manifest.
- `project-history/`: earlier retained documentation versions.
- Root `.txt` reports: complete inventory, feature/dependency map, security/duplicate findings, paths, consolidation, migration, debt, validation and continuation.
- `PROJECT_VISION_AND_FUTURE_ROADMAP.txt`: canonical full product proposal; future ideas do not imply implemented capabilities.
- `PRESERVATION_MANIFEST.json`: earlier subtree/blob identities with current destinations.

Read `REPOSITORY_AUDIT.txt`, `ARCHIVED_FILES_MANIFEST.txt` and the root
[PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md) for scope and safe continuation.
No evidence here establishes account compromise or intellectual-property rights.
PNLCS has its upstream MIT notice. The WHMCS snapshot lacks a top-level project
license; retain dependency notices and obtain a license decision before reuse.
Runtime secrets, customer data and ignored local environments belong outside
Git. The earlier pause on tests was superseded by owner authorization. Baseline
`4f48424` passed 189 application tests and 17 backup tests during cloud setup,
including the isolated encrypted restore drill. Current changes need their own
verification evidence.

`PRESERVATION_MANIFEST.json` records the 18 November 2026 continuation review
against 5,355 tracked baseline paths. Both upstream subtree identities match
the original preservation records. A complete all-ref Git bundle and a full
per-file hash/type/classification inventory are retained outside this checkout
at the local paths recorded in that manifest. Those local copies require separate
retention when moving machines. No archive was removed.
