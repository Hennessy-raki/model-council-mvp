# Start Here in the Next Session

Use this document when continuing in a new Codex conversation.

## Suggested opening prompt

```text
Continue development directly in the existing Model Council repository supplied
for this task. Do not create a copy in the new task's default directory.

Before changing code, read AGENTS.md, README.md, docs/ARCHITECTURE.md,
docs/PROJECT_HANDOFF.md, docs/ROADMAP.md, docs/DEVELOPMENT_BOARDS.md,
docs/START_HERE_NEXT_SESSION.md, the four completed Board 1-4 reports, and
docs/reports/2026-08-29-pre-board-5-session-handoff.md.

Verify that git main contains implementation commit 7947ef1 and the later
pre-Board-5 handoff checkpoint, that the worktree is clean, and that local main
matches the public GitHub repository. Run the 29 existing tests, offline demo,
doctor, discovery scan and ledger summary before implementation.

Then implement Productization Board 5: routing policy. Support manual,
automatic and hybrid selection; capability, availability, cost and latency
constraints; user locks; required model separation; durable routing
explanations; safe SQLite migration; and sufficient automated tests. Consume
the existing registry, provenance, discovery and ledger contracts. Preserve
JSON as seed configuration and protect user-owned settings.

Do not build the Board 6 Web UI, Codex App Server, A2A, MCP, worktree
automation, a new billing system or broad real-model startup. The real Codex
pilot remains paused unless the user separately gives explicit authorization
to send repository content or derived details to an external model service.

Finish Board 5 with its own report, roadmap and handoff updates, sensitive-data
scan, commit, push and remote-main verification. Report the board outcome to
the user before beginning any later board.
```

## Repository orientation

- `model_council/orchestrator.py`: deterministic workflow
- `model_council/manager.py`: model-generated plan and synthesis
- `model_council/adapters/`: model-host integrations
- `model_council/store.py`: SQLite persistence
- `model_council/artifacts.py`: content-addressed files
- `model_council/discovery.py`: startup discovery and isolated probes
- `model_council/ledger.py`: usage, cost, budget and balance ledger
- `artifact_attributions`: internal contributor/reviewer/integrator audit table
- `agent_discovery`: persisted discovery and setup observations
- `usage_events`, `budget_policies`, `budget_alerts`: ledger tables
- `config.example.json`: stable offline baseline
- `config.codex.example.json`: next pilot
- `protocol/`: communication schema drafts
- `tests/`: regression baseline
- `docs/reports/2026-08-29-pre-board-5-session-handoff.md`: frozen Board 5
  starting context and acceptance boundary

## First checks

```powershell
python --version
python -m unittest discover -s tests -v
python -m model_council demo "验证多模型协作闭环"
python -m model_council doctor --config config.codex.example.json
python -m model_council discovery scan --config config.example.json
python -m model_council ledger summary --config config.example.json
```

Expected baseline: twenty-nine tests pass, doctor resolves `codex.cmd`, and the demo produces a completed run with
worker results, an independent review and a final report. Discovery scan must
not run a connectivity probe. Ledger values must retain their measurement
source instead of treating estimates or unavailable data as actual.
