# Start Here in the Next Session

Use this document when continuing in a new Codex conversation.

## Suggested opening prompt

```text
Continue development of the Model Council repository. First read AGENTS.md,
README.md, docs/ARCHITECTURE.md, docs/PROJECT_HANDOFF.md and docs/ROADMAP.md.
Run the existing tests and offline demo before changing code.

Productization Boards 1 through 3 are complete. Read
`docs/reports/2026-08-29-board-1-settings-registry.md` and
`docs/reports/2026-08-29-board-2-artifact-provenance.md` and
`docs/reports/2026-08-29-board-3-startup-discovery.md`, then begin Board 4:
usage, cost and balance ledger. Keep the registry, Artifact provenance and
discovery contracts intact. Distinguish actual, provider-reported, estimated
and unavailable values. Do not implement routing or a Web UI in Board 4.

The real-Codex pilot remains paused. Before that run, obtain explicit user
authorization to send private repository content or derived details to the
external Codex model service.
```

## Repository orientation

- `model_council/orchestrator.py`: deterministic workflow
- `model_council/manager.py`: model-generated plan and synthesis
- `model_council/adapters/`: model-host integrations
- `model_council/store.py`: SQLite persistence
- `model_council/artifacts.py`: content-addressed files
- `model_council/discovery.py`: startup discovery and isolated probes
- `artifact_attributions`: internal contributor/reviewer/integrator audit table
- `agent_discovery`: persisted discovery and setup observations
- `config.example.json`: stable offline baseline
- `config.codex.example.json`: next pilot
- `protocol/`: communication schema drafts
- `tests/`: regression baseline

## First checks

```powershell
python --version
python -m unittest discover -s tests -v
python -m model_council demo "验证多模型协作闭环"
python -m model_council doctor --config config.codex.example.json
python -m model_council discovery scan --config config.example.json
```

Expected baseline: twenty tests pass, doctor resolves `codex.cmd`, and the demo produces a completed run with
worker results, an independent review and a final report. Discovery scan must
not run a connectivity probe.
