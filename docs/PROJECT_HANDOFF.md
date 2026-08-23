# Project Handoff

Last updated: 2026-08-23

## Why this project exists

The original idea is to let models with different strengths collaborate on a
real project. Agent applications are treated as model hosts and execution
interfaces. A designated manager model assigns bounded work, professional models
exchange selected results and files, an independent reviewer challenges the
work, and the manager integrates the final answer.

The core design question is not merely how to run several processes at once.
The important problem is how to provide:

- a common communication contract;
- persistent project memory;
- explicit capabilities and boundaries;
- safe file transfer;
- deterministic scheduling and permissions;
- independent review and evidence-based acceptance.

## Strategic decision

Build a small, dependency-free local control plane first. Validate the complete
collaboration loop with mock models, then replace one role at a time with a real
model host.

Longer term, the project may integrate:

- A2A for remote agent interoperability;
- MCP for tool access;
- Git worktrees for code isolation;
- Codex App Server for persistent Codex sessions;
- a web or Electron control console.

Those systems are integration targets, not requirements for the MVP.

## What is implemented

The repository currently contains:

- a manager that requests and validates a JSON task graph;
- deterministic dependency and parallel-wave scheduling;
- role, capability and boundary declarations;
- SQLite runs, tasks, messages and Artifact metadata;
- SHA-256 content-addressed text Artifacts;
- an independent review stage;
- final manager synthesis;
- mock, generic CLI and OpenAI-compatible HTTP Adapters;
- Responses-style and Chat Completions-style HTTP payloads;
- JSON Schema drafts for agent cards and task messages;
- a CLI for demos, custom runs, agent listing and run inspection;
- four automated tests.

## Verified state

On 2026-08-23:

- Python version: 3.14.4
- Node.js version: 24.16.0
- Git version: 2.55.0
- all four unit/integration tests passed;
- one full offline run completed;
- the run produced four completed tasks;
- ten structured messages were stored;
- five Artifacts were stored;
- all JSON configuration and protocol files parsed successfully.

The final Artifact was confirmed to contain valid UTF-8 Chinese text. Mojibake
seen in one PowerShell capture was a terminal rendering issue rather than file
corruption.

## Current real-agent situation

The `codex` command is discoverable on the original Windows machine. Launching
the packaged executable from inside the managed Codex Desktop task environment
returned Windows "Access denied". This same class of restriction had appeared
in earlier local Codex configuration work.

The repository therefore includes `config.codex.example.json`, but no paid or
remote model invocation has been claimed as verified.

The Codex pilot uses:

```text
codex exec --ephemeral --skip-git-repo-check --sandbox read-only -
```

The prompt is passed on stdin. The manager, implementer and reviewer remain
mocks so that only one integration variable changes.

## Provider caution

The original machine uses a PackyAPI-backed Codex catalog. Earlier local testing
showed that model-catalog presence and JSON validity did not guarantee that a
model could be called directly through a nominally compatible HTTP endpoint.
Some models required the standard Codex client and direct requests returned
provider-side HTTP 403 errors.

Consequences:

- do not assume API compatibility from `/v1/models`;
- test each model through its intended host;
- never copy credentials into repository configuration;
- keep API configuration in environment variables;
- distinguish declared configuration from observed execution.

This information may become stale and should be reverified before provider work.

## Known limitations

- The manager performs one planning pass and one final synthesis pass.
- There is no dynamic re-planning after a worker failure.
- Worker-to-worker questions currently route only through stored results and the
  final manager context; there is no interactive question loop yet.
- There is no token, time or monetary budget ledger.
- CLI stdout is treated as the model result; streaming is not implemented.
- There is no App Server, A2A or MCP transport.
- There is no Git worktree creation, diff review or merge workflow.
- There is no web UI or human approval screen.
- The current HTTP Adapter is intentionally small and does not cover every
  provider-specific response variant.

## Next recommended milestone

Milestone 1 is complete when one real Codex role successfully participates in a
full run from an ordinary PowerShell session.

Acceptance criteria:

1. `config.codex.example.json` is copied to a local untracked config.
2. Only the architect role uses Codex.
3. Codex runs in read-only mode.
4. The process exits successfully and produces non-empty stdout.
5. The stdout becomes an Artifact and a `task_result` message.
6. The mock reviewer receives the Codex Artifact.
7. The mock manager creates the final synthesis.
8. The database contains no failed or blocked tasks.
9. No credential, user path or runtime database is committed.

After that, add a persistent `CodexAppServerAdapter` with JSONL request IDs,
thread identity, streaming events and cancellation.

## How to resume safely

```powershell
python -m unittest discover -s tests -v
python -m model_council demo "验证当前基线"
python -m model_council agents --config config.example.json
```

Read the architecture invariants before changing Adapter or orchestration
boundaries. Preserve the mock-only baseline even after real models are added.
