# GitHub handoff and bounded Codex work

## Target

`https://github.com/renoukhan39-bit/domain-reseller`, default branch `main`.

As inspected on November 13, 2026, connected GitHub account was `renoukhan39-bit`, but its effective repository permissions were `pull=true`, `push=false`. This source package therefore **has not been pushed to that GitHub repository**. Obtain repo owner write access or reconnect a GitHub identity with push permissions before claiming an upload.

## One-time upload from a writable local machine

1. Download and extract the source ZIP next to a fresh clone of the target repo.
2. **Clone** the existing repo first. Never force-push, replace `.git`, or overwrite an unknown branch.

```bash
git clone https://github.com/renoukhan39-bit/domain-reseller.git
cd domain-reseller
git checkout -b feat/domain-reseller-foundation
# Copy the package contents from the extracted `domain-reseller/` folder
# into this clone, including hidden `.github` and `.gitignore` files.
# Do NOT copy `.git`, `.env`, `__pycache__`, or local database files.
git add .
git commit -m "feat: domain reseller foundation with integrations and checklist"
git push -u origin feat/domain-reseller-foundation
# Open a pull request targeting main and let GitHub Actions run.
```

If the push is denied, the connected GitHub identity still lacks repository write permission. Ask the owner to add the correct collaborator, or connect as the repository owner. GitHub Actions must turn green before merging the PR.

## Suggested workflow for Codex / Astra

Keep each task small and reviewable, with evidence:

1. Open `docs/TASKS.md`. Select the highest-priority unchecked task and its acceptance criterion.
2. Prompt: `Implement TASK Mx-yy in this repository. Make changes only needed for this task; add Django tests; run CI checks; do not enable live payments, change secrets or deploy. Provide files changed, risks and manual verification.`
3. Review code and tests; push a branch/PR; merge only after passing checks.
4. For architectural or payment safety changes, request an independent second review before live rollout.
5. Repeat based on available allowance. Do not run an autonomous agent indefinitely, especially with billing/deployment credentials.

**Never copy AWS/Azure/GitHub access tokens, Openprovider credentials, Razorpay live secrets, webhook signing secrets or customer data into prompts, commits or PRs.**

## Optional: import all 66 task checkboxes as GitHub Issues

After the code has been merged and GitHub CLI is authenticated as an account with issue-write permissions:

```bash
python scripts/import_issues.py            # preview; creates nothing
python scripts/import_issues.py --apply    # creates missing issues, skips existing titles
```

The importer uses `docs/ISSUE_BACKLOG.csv`, contains **no access tokens**, and is intentionally a dry-run by default. Review the issue backlog before applying; GitHub API limits may apply. The status `source-written/verify` means code was authored here but has not been proven by CI/sandbox.
