# Start Here in the Next Session

Use this document when continuing in a new Codex conversation.

## Suggested opening prompt

```text
Continue development of the Model Council repository. First read AGENTS.md,
README.md, docs/ARCHITECTURE.md, docs/PROJECT_HANDOFF.md and docs/ROADMAP.md.
Run the existing tests and offline demo before changing code.

The current milestone is a narrow real-Codex pilot. Local integration work is
already complete: the npm Codex CLI launches through Python, doctor passes,
Codex JSONL parsing has regression tests, and diagnostic metadata is persisted.
Keep the manager, implementer and reviewer on mocks. Before the actual run,
obtain explicit user authorization to send private repository content or derived
details to the external Codex model service. Then verify execution,
JSONL-to-Artifact transfer, database messages and final synthesis.
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

Expected baseline: seven tests pass, doctor resolves `codex.cmd`, and the demo produces a completed run with
worker results, an independent review and a final report.
