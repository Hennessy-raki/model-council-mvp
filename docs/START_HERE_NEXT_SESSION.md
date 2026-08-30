# Start Here in the Next Session

Use this document when continuing in a new Model Council conversation.

## Current checkpoint

Productization Boards 1 through 9 are complete. Board 10 is ready for planning
but implementation has not started.

The latest scope and completion reports are:

```text
docs/reports/2026-08-30-board-9-isolated-git-worktrees-plan.md
docs/reports/2026-08-30-board-9-isolated-git-worktrees.md
```

Board 9 adds persistent isolated Git worktrees, explicit read/write/test/merge
permissions, bounded diff/test evidence, exact single-use merge approval and
exact destructive-discard approval. All automated verification used temporary
synthetic Git repositories. No Model Council repository worktree, real Agent,
external endpoint or repository-context model call was used.

Board 8's external boundary remains unchanged: one functionally successful
live synthetic read-only Codex run exists, but repository-context, A2A and MCP
live operation remain unverified and separately gated.

## Suggested opening prompt

```text
Continue directly in the existing Model Council repository supplied for this
task. Do not create a replacement repository.

Before changing code, read AGENTS.md, README.md, docs/ARCHITECTURE.md,
docs/PROJECT_HANDOFF.md, docs/ROADMAP.md, docs/DEVELOPMENT_BOARDS.md,
docs/PRIVACY.md, docs/PRIVACY_ISSUES.md, docs/START_HERE_NEXT_SESSION.md and
the Board 9 plan/report.

Verify the clean public main baseline, run all sixty-two offline tests and run
the full-history privacy scan. Keep SQLite authoritative.

Board 9 is complete. Worktree paths, repository paths, Agent identities, diffs,
test commands and output excerpts are private ignored runtime state. Do not
copy them into public reports. New leases begin read-only; merge and destructive
discard require current evidence plus a matching single-use scope SHA-256.

Do not set invoke_enabled=true, call a live Codex App Server, contact an A2A
Agent, connect an MCP server or send repository content externally without
explicit user authorization for that exact pilot. Credentials remain
environment-variable references.

The next board is Board 10: bounded reviewer-writer repair loops and recovery.
Freeze iteration, retry, time, token/cost and changed-file limits before
implementation. Do not add the Board 11 second real Agent family or Board 12 UI.
```

## Repository orientation

- `model_council/workspaces.py`: worktree leases, permissions, bounded evidence
  and exact merge/discard approvals
- `model_council/interoperability.py`: endpoint, session, event, approval and
  MCP broker contracts
- `model_council/adapters/codex_app_server.py`: persistent Codex Threads/Turns
- `model_council/adapters/cli.py`: CLI sandbox observation and dynamic isolated
  workspace invocation
- `model_council/orchestrator.py`: deterministic collaboration workflow
- `model_council/store.py`: additive SQLite schema and persistence
- `model_council/ledger.py`: usage, cost, budget and balance ledger
- `model_council/routing.py`: deterministic role selection and audit evidence
- `docs/PRIVACY.md`, `docs/PRIVACY_ISSUES.md` and
  `scripts/privacy_scan.py`: public-repository privacy gates

## First checks

```powershell
python --version
python -m unittest discover -s tests -v
python -m model_council demo "验证当前协作闭环"
python -m model_council doctor --config config.codex.example.json
python -m model_council discovery scan --config config.example.json
python -m model_council ledger summary --config config.example.json
python -m model_council routing decisions --config config.example.json
python -m model_council interop show --config config.interop.example.json
python -m model_council workspace list --config config.example.json
python scripts/privacy_scan.py --history
```

Expected baseline: sixty-two tests pass. `interop show` may synchronize
disabled endpoint identities and `workspace list` may initialize ignored
runtime SQLite state; neither operation starts a model, network request or Git
worktree.
