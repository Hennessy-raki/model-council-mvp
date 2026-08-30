# Start Here in the Next Session

Use this document when continuing after Board 11.

## Current checkpoint

Productization Boards 1 through 11 are complete. Board 12 is the active board.

The latest scope and completion reports are:

```text
docs/reports/2026-08-30-board-11-second-agent-evaluation-plan.md
docs/reports/2026-08-30-board-11-second-agent-evaluation.md
```

Board 11 adds a DeepSeek Responses `synthetic_evaluator`, exact single-use
outbound approval, bounded request/response context and objective local
evidence. One authorized 937-byte synthetic scope was consumed once. Transport
and ledger recording succeeded; the 131-byte response failed the required
16-byte exact-token metric. No retry, file, Artifact, repository, worktree or
repair context was used.

## Required next-session sequence

### Board 11: second real Agent family and objective evaluation

Status: complete. Preserve its exact-context gate and recorded failed objective
outcome. Do not reinterpret the live synthetic approval as authorization for a
new call or repository-derived context.

### Board 12: product interface and release preparation

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
docs/PRIVACY_ISSUES.md, docs/START_HERE_NEXT_SESSION.md, and the Board 11
plan/report.

Verify the clean published main baseline, run all eighty-one offline tests and
run python scripts/privacy_scan.py --history.

Board 11 is complete. Preserve its recorded objective failure and do not retry
or disclose a different context under its consumed approval.

Complete Board 12: local product interface, approval center, workspace/repair/
evaluation evidence views, run comparison, privacy-safe backup/restore and
release preparation.

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
