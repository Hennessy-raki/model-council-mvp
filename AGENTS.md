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
5. `docs/DEVELOPMENT_BOARDS.md`
6. `docs/PRIVACY.md`

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
- Treat public-repository privacy as a release gate. Never commit real local
  usernames, home paths, personal email addresses, credentials, runtime state
  or private downstream project content.

## Development workflow

Run before and after changes:

```powershell
python -m unittest discover -s tests -v
python scripts/privacy_scan.py --history
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

Productization Boards 1 through 7 are complete. Board 8 has a complete control
implementation and one functionally successful live synthetic run, but its
privacy acceptance remains pending after discovering that the original
manifest did not cover App Server `cwd`. Read the Board 8 plan/report before
changing persistent sessions or outbound-context approval.

Interoperability state remains local and authoritative in SQLite. Non-loopback
HTTP endpoints require HTTPS. Credentials are environment-variable references
only. Every real App Server, A2A or MCP transport additionally requires
`invoke_enabled: true`, and MCP tool execution requires a persisted single-use
human approval.

One live synthetic Codex App Server run completed with a read-only architect
and mock manager/reviewer. It sent no files, Artifacts or repository content,
but its local App Server received an absolute `cwd` that may have been included
in upstream environment context. The corrected gate binds prompt plus `cwd`,
model, sandbox and approval policy, and blocks personal home paths; this fix is
offline-verified only. No live A2A or MCP endpoint has been verified.

## Codex pilot boundary

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
7. The persistent Codex App Server Adapter is implemented and verified against
   a local fake server; a live pilot still requires separate authorization.

Do not connect every configured model in one change.
