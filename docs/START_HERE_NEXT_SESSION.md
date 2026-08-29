# Start Here in the Next Session

Use this document when continuing in a new Codex conversation.

## Suggested opening prompt

```text
Continue development of the Model Council repository. First read AGENTS.md,
README.md, docs/ARCHITECTURE.md, docs/PROJECT_HANDOFF.md and docs/ROADMAP.md.
Run the existing tests and offline demo before changing code.

Productization Board 1 is complete. Read
`docs/reports/2026-08-29-board-1-settings-registry.md` and continue with Board 2:
Artifact provenance. Record producing Provider, Model and Agent, contributors,
reviewer and final integrator. Preserve provenance internally while supporting
compact, detailed and hidden presentation modes.

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
```

Expected baseline: ten tests pass, doctor resolves `codex.cmd`, and the demo produces a completed run with
worker results, an independent review and a final report.
