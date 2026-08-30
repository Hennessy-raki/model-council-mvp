# Start Here in the Next Session

Use this document when continuing in a new Model Council conversation.

## Current checkpoint

Productization Boards 1 through 8 are complete. The authoritative Board 7
report is:

```text
docs/reports/2026-08-30-board-7-persistent-remote-interoperability.md
```

The Board 8 scope and completion report are:

```text
docs/reports/2026-08-30-board-8-controlled-live-pilot-plan.md
docs/reports/2026-08-30-board-8-controlled-live-pilot.md
```

Board 7 protocol coverage uses local fake Codex App Server, A2A and MCP
transports. Board 8 additionally completed one live synthetic read-only Codex
App Server pilot with mock manager/reviewer, zero files, zero Artifacts and an
exact one-time prompt approval. A2A, MCP and repository-context live operation
remain unverified.

## Suggested opening prompt

```text
Continue directly in the existing Model Council repository supplied for this
task. Do not create a replacement repository.

Before changing code, read AGENTS.md, README.md, docs/ARCHITECTURE.md,
docs/PROJECT_HANDOFF.md, docs/ROADMAP.md, docs/DEVELOPMENT_BOARDS.md,
docs/PRIVACY.md, docs/START_HERE_NEXT_SESSION.md and
docs/reports/2026-08-30-board-7-persistent-remote-interoperability.md.

Verify the clean public main baseline, run all fifty-five offline tests and run the
full-history privacy scan. Keep SQLite authoritative.

Do not set invoke_enabled=true, call a live Codex App Server, contact an A2A
Agent, connect an MCP server or send repository content externally without
explicit user authorization for that exact pilot. Credentials must remain
environment-variable references. MCP tools require a persisted single-use
approval.

Board 8 is complete. Any future live pilot must show
`interop context <MANIFEST_ID> --show-prompt` to the user, obtain explicit
authorization for that exact prompt, and approve the matching SHA-256 once.
Do not expand the context to repository content or begin Board 9 without a new
Board definition.
```

## Repository orientation

- `model_council/interoperability.py`: endpoint, session, event, approval and
  MCP broker contracts
- `model_council/adapters/codex_app_server.py`: persistent Codex Threads/Turns
- `model_council/adapters/a2a.py`: A2A Agent Card, Message and Task client
- `model_council/web.py`: local settings and interoperability evidence UI
- `model_council/registry.py`: SQLite registry and user-owned edit operations
- `model_council/orchestrator.py`: deterministic workflow
- `model_council/store.py`: additive SQLite schema and persistence
- `model_council/discovery.py`: startup discovery and isolated probes
- `model_council/ledger.py`: usage, cost, budget and balance ledger
- `model_council/routing.py`: deterministic role selection and audit evidence
- `config.interop.example.json`: disabled-by-default protocol configuration
- `docs/PRIVACY.md` and `scripts/privacy_scan.py`: public-repository privacy
  gate

## First checks

```powershell
python --version
python -m unittest discover -s tests -v
python -m model_council demo "验证本地协作闭环"
python -m model_council doctor --config config.codex.example.json
python -m model_council discovery scan --config config.example.json
python -m model_council ledger summary --config config.example.json
python -m model_council routing decisions --config config.example.json
python -m model_council interop show --config config.interop.example.json
python scripts/privacy_scan.py --history
python -m model_council web --config config.example.json
```

Expected baseline: fifty-one tests pass. `interop show` may synchronize disabled
endpoint identities into ignored local runtime state but must not start a
process or network request. The Web server binds to loopback.
