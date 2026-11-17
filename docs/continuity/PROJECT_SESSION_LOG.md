> Recovery note (17 November 2026): recovered from `8ce7879a1fcb`. The original text below is retained as historical project work; old PR states, verification counts and proposed changes are snapshots, not current status. Current recovery evidence and handoff are in `../AnalyseFuture/REPOSITORY_AUDIT.txt` and `../AnalyseFuture/NEXT_DEVELOPER_INSTRUCTIONS.txt`. The nameserver ownership fix is being recovered with its tests in this task; use the current validation report for results. Direct main delivery is explicitly authorized for this task.

# PROJECT SESSION LOG — persistent conversation-to-code handoff

**Purpose:** append new, non-secret facts after **each meaningful engineering or research session** so the team never needs a long ChatGPT conversation to recover project decisions.\
**Starting source:** [PROJECT_CONTINUITY_MASTER.md](PROJECT_CONTINUITY_MASTER.md).\
**Policy:** entries describe **observed** GitHub artifacts and accessible conversation summaries only. Do not state that inaccessible prior messages were exported. Do not record personal data, secrets, copied paid/unlicensed code or full sensitive payment webhooks.

## Append-only entry format (copy for every future session)

~~~markdown
## YYYY-MM-DD — <short topic>
- Owner request:
- Starting main SHA and existing open PRs:
- Task IDs and architecture/ownership decisions:
- Actual files reviewed and implementation changes:
- New/updated docs, research sources and upstream commit SHAs:
- Branch, commits, PR link and review/merge status:
- Verification: exact environment, commands, test counts, Actions URLs; unrun checks:
- Real external API/sandbox evidence or blockers:
- Confirmed findings vs hypotheses and rollback/operational risks:
- Owner decisions pending:
- Three next prioritized tasks:
~~~

Never overwrite earlier entries merely to make a plan look complete; add a dated correction if a conclusion changes. See [TASKS.md](../engineering/TASKS.md) and [FEATURE_MATRIX.md](../product/FEATURE_MATRIX.md) for authoritative acceptance state.

## 2026-11-13 through 2026-11-14 — project foundation and public repository strategy

- Owner request: build a genuine independently controlled domain reseller/web services platform competitive in ambition with GoDaddy/Namecheap/WHMCS, minimizing Codex credits and avoiding redundant construction; evaluate one application foundation vs multiple public repositories; continue work in one canonical GitHub repo.
- Canonical repo: https://github.com/renoukhan39-bit/domain-reseller
- Key decision: existing Django/Python/PostgreSQL remains the starting point; no PNLCS Laravel/MySQL migration without owner-approved ADR. Learn from open-source approaches subject to license conditions, not by combining incompatible apps.
- Public inventory: [REPOSITORIES_TO_STUDY.txt](../research/REPOSITORIES_TO_STUDY.txt), 13 GitHub projects; secondary notes in [PUBLIC_REPOSITORY_REPORT.md](../research/PUBLIC_REPOSITORY_REPORT.md) and [REUSE_FIRST_STRATEGY.md](../research/REUSE_FIRST_STRATEGY.md).
- Conversation scope: the dates/titles come from visible project conversation summaries, **not** complete exported transcripts.
- Next work selected in later sessions: audit actual source, prioritize safe payment/registrar acceptance, preserve default OFF operations.

## 2026-11-15 — two-upstream deep research, code audit and M5-08 safety PR

- Owner request: inspect README, AGENTS, START_HERE, PROJECT_GOAL, ROADMAP, FEATURE_MATRIX, TASKS, ARCHITECTURE, REUSE_FIRST_STRATEGY, PUBLIC_REPOSITORY_REPORT, 13-repo inventory, CODEX_CLOUD, PROVIDER_COMPATIBILITY, PAYMENT_RECONCILIATION and ISSUE_BACKLOG; deep-study exactly PNLCS and official Openprovider WHMCS module; document risks and roadmap; implement one safe P0 fix and create an unmerged PR.
- Starting main: [6b522210ee47a38abc14868b0f26dcabc910dd83](https://github.com/renoukhan39-bit/domain-reseller/commit/6b522210ee47a38abc14868b0f26dcabc910dd83).
- PNLCS pinned SHA: [beaa7ea7c91972c3380bbd233610da938c871959](https://github.com/Panelica/pnlcs/tree/beaa7ea7c91972c3380bbd233610da938c871959); upstream MIT; PHP ^8.4 + Laravel ^13, design references for billing, customer area, registrar and gateway adapters, webhook claims, one-shot jobs; old Openprovider /v1beta and HTTP sandbox patterns were not adopted.
- Official WHMCS domains module pinned SHA: [9bcd5198fa2c09db61faa854d029474013d7464f](https://github.com/openprovider/Openprovider-WHMCS-domains/tree/9bcd5198fa2c09db61faa854d029474013d7464f); PHP/WHMCS, no root LICENSE located in tree; patterns for registrar lifecycle, contacts, prices, EPP, DNS/DNSSEC, sync; no source copied.
- Confirmed source gaps addressed: shop/views.py nameserver customer POST previously checked local owner/status and only FULFILLMENT_ENABLED; not current registrar identity or full payment/registrar environment pairing.
- Implementation: shop/views.py now requires fulfillment_ready(), matching provider ID/domain/active state and saved user registrant handle from read-only GET before NS PUT. shop/tests/domains/test_nameservers.py adds **10** targeted offline tests. No new dependencies/migrations. Caveat: remote GET and PUT are not atomic.
- Research deliverables in [PR #34](https://github.com/renoukhan39-bit/domain-reseller/pull/34): CODEBASE_AUDIT.md, TWO_PRIMARY_REPO_COMPARISON.md, MASTER_BUILD_PLAN.md, plus updates to TASKS, FEATURE_MATRIX, ROADMAP and ARCHITECTURE.
- Branch/head: fix/M5-08-nameserver-registrar-identity @ [4f65433d27adbffddcc5bfa438cdaaebb4e2ff6a](https://github.com/renoukhan39-bit/domain-reseller/commit/4f65433d27adbffddcc5bfa438cdaaebb4e2ff6a). PR #34 was open/unmerged at consolidation.
- Verified GitHub Actions: [branch CI 43745054673](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43745054673) successful with **184 application tests, OK**, Django checks, PostgreSQL migrations, compileall and backup recovery; [PR CI 43745160078](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/43745160078) completed success.
- Unrun/unverified: independent local Docker reproduction; real Openprovider HTTPS /v1 sandbox register/renew/NS; actual Razorpay test webhook settlement, production SMTP, legal/finance, offsite backup and public launch. No real payment or domain was made.
- Owner approvals still needed: merge PR #34, live deployment/credentials/domain purchases, legal/finance sign-off, outbound source licensing [#29](https://github.com/renoukhan39-bit/domain-reseller/issues/29).
- Next three tasks: independent clean Docker/PG16 foundation M0-09; Openprovider sandbox M4-07; Razorpay test-mode signed webhook/reconciliation M3-08/M3-09.

## 2026-11-16 — persistent documentation and chat continuity

- Owner request: push research, charts, project links, decisions, prior chat context and implementation status into a GitHub document so new ChatGPT or Codex sessions can continue without loading long conversation history.
- Starting default branch inspected: main remains [6b522210ee47a38abc14868b0f26dcabc910dd83](https://github.com/renoukhan39-bit/domain-reseller/commit/6b522210ee47a38abc14868b0f26dcabc910dd83); PR #34 was still open.
- Dedicated docs-only branch: docs/project-continuity-master-2026-11-16; [documentation PR #35](https://github.com/renoukhan39-bit/domain-reseller/pull/35) opened, **not merged**.
- Documentation branch commit before this log update: [0e7765db8b68fb4662409c52a69b149582b54938](https://github.com/renoukhan39-bit/domain-reseller/commit/0e7765db8b68fb4662409c52a69b149582b54938). Future agents must check actual current HEAD.
- Deliverable: [PROJECT_CONTINUITY_MASTER.md](PROJECT_CONTINUITY_MASTER.md), this append-only session log, and onboarding entry-point updates.
- Scope: full linked document index, 13 upstream URLs, pinned two-repo analysis, architecture/revenue flow diagrams, 66 task source, 20 acceptance tests, code inventory, test evidence, risks, cost/release roadmap, owner approvals and a copy/paste Codex restart prompt.
- Provenance limitation: full older ChatGPT transcripts are **not available** to reconstruct verbatim. If the owner exports and sanitizes them, add further factual decisions here with links instead of treating summaries as exact raw chat records.
- Default operational posture unchanged: **SALES_ENABLED=false; FULFILLMENT_ENABLED=false**. No code or production operations changed by this documentation-only work.
- Next tasks: (1) review PR #34 and confirm any merge only on owner request; (2) execute clean Compose/PG16 testing; (3) obtain explicit isolated sandbox approval for M4-07 and M3-08 integration acceptance.


## 17 November 2026 — owner-authorized master recovery and functional layout

Starting main: `30fe576f25acc1bbf1733f76bc8b610c9e14dbd1`. Expanded the narrow fetch to seven remote heads and 42 commits. Preserved an all-ref Git bundle and exact snapshots. Recovered five prior project documents plus registrar nameserver ownership guards/tests. Kept the stronger current payment replay design. Consolidated reset templates and gateway validation, then grouped source, tests, templates, tools, docs and reference projects by responsibility. See root `PROJECT_STRUCTURE.md` and `AnalyseFuture` recovery reports for complete path records. The owner later explicitly ordered no tests; none were run after that instruction. Prior passing tests do not validate the final layout. Normal direct main delivery is authorized; no force push, branch deletion, deployment or live purchase. Final commit is discoverable from this record’s Git history; remote CI and account compromise status remain unverified.


## 17 November 2026 — authorized runtime verification after restructuring

The owner superseded the prior pause by asking to test everything. Starting main
was `63dc539e768ae8800aafff1e123afe79d24663cf`. A clean build, PostgreSQL checks,
189 application tests, 17 backup tests, encrypted synthetic recovery, 66-item issue
import dry run, installed-wheel/template/alias checks and live Chromium account
flows passed. Chromium exposed `Origin: null` activation failures under
`no-referrer`; verification pages now use `strict-origin`, with same-origin and
null/cross-origin regression coverage. Five old reset aliases no longer append a
newline. Test fixtures were synthetic and cleaned; no external purchases or live
provider calls occurred. `check --deploy` has the deliberate HSTS-preload warning.
External registrar/payment/SMTP/staging/production acceptance remains open due to
missing configuration/credentials. See `AnalyseFuture/TEST_AND_VALIDATION_REPORT.txt`.
Normal direct main delivery remains the owner's selected workflow; no PR or force
push. The final commit is discoverable from this entry's Git history.

## 2026-11-18 — continued security implementation on a recovery branch

The owner supplied the full audit/recovery mission and requested implementation.
Baseline was `4f484241a7c18726adbd3a3845902fd842c5cd7f` with a clean working tree.
The requested branch `recovery/security-and-account-hardening` supersedes the
older direct-main delivery choice for this round.

Reviewed all 5,355 tracked path identities and seven advertised remote heads.
The 5,019 upstream paths retain their original tree identities. All 20 preserved
branch-recovery blobs match the accessible originals. Selected secret signatures
produced zero candidates across 5,176 historical blobs and 5,019 decompressed ZIP
members. GitHub account access cannot be established from these source checks.
No tracked files were moved or deleted. Repeated README navigation was consolidated.

Implemented M5-08/TD-18/TD-19 improvements with database-enforced normalized email
identity, nondestructive duplicate preflight, signup/admin race handling, profile
locking, view-only evidence administration, stale-claim checking and safe
existing-order retry routing. Hash-locked Python runtime/build dependencies,
least-privilege pinned CI Actions and privacy-safe Gunicorn access logs are included.
The approach is ADAPT/REUSE of existing Django auth/forms/admin/transactions
(BSD-3-Clause) and the existing commerce services. No archived source was adopted.
Application-specific constraints and guards use the repository's existing models.

The complete rebuilt-image suite passed 219 PostgreSQL application tests with
zero skips, against baseline 189. All 17 backup tests, encrypted synthetic restore,
fresh locked wheel install, 16-package advisory scan and real headless Chromium
account flows passed. The initial browser fixture was rejected by Django's password
similarity validator, and an independent password completed the flow. Migration
0004 preserves existing accounts and stops on ambiguous nonblank email groups.
The deployment check reports the deliberate HSTS preload warning. See
[the validation report](../../AnalyseFuture/TEST_AND_VALIDATION_REPORT.txt).

The environment install_script draft was updated and tested with the hash-lock
Dockerfile. Saved startup instructions still use the verified helper. Publication
and fresh-task restoration were not performed. Real provider/payment/SMTP,
infrastructure/alerts/recovery, legal/tax and independent review gates remain open.
Next priorities are authorized registrar/payment sandbox acceptance, real SMTP
delivery, then deployment controls and business requirements for billing.
The tested implementation commits through 88a00b2 were pushed normally to the
recovery branch. The egress proxy rejects api.github.com with a 403 CONNECT
failure. An additive domain allowance was saved in the environment draft for
review. PR creation remains blocked by live API connectivity. The public workflow page
confirmed Python CI success for implementation commit 88a00b2,
[run 44194220815](https://github.com/renoukhan39-bit/domain-reseller/actions/runs/44194220815).
The documentation head was still running when this record was written. Final documentation commits and remote SHA are recorded in
the final response and prepared PR body.
