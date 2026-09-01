# Start Here in the Next Session

Use this document after the local-private Board 14.11 closeout and the
Board 17A team-lifecycle handoff.

Before starting any new board, read `docs/PROJECT_GOAL.md`. It is the
canonical statement of the product初心, the expected user lifecycle and the
non-negotiable control boundaries. Do not infer the project's purpose from the
latest board number alone.

## Current checkpoint

Boards 1 through 12 remain the prepared public release candidate `0.2.0rc1`.
Board 13 is complete only in the local private checkout. No Git tag, GitHub
Release or push has been created for Board 13.

Board 14.0 through Board 14.10 are implemented locally. Board 14.11 completed
one separately authorized, read-only synthetic Manager turn through the
controlled executor after the full experiment and start-approval ladder. Five
earlier attempts failed closed without retry; all six attempts and their
approvals are terminal and cannot be reused. Board 14 is complete only in the
local private checkout and does not alter the public `0.2.0rc1` release
candidate.

Board 15 is complete. It adds a public-safe project-status page, aligns the
authoritative Board 13/14 state and protects it with deterministic regression
coverage. It creates no external-call authority.

Board 16 remains deferred because one local Windows loopback interruption did
not reproduce. Board 17A is complete for the local offline team-lifecycle
vertical slice. The normal CLI `run` entry point now requires a one-time
Supervisor project-run approval bound to the current ready team and exact goal.
Artifact retention/purge remains deferred and separately scoped.

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
docs/reports/2026-09-01-board-14-next-session-handoff.md
docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md
docs/reports/2026-09-01-board-15-project-rebaseline-plan.md
docs/reports/2026-09-01-board-15-project-rebaseline.md
docs/reports/2026-09-01-pre-board-17-artifact-retention-handoff.md
docs/reports/2026-09-01-board-17a-team-lifecycle-plan.md
docs/reports/2026-09-01-board-17a-team-lifecycle.md
docs/reports/2026-09-01-board-17a-next-session-handoff.md
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

Board 14.11 records the privacy-safe closeout: the one authorized turn
completed under the v2 output contract and the bound usage/token controls,
without copying prompt, response, JSONL, stdout, stderr or exact Provider
records into tracked files. Its earlier continuation handoff is historical;
the ignored local supplement remains runtime-only and must never be committed
or transmitted to an external model.

## Required next-session sequence

1. Work directly in the existing repository; do not create a replacement
   repository or worktree for routine maintenance.
2. Verify the checkout is clean. The local Board 13 commit intentionally does
   not match `origin/main` until an explicit future publishing decision.
3. Run the full offline suite, compilation and history privacy scan.
4. Read `docs/PRIVACY_ISSUES.md` before changing any data boundary.
5. Treat Board 14 as terminal. Freeze a distinct new board or release scope
   before implementation; no Board 14 experiment or approval authorizes a
   follow-up call.
6. For future work, read the canonical goal and the latest Board 17A report,
   then freeze a new scope before changing real Agent readiness, retention,
   cleanup, Provider, transport or workspace behavior.

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
- The completed Board 14 experiment and its consumed start approval are never
  replayed or used as authority for another call.

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

The complete offline suite contains one hundred and thirty-four tests after the
Board 17A project-run authorization coverage. The release verifier remains the
Board 12 public-release gate and
requires a clean
synchronized `main`; do not expect it to pass while this intentionally
unpublished local incubation branch is ahead of `origin/main`.
