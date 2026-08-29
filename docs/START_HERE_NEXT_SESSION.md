# Start Here in the Next Session

Use this document when continuing in a new Codex conversation.

## Suggested opening prompt

```text
Continue development directly in the existing Model Council repository supplied
for this task. Do not create a copy in the new task's default directory.

Before changing code, read AGENTS.md, README.md, docs/ARCHITECTURE.md,
docs/PROJECT_HANDOFF.md, docs/ROADMAP.md, docs/DEVELOPMENT_BOARDS.md,
docs/PRIVACY.md, docs/START_HERE_NEXT_SESSION.md, the completed Board 1-5
reports, and docs/reports/2026-08-29-pre-board-6-session-handoff.md.

Verify that the worktree is clean and that local main matches the public GitHub
repository. Run the 41 existing tests, offline demo, doctor, discovery scan,
ledger summary, routing decision inspection and privacy scan before
implementation.

Then implement Productization Board 6: the local settings interface. Build a
local control surface over the existing Provider, Model, Agent, role,
application-setting, discovery, provenance, ledger, budget and routing
contracts. Keep SQLite authoritative, preserve user-owned settings and make
routing explanations inspectable.

Do not implement Board 7 Codex App Server, A2A, MCP or remote Agent
interoperability. Do not add worktree automation, a new billing system or broad
real-model startup. The real Codex pilot remains paused unless the user
separately gives explicit authorization to send repository content or derived
details to an external model service.

Finish Board 6 with its own report, roadmap and handoff updates, the full
privacy gate from docs/PRIVACY.md, commit, push and remote-main verification.
Report the board outcome to the user before beginning Board 7.
```

## Repository orientation

- `model_council/orchestrator.py`: deterministic workflow
- `model_council/manager.py`: model-generated plan and synthesis
- `model_council/adapters/`: model-host integrations
- `model_council/store.py`: SQLite persistence
- `model_council/artifacts.py`: content-addressed files
- `model_council/discovery.py`: startup discovery and isolated probes
- `model_council/ledger.py`: usage, cost, budget and balance ledger
- `model_council/routing.py`: deterministic role selection and audit evidence
- `artifact_attributions`: internal contributor/reviewer/integrator audit table
- `agent_discovery`: persisted discovery and setup observations
- `usage_events`, `budget_policies`, `budget_alerts`: ledger tables
- `routing_decisions`: durable selected and rejected routing evidence
- `config.example.json`: stable offline baseline
- `config.codex.example.json`: next pilot
- `docs/PRIVACY.md` and `scripts/privacy_scan.py`: public-repository privacy gate
- `protocol/`: communication schema drafts
- `tests/`: regression baseline
- `docs/reports/2026-08-29-pre-board-6-session-handoff.md`: frozen Board 6
  starting context and acceptance boundary

## First checks

```powershell
python --version
python -m unittest discover -s tests -v
python -m model_council demo "验证多模型协作闭环"
python -m model_council doctor --config config.codex.example.json
python -m model_council discovery scan --config config.example.json
python -m model_council ledger summary --config config.example.json
python -m model_council routing decisions --config config.example.json
python scripts/privacy_scan.py --history
```

Expected baseline: forty-one tests pass, doctor resolves `codex.cmd`, and the
demo produces a completed run with worker results, an independent review, a
final report and persisted routing decisions. Discovery scan must not run a
connectivity probe. Ledger and routing evidence must preserve unknown values
and measurement sources. The privacy scan must report no findings.
