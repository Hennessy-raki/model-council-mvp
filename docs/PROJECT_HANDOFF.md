# Project Handoff

Last updated: 2026-08-30

The authoritative Board 6 completion report is:

```text
docs/reports/2026-08-30-board-6-local-settings-interface.md
```

It records the local-interface scope, verification, privacy boundaries and
next-board boundary. The pre-Board-6 starting context remains in
`docs/reports/2026-08-29-pre-board-6-session-handoff.md`.

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
- a no-invocation Adapter doctor command;
- Codex JSONL parsing with final-message extraction and diagnostic metadata;
- a persistent Provider, Model, Agent, role and application-settings registry;
- protected user overrides and nested sensitive-value redaction;
- Artifact producer identity and contributor/reviewer/final-integrator audit
  attribution;
- startup discovery with separated executable, authentication, permission and
  connectivity status;
- Adapter capability-based model discovery and opt-in isolated probes;
- manual GUI-only Agent registration;
- normalized per-call usage and cost records with explicit measurement sources;
- project, run and role totals;
- warning and hard budget policies plus supported Provider balance snapshots;
- deterministic manual, automatic and hybrid role routing;
- capability, availability, cost, latency, hard-budget and identity-separation
  constraints;
- immutable routing decisions with selected evidence, rejected candidates and
  reason codes;
- a loopback-only local settings interface over the persisted SQLite state;
- user-owned Provider, Model, Agent, role, application-setting and budget
  editing with sensitive values redacted before storage;
- local views for discovery observations, Artifact provenance, ledger, budget,
  balance-snapshot and routing-decision evidence;
- a local repository privacy scanner and required public-push safety gate;
- forty-five automated tests.

## Verified state

On 2026-08-29:

- Python version: 3.14.4
- Node.js version: 24.16.0
- Git version: 2.55.0
- Codex CLI version: 0.150.1
- all ten unit/integration tests passed before productization Board 2;
- all thirteen unit/integration tests passed after the Artifact provenance board;
- all twenty unit/integration tests passed after the startup discovery board;
- all twenty-nine unit/integration tests passed after the usage and cost ledger;
- all forty-one unit/integration tests passed after the routing policy and
  privacy gate;
- all forty-five unit/integration tests passed after the local settings
  interface;
- one full offline run completed;
- the run produced four completed tasks;
- ten structured messages were stored;
- five Artifacts were stored;
- all JSON configuration and protocol files parsed successfully.

The final Artifact was confirmed to contain valid UTF-8 Chinese text. Mojibake
seen in one PowerShell capture was a terminal rendering issue rather than file
corruption.

## Current real-agent situation

Two Codex installations were observed on the original Windows machine. The
WindowsApps-packaged executable previously returned "Access denied" from a
managed task environment. A separate npm-installed `codex.cmd` is available on
the local `PATH`; version and Python `subprocess` launch checks both succeeded.

The repository therefore includes `config.codex.example.json`, but no paid or
remote model invocation has been claimed as verified.

The Codex pilot now uses:

```text
codex.cmd exec --ephemeral --skip-git-repo-check --sandbox read-only
  --color never --json -
```

The prompt is passed on stdin. JSONL events are parsed deterministically, and
only the final completed `agent_message` becomes the task Artifact. Thread ID,
event counts, usage, duration, exit code and stderr tail are stored as message
metadata. The manager, implementer and reviewer remain mocks so that only one
integration variable changes.

`python -m model_council doctor --config config.codex.example.json` currently
passes and resolves `codex.cmd` without invoking a model.

The real repository-analysis run has not been executed yet. The managed safety
review correctly required explicit user authorization before sending private
repository contents or derived details to an external model service.

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
- There is no automatic price catalog refresh or time-based budget policy.
- Codex JSONL is collected after process completion; live event streaming is not
  implemented.
- There is no App Server, A2A or MCP transport.
- There is no Git worktree creation, diff review or merge workflow.
- There is no web UI or human approval screen.
- The current HTTP Adapter is intentionally small and does not cover every
  provider-specific response variant.

## Separate real-agent milestone

The next productization milestone is Board 6. The real-agent milestone below is
separate and remains paused pending explicit user authorization.

Milestone 1 is complete when one real Codex role successfully participates in a
full run from an ordinary PowerShell session.

Acceptance criteria:

1. `config.codex.example.json` is copied to a local untracked config.
2. Only the architect role uses Codex.
3. Codex runs in read-only mode.
4. The process exits successfully and produces non-empty stdout.
5. JSONL contains a completed `agent_message`.
6. The final message becomes an Artifact and a `task_result` message containing
   diagnostic metadata.
7. The mock reviewer receives the Codex Artifact.
8. The mock manager creates the final synthesis.
9. The database contains no failed or blocked tasks.
10. No credential, user path or runtime database is committed.

After that, add a persistent `CodexAppServerAdapter` with JSONL request IDs,
thread identity, streaming events and cancellation.

## Productization board status

Board 1, the settings and registry foundation, is complete. Its report is:

```text
docs/reports/2026-08-29-board-1-settings-registry.md
```

Board 2, Artifact provenance, is complete. Each new Artifact now records an
immutable producing Agent/Provider/Model snapshot, plus contributor, reviewer
and final-integrator attribution. The `artifact_provenance_display` setting
supports `compact`, `detailed` and `hidden`; hidden suppresses only the CLI
projection and retains the internal audit trail. Existing SQLite databases are
upgraded safely through additive migration. The board report is:

```text
docs/reports/2026-08-29-board-2-artifact-provenance.md
```

Board 3, startup discovery and setup, is complete. Discovery scans configured
Agents and known local Codex, Claude, Gemini and OpenCode commands without
invoking a model. It stores executable, authentication, permission,
connectivity and model observations separately. Model discovery is delegated
only to Adapters that declare the capability. Connectivity probes are explicit
and CLI probes use a fixed prompt from an empty temporary directory. GUI-only
hosts can be registered as user-owned Agent profiles.

```text
docs/reports/2026-08-29-board-3-startup-discovery.md
```

Board 4, usage, cost and balance ledger, is complete. Every Adapter invocation
creates a normalized record with separate token, duration and cost sources.
Summaries aggregate by project, run and role. Warning policies create audit
alerts; hard limits block later calls and conservatively block when prior values
are unavailable. Provider balance is queried only by an Adapter that explicitly
declares a supported balance API.

```text
docs/reports/2026-08-29-board-4-usage-cost-ledger.md
```

Board 5, routing policy, is complete. Every manager, worker and reviewer role is
resolved through deterministic control-plane policy before Adapter invocation.
Manual assignments fail without silent replacement. Automatic and hybrid
selection consume persisted capability, availability, cost, latency, budget and
separation evidence. Every outcome stores an immutable explanation.

```text
docs/reports/2026-08-29-board-5-routing-policy.md
```

The privacy-cleaned Board 5 implementation commit is
`f386ecea1dda471921e331dd0cb0f354f926ba3a`. Public `main` was force-updated
after replacing an older README home-directory example throughout reachable
history. The current tree and reachable history pass the privacy scanner.
GitHub may retain unreferenced objects until garbage collection; a private
Support purge remains the strongest follow-up for immediate physical removal.

Board 6, the local settings interface, is complete. It exposes the stable local
registry and routing contracts through a loopback-only, dependency-free Web
server. SQLite remains authoritative; refreshes only read persisted records and
save operations create user-owned records. It does not invoke models, discovery
probes, Provider balance APIs or external services.

Board 7 remains unstarted. Codex App Server, A2A, MCP and remote Agent
interoperability require a separate board authorization. The real Codex pilot
also remains paused until the user explicitly authorizes sending private
repository context to the external service.

The completed Board 6 scope and verification evidence are recorded in:

```text
docs/reports/2026-08-30-board-6-local-settings-interface.md
```

## How to resume safely

```powershell
python -m unittest discover -s tests -v
python -m model_council demo "验证当前基线"
python scripts/privacy_scan.py
python -m model_council agents --config config.example.json
python -m model_council web --config config.example.json
```

Read the architecture invariants before changing Adapter or orchestration
boundaries. Preserve the mock-only baseline even after real models are added.
The Web command opens only a loopback server and must not be extended into
Board 7 remote interoperability without new authorization.
