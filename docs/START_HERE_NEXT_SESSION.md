# Start Here in the Next Session

Use this document when continuing in the fresh Model Council conversation
created after Board 10.

## Current checkpoint

Productization Boards 1 through 10 are complete. Board 11 must be completed
first; Board 12 follows in the same new session only after Board 11 passes its
full delivery and privacy gates.

The latest scope and completion reports are:

```text
docs/reports/2026-08-30-board-10-bounded-repair-recovery-plan.md
docs/reports/2026-08-30-board-10-bounded-repair-recovery.md
```

Board 10 adds persistent bounded repair sessions, per-iteration checkpoint/test/
diff evidence, deterministic acceptance, optional usage budgets and explicit
interrupted-stage recovery. All verification used temporary synthetic Git
repositories and local callbacks. No real Agent, external endpoint,
repository-context model call or Model Council worktree was used.

## Required next-session sequence

### Board 11: second real Agent family and objective evaluation

Before implementation, freeze:

- exactly one additional Agent family and one narrow role;
- synthetic evaluation tasks and objective acceptance metrics;
- exact endpoint, model, credential environment variable and invocation gate;
- exact outbound prompt, files, Artifacts, paths and byte limits;
- evaluation comparison against the existing baseline;
- failure, cost and privacy rollback behavior.

Do not send repository content, repair bundles or private-derived context to
the new Agent without displaying the exact outbound scope and obtaining
explicit authorization for that invocation. Complete Board 11 tests, report,
privacy scan, commit, push and remote verification before Board 12.

### Board 12: product interface and release preparation

After Board 11 is complete:

- add the local product approval center;
- expose workspace/repair/evaluation evidence without moving it out of SQLite;
- add run comparison;
- add bounded local backup/restore with privacy-safe defaults;
- complete release documentation, security/privacy review and release
  candidate verification.

Do not weaken Board 8 context approval, Board 9 merge/discard approval or Board
10 repair limits for UI convenience.

## Suggested opening prompt

```text
Continue directly in the existing Model Council repository supplied for this
task. Do not create a replacement repository.

Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/PROJECT_HANDOFF.md,
docs/ROADMAP.md, docs/DEVELOPMENT_BOARDS.md, docs/PRIVACY.md,
docs/PRIVACY_ISSUES.md, docs/START_HERE_NEXT_SESSION.md, and the Board 10
plan/report.

Verify the clean published main baseline, run all seventy-three offline tests and
run python scripts/privacy_scan.py --history.

Complete Board 11 first: one second real Agent family plus objective synthetic
evaluation. Freeze its exact endpoint, role, context inventory, byte/file/
Artifact limits, credentials boundary, metrics and failure rollback before
code. A live call or repository-derived disclosure still requires exact user
authorization; prior invoke_enabled, worktree or repair permissions do not
authorize it.

After Board 11 is fully tested, reported, scanned, committed, pushed and
remotely verified, complete Board 12: local product interface, approval center,
run comparison, privacy-safe backup/restore and release preparation.

Keep SQLite authoritative. Never commit runtime databases, worktrees, repair
goals/feedback, evaluation prompts/results containing private context, personal
paths, credentials or private project content.
```

## Repository orientation

- `model_council/repair.py`: Board 10 sessions, iterations, budgets, review and
  recovery
- `model_council/workspaces.py`: Board 9 worktrees, evidence and merge/discard
  approval
- `model_council/outbound_context.py`: exact external context manifests
- `model_council/interoperability.py`: App Server, A2A and MCP state/contracts
- `model_council/ledger.py`: usage, cost and budget evidence
- `model_council/routing.py`: deterministic role selection
- `model_council/web.py`: current local settings interface
- `model_council/store.py`: additive SQLite schema
- `docs/PRIVACY.md`, `docs/PRIVACY_ISSUES.md` and
  `scripts/privacy_scan.py`: release privacy gates

## First checks

```powershell
python --version
python -m unittest discover -s tests -v
python -m model_council repair list --config config.example.json
python -m model_council workspace list --config config.example.json
python -m model_council interop show --config config.interop.example.json
python scripts/privacy_scan.py --history
```

Expected baseline: seventy-three tests pass. The list/show commands may
initialize ignored local SQLite state but must not start an Agent, model,
network request or Git worktree.
