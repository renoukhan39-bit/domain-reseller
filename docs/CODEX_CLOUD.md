# Codex Cloud & Astra — contributor instructions

Codex Cloud can edit code and run tests on a configured GitHub environment; model selection, limits and costs depend on the current subscription. It is not an unlimited unattended development team.

## Paste this into Codex when starting a task

> Work in `renoukhan39-bit/domain-reseller`, our canonical project. Start by reading `docs/START_HERE.md`, `README.md`, `AGENTS.md`, `docs/PROJECT_GOAL.md`, `docs/TASKS.md`, `docs/ROADMAP.md`, and `docs/REUSE_FIRST_STRATEGY.md`. We want an independently developed GoDaddy/Namecheap-style domain and web-services product, not a mock demo. Do not merge upstream applications. First audit current code and tests, select one P0 task, implement on a feature branch, run and report checks/tests, update docs, and create a pull request. Do not use real registrar balances, payment keys or paid cloud infrastructure without owner approval. Preserve safety, license, customer data and transaction invariants.

## Credit-saving rules
1. Before adding a feature, search existing code and upstream packages; classify `CONFIGURE`, `REUSE`, `ADAPT` or `BUILD`.
2. Use small milestones and CI logs. Avoid repeated architecture rewrites or full-project regeneration.
3. Study PNLCS, FOSSBilling, Upmind, Namingo, Paymenter as references only, respecting licenses.
4. Do not claim that mocked or syntax-only tests are equivalent to provider sandbox tests.
5. PR must document task ID, actual command results, security/financial risks, rollback and external blockers.
6. Live domain purchases, enabling fulfillment, spending credits, changing production and other irreversible actions need explicit approval.

## First recommended task
Verify clean install, migrations and green CI (`M0-09`), then investigate the registrar API endpoint version and sandbox acceptance before writing new features.
