# Start Here in the Next Session

Use this document when continuing in a new Codex conversation.

## Suggested opening prompt

```text
Continue development of the Model Council repository. First read AGENTS.md,
README.md, docs/ARCHITECTURE.md, docs/PROJECT_HANDOFF.md and docs/ROADMAP.md.
Run the existing tests and offline demo before changing code.

The current next milestone is a narrow real-Codex pilot: keep the manager,
implementer and reviewer on mock adapters, and replace only the architect with
the read-only CLI adapter from config.codex.example.json. Do not connect every
model at once. Verify actual execution, stdout-to-Artifact transfer, database
messages and final synthesis. If the packaged codex.exe cannot launch inside a
managed desktop task, explain the boundary and prepare an ordinary PowerShell
test without weakening sandbox permissions.
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
```

Expected baseline: four tests pass and the demo produces a completed run with
worker results, an independent review and a final report.
