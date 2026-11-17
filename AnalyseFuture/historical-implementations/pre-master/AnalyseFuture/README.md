# Preserved material for future analysis

This folder preserves existing material outside the active Django application.
It is an archive for evaluation, not an installation target or an approved
replacement architecture. Nothing here has been declared malicious merely
because it was moved. Do not execute its installers, Composer/npm scripts,
or provider integrations as part of normal Django setup.

| Location | Contents | Intended use |
| --- | --- | --- |
| `Openprovider-WHMCS-domains-master/` | All 3,252 files from the previously extracted Openprovider WHMCS snapshot | Study provider behavior and integration ideas; WHMCS/PHP is separate from Django |
| `pnlcs-main/` | All 1,767 files/links from the previously extracted PNLCS snapshot | Study billing, portal and module designs; Laravel/MySQL is a separate application |
| `project-history/2026-11-17/` | Original README and four documentation files before status/navigation clarification | Preserve prior project work and compare editorial changes |
| `PRESERVATION_MANIFEST.json` | Original commit, paths and Git subtree/blob identities | Verify preservation without relying on file counts alone |

Both upstream directories retain their original names, file contents, notices,
executable modes, and relative layout. PNLCS's `public/themes -> ../themes`
symlink remains inside its snapshot. Dependency vendor folders are intentional
parts of those snapshots. Empty directories are present locally where supplied;
Git tracks files, not empty directories.

PNLCS includes an MIT license, copyright Panelica. Preserve it on reuse. The
Openprovider snapshot has bundled dependency notices but no top-level project
license was found; do not assume a redistribution or adaptation license for the
whole module. Commercial reuse needs a separate license and provider review.

The existing Django application remains the selected foundation. Copying PHP
modules into it is not an integration. A framework migration still requires an
explicit architecture decision and owner approval under `AGENTS.md`.

The ZIP upload and extraction history is recorded in
[`../docs/REPOSITORY_STRUCTURE.md`](../docs/REPOSITORY_STRUCTURE.md). This archive
is not evidence that the GitHub account was or was not compromised. Private
credentials and customer data must never be added here as a preservation tactic;
use secure incident evidence storage if any is discovered.

Read the [project idea and future roadmap](../docs/PROJECT_IDEA_AND_FUTURE_ROADMAP.txt)
for proposals, and the [current task list](../docs/TASKS.md) for delivery gates.
