# Start Here in the Next Session

Use this document when continuing in a new Model Council conversation.

## Current checkpoint

Productization Boards 1 through 6 are complete. The authoritative Board 6
report is:

```text
docs/reports/2026-08-30-board-6-local-settings-interface.md
```

Board 7 is not authorized or implemented. The real Codex pilot also remains
paused until the user gives separate, explicit authorization to send repository
content or derived private details to an external model service.

## Suggested opening prompt

```text
Continue directly in the existing Model Council repository supplied for this
task. Do not create a replacement repository.

Before changing code, read AGENTS.md, README.md, docs/ARCHITECTURE.md,
docs/PROJECT_HANDOFF.md, docs/ROADMAP.md, docs/DEVELOPMENT_BOARDS.md,
docs/PRIVACY.md, docs/START_HERE_NEXT_SESSION.md and
docs/reports/2026-08-30-board-6-local-settings-interface.md.

Verify the clean public main baseline and run the offline tests and privacy
scan. Inspect the Board 6 local settings interface only on loopback. Do not
invoke a real external model, discovery probe or Provider balance endpoint.

Do not begin Board 7 Codex App Server, A2A, MCP or remote Agent
interoperability without a new explicit user authorization. Keep SQLite
authoritative and preserve deterministic routing and user-owned settings.
```

## Repository orientation

- `model_council/web.py`: loopback-only Board 6 settings interface
- `model_council/registry.py`: SQLite registry and user-owned edit operations
- `model_council/orchestrator.py`: deterministic workflow
- `model_council/store.py`: SQLite persistence
- `model_council/discovery.py`: startup discovery and isolated probes
- `model_council/ledger.py`: usage, cost, budget and balance ledger
- `model_council/routing.py`: deterministic role selection and audit evidence
- `artifact_attributions`: internal contributor/reviewer/integrator audit table
- `agent_discovery`: persisted discovery and setup observations
- `usage_events`, `budget_policies`, `budget_alerts`: ledger tables
- `routing_decisions`: durable selected and rejected routing evidence
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
python scripts/privacy_scan.py --history
python -m model_council web --config config.example.json
```

Expected baseline: forty-five tests pass. The local Web server binds to
loopback, displays persisted evidence and writes only user-owned SQLite
records. It must not call a model or external service.
