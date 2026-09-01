# Start Here in the Next Session

Use this document after the local-only Board 14 preparation commit.

## Current checkpoint

Boards 1 through 12 remain the prepared public release candidate `0.2.0rc1`.
Board 13 is complete only in the local private checkout. No Git tag, GitHub
Release or push has been created for Board 13.

Board 14.0, Board 14.1 preparation, Board 14.2 offline App Server verification,
Board 14.3 controlled-executor verification, Board 14.4 usage compatibility
repair, Board 14.5 executor-integrity binding, and Board 14.6 privacy-safe
usage-failure diagnostics, and Board 14.7 privacy-safe Manager output-contract
diagnostics, and Board 14.8 contract-bound synthetic prompt repair are
implemented locally. Board 14.9 explicit Provider input/output budget repair is
also implemented locally. Board 14 remains in progress because five separately
authorized real synthetic attempts failed closed and none is eligible for
retry.

The latest scope and completion reports are:

```text
docs/reports/2026-08-31-board-12-product-release-plan.md
docs/reports/2026-08-31-board-12-product-release.md
docs/reports/2026-08-31-board-13-supervisor-team-readiness-plan.md
docs/reports/2026-08-31-board-13-supervisor-team-readiness.md
docs/reports/2026-08-31-board-14-local-multi-agent-experiment-plan.md
docs/reports/2026-08-31-board-14-local-multi-agent-experiment-preparation.md
docs/reports/2026-08-31-board-14-2-offline-app-server-execution-plan.md
docs/reports/2026-08-31-board-14-2-offline-app-server-execution.md
docs/reports/2026-08-31-board-14-3-controlled-executor-plan.md
docs/reports/2026-08-31-board-14-3-controlled-executor.md
docs/reports/2026-08-31-board-14-4-usage-compatibility-repair-plan.md
docs/reports/2026-08-31-board-14-4-usage-compatibility-repair.md
docs/reports/2026-08-31-board-14-5-executor-integrity-plan.md
docs/reports/2026-08-31-board-14-5-executor-integrity.md
docs/reports/2026-08-31-board-14-6-usage-failure-diagnostics-plan.md
docs/reports/2026-08-31-board-14-6-usage-failure-diagnostics.md
docs/reports/2026-08-31-board-14-7-output-contract-diagnostics-plan.md
docs/reports/2026-08-31-board-14-7-output-contract-diagnostics.md
docs/reports/2026-08-31-board-14-8-contract-bound-synthetic-prompt-plan.md
docs/reports/2026-08-31-board-14-8-contract-bound-synthetic-prompt.md
docs/reports/2026-09-01-board-14-9-provider-input-budget-plan.md
docs/reports/2026-09-01-board-14-9-provider-input-budget.md
docs/reports/2026-09-01-board-14-10-cost-feasibility-plan.md
docs/reports/2026-09-01-board-14-10-cost-feasibility.md
```

Board 12 adds the loopback-only product interface, unified approval center,
workspace/repair/evaluation evidence views, deterministic run comparison,
privacy-safe local backup/restore and repeatable release-candidate
verification.

Board 13 adds `model_council/supervisor.py`: an independent local team wizard,
synthetic readiness reports, explicit confirmation state, SHA-256 team
snapshots, stale-on-drift start approvals and a local fake Manager platform.
It invokes no Adapter, process, network endpoint, model or task execution.

Board 14 adds `model_council/experiments.py`. Its `synthetic_fake` mode can
complete a zero-call simulation. Its `real_codex` mode uses a separately
approved one-time controlled executor after all experiment and start-approval
gates have passed.

Board 14.2 adds an opt-in `strict_no_approvals` App Server policy. The public
Board 14 candidate enables it: a server-side interactive approval request is
declined and terminates the turn. The protocol was exercised only against the
repository fake App Server. The local 14.1 manifest is approved but unarmed;
do not arm it for a real pilot because it predates the strict policy.

Board 14.3 adds a second SHA-256-bound start approval that is consumed once
before the controlled executor can start a process. Board 14.4 adds
fail-closed usage compatibility for supported App Server locations. Both were
verified only against repository fake App Server fixtures. The executor stores
response hashes and byte counts rather than response text.

Board 14.5 binds the controlled-executor and JSON-lines transport source
hashes into every new start approval. A source change after approval makes that
approval stale before any process can start.

Board 14.6 records an ignored local usage diagnostic when a completed Manager
turn fails the hard usage gate. It distinguishes unavailable, incomplete and
over-limit usage while retaining no raw JSONL, prompt, response or transcript.

Board 14.7 validates the frozen two-Worker Manager plan and records only
output-contract failure class, output SHA-256 and byte count when the plan is
invalid. It does not retain the output text.

Board 14.8 resolves the fourth attempt's actionable product cause: the
canonical `manager_two_worker_plan_v2` prompt is generated from the two bound
mock Worker IDs and states the exact JSON shape already enforced locally.
Generic or edited prompts cannot prepare an experiment. It creates no new
candidate and grants no App Server or model-call authority.

Board 14.9 follows a fifth attempt that failed at complete Provider input
usage above the total cap. Future scopes may set explicit
`max_input_tokens` and `max_output_tokens`; each is SHA-256-bound, must be
compatible with `max_total_tokens`, and fails closed independently. No host or
Provider context is treated as free or inferred from prompt bytes.

Board 14.10 requires a future high-input scope to bind a declared
currency-matching price schedule and prove the maximum token envelope fits the
cost cap before it can be prepared.

## Required next-session sequence

1. Work directly in the existing repository; do not create a replacement
   repository or worktree for routine maintenance.
2. Verify the checkout is clean. The local Board 13 commit intentionally does
   not match `origin/main` until an explicit future publishing decision.
3. Run the full offline suite, compilation and history privacy scan.
4. Read `docs/PRIVACY_ISSUES.md` before changing any data boundary.
5. Freeze a new board or release scope before implementation.

Do not create a tag or GitHub Release unless the user explicitly requests it.
Do not interpret the Board 11 live synthetic approval as authorization for a
new model call or for repository-, workspace-, repair- or evaluation-derived
context.

## Preserved control boundaries

- SQLite is the authoritative local state.
- Page refresh performs no model, network, Git, test, merge, discard or restore
  action.
- Outbound context, MCP execution, workspace merge/discard and backup restore
  retain separate approvals and consumption steps.
- Backup defaults to SQLite only; Artifact inclusion is explicit.
- Backups never include credentials, environment files, repositories or
  worktrees.
- Repair goals, feedback, diffs, evaluation output and backup contents remain
  private local runtime data.
- Supervisor bindings, readiness reports, confirmations, snapshots, approvals
  and fake Manager events remain private local runtime data.
- Experiment prompts, transport metadata, identities, budgets, approvals and
  evidence remain private local runtime data.

## Repository orientation

- `model_council/web.py`: loopback product interface and approval/evidence views
- `model_council/backup.py`: verified backup, exact restore approval and safety
  backup
- `model_council/comparison.py`: local run summaries and pairwise deltas
- `model_council/release.py`: repeatable release-candidate verification
- `model_council/evaluation.py`: Board 11 objective evaluation evidence
- `model_council/repair.py`: Board 10 bounded repair/recovery
- `model_council/workspaces.py`: Board 9 worktrees and merge/discard approvals
- `model_council/outbound_context.py`: exact external-context manifests
- `model_council/supervisor.py`: local team readiness and start approval
- `model_council/experiments.py`: controlled experiment manifests and evidence
- `docs/RELEASE.md`: release-candidate instructions
- `docs/PRIVACY.md` and `docs/PRIVACY_ISSUES.md`: privacy gates and register

## First checks

```powershell
python --version
git status --short --branch
python -m unittest discover -s tests -v
python -m compileall -q model_council tests scripts
python scripts/privacy_scan.py --history
```

The complete offline suite contains one hundred and twenty-seven tests after
Board 14.10. The release verifier remains the Board 12 public-release gate and
requires a clean
synchronized `main`; do not expect it to pass while this intentionally
unpublished local incubation branch is ahead of `origin/main`.
