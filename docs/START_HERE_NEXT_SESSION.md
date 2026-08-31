# Start Here in the Next Session

Use this document after the Board 12 release-candidate commit.

## Current checkpoint

Productization Boards 1 through 12 are complete. The prepared version is
`0.2.0rc1`. No Git tag or GitHub Release has been created.

The latest scope and completion reports are:

```text
docs/reports/2026-08-31-board-12-product-release-plan.md
docs/reports/2026-08-31-board-12-product-release.md
```

Board 12 adds the loopback-only product interface, unified approval center,
workspace/repair/evaluation evidence views, deterministic run comparison,
privacy-safe local backup/restore and repeatable release-candidate
verification.

## Required next-session sequence

1. Work directly in the existing repository; do not create a replacement
   repository or worktree for routine maintenance.
2. Verify the checkout is clean and `HEAD`, `main`, `origin/main` and the
   public remote `main` agree.
3. Run `python scripts/release_verify.py`.
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
- `docs/RELEASE.md`: release-candidate instructions
- `docs/PRIVACY.md` and `docs/PRIVACY_ISSUES.md`: privacy gates and register

## First checks

```powershell
python --version
git status --short --branch
python -m unittest discover -s tests -v
python -m compileall -q model_council tests scripts
python scripts/privacy_scan.py --history
python scripts/release_verify.py
```

The complete offline suite contains ninety-three tests at Board 12 closure.
The release verifier additionally requires a clean synchronized `main`, all
required Board 1-12 documents, safe tracked filenames and a GitHub noreply
commit-author address.
