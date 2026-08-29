# Agent Working Agreement

## Project goal

Model Council is a local-first control plane for collaboration among different
models and their host agents. One manager model proposes task allocation;
deterministic code enforces identity, dependencies, permissions, timeouts,
message persistence and Artifact transfer.

The product is not intended to make models open unrestricted direct connections
to one another. "Model communication" means that the orchestrator selectively
passes structured messages, summaries and Artifact references between persistent
agent identities.

## Read first

Before changing code, read:

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/PROJECT_HANDOFF.md`
4. `docs/ROADMAP.md`

## Architectural invariants

- Keep cognition and control separate.
- The manager model may propose actions but cannot grant itself permissions.
- All model hosts must be accessed through an Adapter.
- Do not broadcast full conversation history to every model.
- Store durable facts in SQLite and large text/file results as Artifacts.
- Pass Artifact references in messages instead of duplicating file contents.
- Never put API keys or bearer tokens in JSON configuration or source code.
- CLI commands must remain argument arrays executed with `shell=False`.
- A real coding agent starts read-only. Workspace writes require isolation and
  an explicit approval design.
- Add one real provider at a time and keep remaining roles on mocks until the
  pilot is verified.

## Development workflow

Run before and after changes:

```powershell
python -m unittest discover -s tests -v
```

Offline smoke test:

```powershell
python -m model_council demo "验证多模型协作闭环"
```

Do not commit:

- `runtime/`
- `__pycache__/`
- `.env`
- access tokens
- provider credentials
- user project worktrees

## Current priority

The next milestone is a narrow Codex pilot:

1. Keep the manager and reviewer on `mock`.
2. Replace only the architect with the existing read-only `cli` Adapter.
3. Run from an ordinary user PowerShell if the managed Codex Desktop process
   cannot launch the packaged `codex.exe`.
4. Obtain explicit authorization before sending private repository content or
   derived details to an external model service.
5. Use `--json` and `output_format: codex_jsonl`.
6. Capture thread ID, usage, events, duration, stderr, exit status and the final
   Artifact.
7. Only after this passes, design a persistent Codex App Server Adapter.

Do not connect every configured model in one change.
