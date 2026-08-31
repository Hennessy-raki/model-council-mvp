# Start Here in the Next Session

Use this document after the local-only Board 13 Supervisor commit.

## Current checkpoint

Boards 1 through 12 remain the prepared public release candidate `0.2.0rc1`.
Board 13 is complete only in the local private checkout. No Git tag, GitHub
Release or push has been created for Board 13.

The latest scope and completion reports are:

```text
docs/reports/2026-08-31-board-12-product-release-plan.md
docs/reports/2026-08-31-board-12-product-release.md
docs/reports/2026-08-31-board-13-supervisor-team-readiness-plan.md
docs/reports/2026-08-31-board-13-supervisor-team-readiness.md
```

Board 12 adds the loopback-only product interface, unified approval center,
workspace/repair/evaluation evidence views, deterministic run comparison,
privacy-safe local backup/restore and repeatable release-candidate
verification.

Board 13 adds `model_council/supervisor.py`: an independent local team wizard,
synthetic readiness reports, explicit confirmation state, SHA-256 team
snapshots, stale-on-drift start approvals and a local fake Manager platform.
It invokes no Adapter, process, network endpoint, model or task execution.

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

The complete offline suite contains one hundred tests after Board 13. The
release verifier remains the Board 12 public-release gate and requires a clean
synchronized `main`; do not expect it to pass while this intentionally
unpublished local Board 13 commit is ahead of `origin/main`.
