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
Runtime secrets, customer data and ignored local environments are not archive
material to publish. They remain outside Git. Current runtime tests were deferred
at the owner's explicit request.
