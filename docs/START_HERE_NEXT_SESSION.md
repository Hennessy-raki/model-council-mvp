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

Board 17B is complete for deterministic local Agent lifecycle fixtures only.
It does not qualify a real Agent or authorize a new model call. Read the
Board 17B report before freezing any real-Agent, Provider, transport, workspace
or retention scope.

Board 18 is complete for one explicit local fake subprocess fixture only. It
uses `shell=False`, stores bounded process evidence, and does not qualify a
real Agent or authorize a new model call.

Board 19 is complete for local project-run approval hardening. Production
Python and CLI project-run entry points now fail closed without exact
Supervisor approval; the private offline test mode is not a product entry
point.

Board 20 is complete for one bounded CLI `lifecycle-sequence` using the
built-in local fake subprocess. It does not qualify a real Agent or authorize
a new model call.

Board 21 is complete for a pure local `qualification-preflight` validator. It
does not load project configuration, start a process, qualify a real Agent or
authorize a new model call.

Board 22 is complete for binding eligible preflight results to non-mock
Supervisor roles and approval provenance. It does not qualify a real Agent or
authorize a new model call.

Board 23 is complete for local qualification provenance integrity and
revalidation. It does not qualify a real Agent or authorize a new model call.

Board 24 is scope-frozen for offline preparation of a real-Agent
qualification authorization package. It does not start or qualify an Agent.
Actual Model identity and the exact working directory remain unresolved.

## Checkpoint after the 2026-10-14 boards

A second development owner resumed the project on 2026-10-14 and added four
boards. Read this section before acting on any earlier statement in this file,
because several earlier statements describe a state that has since moved.

- **Board 25** independently audited Boards 1 through 23 instead of inheriting
  their acceptance claims, and recomputed the local disclosure surface against
  the owner's restated requirement that no information about this machine be
  recoverable by another party. It added `--local-state` to the privacy scanner
  and removed machine-identifying values from newly persisted Artifact records.
- **Board 24**'s frozen offline scope was then implemented: a deterministic,
  privacy-safe authorization package, the read-only `authorization build` and
  `authorization verify` commands, and a working-directory reference by category
  and environment-variable name rather than by value.
- **Board 26** made a built package bindable to one role, captured against the
  current team snapshot, re-validated on every read, and projected read-only
  through the CLI and the loopback Web view.
- **Board 27** added a version comparison engine with an operator-controlled
  preference, and replaced the hardcoded four-vendor discovery list with a
  configuration-driven catalogue that can record a GUI-only Agent without
  claiming it is invocable.

Two environment facts changed since Board 23 and are worth re-measuring rather
than trusting: the Codex CLI reports a different version than the recorded
0.150.1, and the machine now has several Agent applications that the earlier
four-name discovery could not see. The version engine reports the first; the
configuration-driven catalogue handles the second.

The reports for the new boards are:

```text
docs/reports/2026-10-14-board-25-foundation-audit-and-trust-surface.md
docs/reports/2026-10-14-board-24-real-agent-qualification-authorization-implementation.md
docs/reports/2026-10-14-board-26-authorization-package-binding-and-projection.md
```

Board 27's changes are recorded in `docs/DEVELOPMENT_BOARDS.md` and in the two
commits that carry them. None of these boards authorizes an external call, and
the consumed Board 8, 11 and 14 approvals remain terminal.

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
docs/reports/2026-09-01-board-17b-agent-lifecycle-verification-plan.md
docs/reports/2026-09-01-board-17b-agent-lifecycle-verification.md
docs/reports/2026-09-01-board-18-local-subprocess-lifecycle-plan.md
docs/reports/2026-09-01-board-18-local-subprocess-lifecycle.md
docs/reports/2026-09-01-board-18-next-session-handoff.md
docs/reports/2026-09-03-board-19-project-run-approval-hardening-plan.md
docs/reports/2026-09-03-board-19-project-run-approval-hardening.md
docs/reports/2026-09-03-board-19-next-session-handoff.md
docs/reports/2026-09-03-board-20-cli-local-lifecycle-plan.md
docs/reports/2026-09-03-board-20-cli-local-lifecycle.md
docs/reports/2026-09-03-board-20-next-session-handoff.md
docs/reports/2026-09-03-board-21-offline-agent-qualification-preflight-plan.md
docs/reports/2026-09-03-board-21-offline-agent-qualification-preflight.md
docs/reports/2026-09-03-board-22-qualification-binding-plan.md
docs/reports/2026-09-03-board-22-qualification-binding.md
docs/reports/2026-09-09-board-23-qualification-integrity-plan.md
docs/reports/2026-09-09-board-23-qualification-integrity.md
docs/reports/2026-09-09-board-24-real-agent-qualification-authorization-plan.md
docs/reports/2026-09-09-board-24-real-agent-qualification-authorization-freeze.md
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

The complete offline suite contains two hundred and thirty-four tests after the
Board 27 discovery and version work. Re-measure the exact count from the
current suite output instead of trusting this number; it changes with every
board. The measured total, the package line count and the tracked-file count
are recorded together in `docs/reports/` for the board that most recently
changed them. The latest detailed continuation
checkpoint is:

```text
docs/reports/2026-09-03-development-handoff-next-session.md
```

The release verifier remains the
Board 12 public-release gate and
requires a clean
synchronized `main`; do not expect it to pass while this intentionally
unpublished local incubation branch is ahead of `origin/main`.
