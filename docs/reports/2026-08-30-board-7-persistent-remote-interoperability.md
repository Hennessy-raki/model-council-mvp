# Board 7 Report: Persistent and Remote Interoperability

Date: 2026-08-30

Status: accepted offline implementation; live endpoint pilots not executed

## Objective

Add persistent Codex App Server sessions, a second external Agent-family
contract, A2A transport, MCP tool brokering, and remote identity/authentication
without weakening the local-first control plane.

The implementation must preserve deterministic routing, SQLite authority,
environment-only credentials, argument-array subprocess execution and explicit
human approval for tool side effects.

## Protocol baselines

- Codex App Server current JSON-line protocol with initialization, Threads,
  Turns, notifications and server approval requests.
- A2A v1.0 JSON-RPC binding with Agent Cards, Messages, Tasks and Artifacts.
- MCP 2025-11-25 with stdio and Streamable HTTP transports.

These baselines were checked against their official public documentation on
2026-08-30. The repository does not copy credentials or private Support details
into protocol configuration.

## Delivered

### Durable interoperability control plane

Safe additive SQLite tables persist:

- configured interoperability endpoints and remote identities;
- observed Agent Cards and initialization capabilities;
- local-to-remote session identity, including Codex Thread and A2A context IDs;
- bounded inbound and outbound protocol events;
- pending, approved, rejected and consumed human approvals.

All records remain under ignored runtime state. JSON configuration is seed
input, not a remote source of truth.

### Codex App Server Adapter

`CodexAppServerAdapter`:

- launches a configured command array with `shell=False`;
- performs `initialize` and `initialized`;
- starts a Thread once and resumes its stored Thread ID on later calls;
- starts one Turn and collects Agent-message deltas or completed messages;
- records protocol events, Turn IDs, usage and stderr diagnostics;
- allows only `read-only` or `workspace-write` sandbox declarations;
- records and declines command/file-change approval requests;
- requires `invoke_enabled: true` before process startup.

The process is local, but a real Codex host may use an external model. No real
Codex App Server was invoked during this board.

### A2A Adapter

`A2AAdapter` is the second external Agent-family integration contract. It:

- requires HTTPS for non-loopback endpoints;
- supports an environment-variable bearer credential reference;
- fetches and validates the Agent Card;
- sends a v1.0 JSON-RPC `message/send`;
- polls a returned Task with `tasks/get` until a terminal state;
- extracts text from Messages and Artifacts;
- persists Agent Card, context, Task and protocol evidence;
- requires `invoke_enabled: true`.

No live third-party Agent endpoint was called.

### MCP tool broker

`MCPToolBroker` supports:

- stdio JSON-RPC using command arrays and `shell=False`;
- Streamable HTTP JSON request/response operation;
- protocol initialization and persisted server capability observations;
- explicit `tools/list`;
- a three-step tool flow: request, human decision and single-use execution.

An approved request is atomically marked consumed before transport execution.
It cannot be replayed after success or failure. The local settings interface and
CLI operate on the same approval record.

### CLI and local interface

The `interop` command exposes endpoints, sessions, events and approvals:

```powershell
python -m model_council interop show --config config.interop.example.json
python -m model_council interop sessions --config config.interop.example.json
python -m model_council interop approvals --config config.interop.example.json
```

MCP tool calls require `request-tool`, `approve` and `call-tool`. The Board 6
loopback interface now shows remote identities, observed capabilities, sessions,
events and approve/reject controls protected by its local write token and
same-origin checks.

`config.interop.example.json` keeps every transport disabled for invocation by
default and uses only generic endpoints and environment-variable references.

## Verification

```text
51 tests passed
```

Board 7 coverage uses only local fakes:

- Codex initialization, Thread persistence/resume, Turn streaming and rejected
  command approval;
- A2A Agent Card retrieval, Message submission, Task polling and durable
  context identity;
- MCP tool discovery, pending approval, decision, single-use consumption and
  replay rejection;
- Streamable HTTP initialization, session headers and initialized notification;
- disabled invocation gates and plaintext-credential rejection;
- HTTPS, redirect and inline-command credential rejection;
- oversized protocol-event hashing and truncation;
- loopback Web approval decisions;
- regression coverage for Boards 1 through 6.

No real Codex model, A2A Agent, MCP server, paid Provider, balance endpoint or
external model service was called.

## Privacy and security boundaries

- Runtime interoperability databases and event payloads remain ignored.
- Non-loopback remote endpoints require HTTPS.
- Endpoint URLs cannot contain embedded credentials.
- Bearer credentials are loaded only from named environment variables.
- Configuration keys that contain plaintext authorization or secret material
  are rejected.
- Real transport startup requires `invoke_enabled: true`.
- MCP tool execution additionally requires a persisted single-use approval.
- App Server requests cannot self-authorize commands or file changes.
- The public-push full-history privacy scan remains mandatory.

## Known limitations

- Live endpoints are unverified.
- Codex App Server requests are process-per-Turn while Thread identity persists
  across processes.
- Interactive App Server approval requests are declined rather than paused for
  asynchronous user input.
- A2A push notifications, streaming, extended Agent Cards and webhook
  authentication are not implemented.
- MCP Streamable HTTP supports JSON request/response operation but not
  resumable SSE replay.
- Remote token rotation and certificate pinning remain deployment concerns.
- Git worktree creation, repair loops and merge approval remain out of scope.

## Next boundary

Before a live pilot, the user must authorize the exact endpoint and the context
that may leave the machine. Start with one read-only role, keep manager and
reviewer local, verify persisted evidence, and stop before enabling another
remote integration.

Define a new productization board before adding worktree automation, live repair
loops, deployment or broader remote execution.
