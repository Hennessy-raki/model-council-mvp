# Project Handoff

Last updated: 2026-08-30

The authoritative Board 7 completion report is:

```text
docs/reports/2026-08-30-board-7-persistent-remote-interoperability.md
```

It records the persistent-session, A2A, MCP, remote-identity, approval,
verification and privacy boundaries. The Board 6 report remains in
`docs/reports/2026-08-30-board-6-local-settings-interface.md`.

Board 8 completed one constrained live synthetic Codex App Server pilot. Its
frozen scope is:

```text
docs/reports/2026-08-30-board-8-controlled-live-pilot-plan.md
```

Its offline completion evidence is:

```text
docs/reports/2026-08-30-board-8-controlled-live-pilot.md
```

The successful pilot used the separate `config.pilot.example.json` pattern,
retained mock manager/reviewer roles, displayed the exact locally stored
synthetic prompt, obtained explicit user authorization, and consumed its
SHA-256 approval once. It sent no files, Artifacts, repository content,
credentials or private-derived details. Any future live attempt must repeat
that exact-context approval flow.

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

The local control plane now integrates:

- A2A for remote agent interoperability;
- MCP for tool access;
- Codex App Server for persistent Codex sessions;
- a local Web control console.

Git worktrees, repair loops and merge approval remain future integration
targets.

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
- persistent interoperability endpoint identities, sessions and events;
- Codex App Server Thread start/resume and Turn streaming;
- A2A v1.0 Agent Card, Message and Task support;
- MCP 2025-11-25 stdio and Streamable HTTP transports;
- environment-only remote authentication, explicit invocation gates and
  single-use MCP tool approvals;
- a local repository privacy scanner and required public-push safety gate;
- fifty-one automated tests.

## Verified state

Baseline history through 2026-08-30:

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
- all fifty-one unit/integration tests passed after persistent and remote
  interoperability;
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

The real repository-analysis run has not been executed. The verified live run
was synthetic only. Explicit authorization is still required before sending
private repository contents or derived details to an external model service.

Board 7 adds a separate `CodexAppServerAdapter` and
`config.interop.example.json`. The Adapter passed initialization, Thread
start/resume, Turn streaming and approval-rejection tests against a local fake
server. Board 8 subsequently verified one real synthetic read-only App Server
Turn under an exact one-time context approval.

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
- There is no Git worktree creation, diff review or merge workflow.
- The current HTTP Adapter is intentionally small and does not cover every
  provider-specific response variant.
- One live synthetic Codex App Server Turn is verified. A2A and MCP remain
  local-fake only, and repository context remains unverified.
- The first live Turn exposed a harmless but unnecessary featured-plugin
  catalog request that failed with HTTP 401. Public pilot examples now disable
  `plugins`, `remote_plugin` and `apps`; this mitigation is offline-validated
  but has not been rechecked with another live Turn.
- The first live Turn emitted token-usage notification data, but the then
  current sanitizer redacted the container key and the ledger used estimates.
  The Adapter now safely normalizes numeric usage fields and tests verify
  provider-reported ledger input; that correction is offline-validated.
- App Server interactive command and file-change requests are recorded and
  declined. A future repair-loop board must define richer user interaction.
- Streamable HTTP currently supports JSON request/response operation, not
  resumable SSE event replay.

## Separate real-agent milestone

Productization Boards 1 through 8 are complete. The synthetic live-agent
milestone below is verified; repository analysis remains separately gated.

Milestone 1 completed when one real Codex role successfully participated in a
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

The persistent `CodexAppServerAdapter` is now implemented and tested against a
local fake server. Live Codex verification, cancellation and richer interactive
approval UX remain separate acceptance work.

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

Board 7, persistent and remote interoperability, is complete as an offline
protocol implementation. It adds Codex App Server, A2A and MCP clients plus
durable identities, sessions, events and approvals. Real transport is disabled
unless the endpoint has `invoke_enabled: true`; non-loopback HTTP endpoints must
use HTTPS and credential values remain outside configuration.

The completed Board 7 scope and verification evidence are recorded in:

```text
docs/reports/2026-08-30-board-7-persistent-remote-interoperability.md
```

## How to resume safely

```powershell
python -m unittest discover -s tests -v
python -m model_council demo "验证当前基线"
python scripts/privacy_scan.py
python -m model_council agents --config config.example.json
python -m model_council web --config config.example.json
python -m model_council interop show --config config.interop.example.json
```

Read the architecture invariants before changing Adapter or orchestration
boundaries. Preserve the mock-only baseline even after real models are added.
Do not set `invoke_enabled: true` or send repository context to a live endpoint
without explicit user authorization for that exact pilot.
