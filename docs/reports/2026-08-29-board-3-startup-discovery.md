# Board 3 Report: Startup Discovery and Setup

Date: 2026-08-29

Status: accepted

Commit: `feat: add startup discovery and setup`

## Objective

Make local model hosts observable and configurable without treating command
presence as proof of authentication, permission or model connectivity.

GitHub Issue #3 was not present when this board started. Acceptance therefore
followed `docs/DEVELOPMENT_BOARDS.md`, `AGENTS.md`, the project handoff and the
completed Board 1 and Board 2 contracts.

## Delivered

### Persistent discovery observations

SQLite now includes `agent_discovery`. Each target stores independent:

- executable status;
- authentication status;
- permission status;
- connectivity status;
- resolved executable;
- configured or discovered models;
- Adapter discovery capabilities;
- sanitized diagnostic details and timestamps.

The schema is additive, so existing databases gain the table without rebuilding
or deleting registry, run or Artifact data.

### Configured Agent checks

Every configured Adapter exposes a discovery contract. A scan records only the
checks supported by that Adapter:

- CLI executable resolution;
- optional non-interactive CLI authentication commands or environment
  references;
- configured CLI sandbox and local workspace access;
- API credential-environment presence without claiming remote verification;
- explicit `unknown` or `not_applicable` states when evidence is unavailable.

The Codex example deliberately does not hard-code `codex login status`.
Custom-provider authentication may not use the standard OpenAI login flow, so a
generic login command could create a false failure.

### Known local command scan

The scanner checks command candidates for:

- Codex CLI;
- Claude Code CLI;
- Gemini CLI;
- OpenCode CLI.

Available commands create discovery-owned, unassigned Agent profiles. Missing
commands are still persisted as observations. Discovery-owned records can later
be replaced by explicit configuration, while user-owned records remain
protected.

### Adapter model discovery

Model enumeration is executed only when an Adapter declares
`model_discovery`. The generic CLI Adapter supports an optional command-array
contract and parses JSON or line-oriented model IDs. The OpenAI-compatible
Adapter uses the provider `/models` endpoint. Mock discovery remains offline.

Model discovery is explicit; startup scanning does not enumerate provider
models or run connectivity probes. An explicitly configured
`auth_check_command` remains responsible for its own non-interactive behavior.

### Opt-in project-neutral connectivity

`discovery probe` is an explicit user action. CLI probes:

- use a fixed minimal prompt;
- run from a new empty temporary directory;
- do not include the project goal, Agent description, conversation context or
  Artifact references;
- preserve only bounded diagnostic metadata, not the model response body.

No real Codex model was invoked while accepting this board. Automated coverage
uses a local fixture, and the manual smoke probe used only the offline mock
Adapter.

### Manual GUI Agent registration

GUI-only model hosts can be registered through the CLI with optional Provider,
Model, capability and boundary references. These Agent profiles and discovery
records are marked `user`, so later config synchronization or command scanning
cannot overwrite them.

### CLI control surface

```powershell
python -m model_council discovery scan --config config.example.json
python -m model_council discovery show --config config.example.json
python -m model_council discovery models manager --config config.example.json
python -m model_council discovery probe manager --config config.example.json
python -m model_council discovery register-gui desktop-reviewer `
  --name "Desktop Reviewer" --config config.example.json
```

`auto_discovery_on_start` now activates local scanning when set to true. It
never runs a connectivity probe.

## Verification

Automated verification:

```text
20 tests passed
```

New coverage verifies:

- status separation for executable, authentication, permission and
  connectivity;
- available and missing known-command observations;
- no connectivity probe during scan or automatic startup discovery;
- Adapter capability-based model enumeration and de-duplication;
- OpenAI-compatible `/models` discovery without a real network call;
- isolated, fixed-prompt CLI connectivity checks;
- user-owned GUI registration;
- CLI scan output;
- additive creation of the discovery table on an existing SQLite database.

Local smoke verification observed:

- an npm-installed `codex.cmd` resolved successfully on the test machine;
- executable status `available`;
- authentication status `unknown`, because no reliable provider-neutral check
  is configured;
- permission status `read_only`;
- connectivity status `not_checked`;
- mock model discovery and mock connectivity probe success.

These observations are machine-specific and must be refreshed rather than
treated as permanent capability claims.

## Scope boundaries

This board does not:

- select Agents for project roles;
- calculate usage, cost or provider balance;
- build a Web interface;
- invoke a real model automatically;
- send repository content during setup;
- implement Codex App Server, A2A or MCP.

The real Codex pilot remains paused until the user explicitly authorizes sending
private repository content or derived details to an external model service.

## Next board

Board 4 will add the usage, cost and balance ledger. It must preserve the
difference between actual, provider-reported, estimated and unavailable values,
and must not implement routing policy ahead of Board 5.
