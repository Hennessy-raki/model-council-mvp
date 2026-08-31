# Board 14.3 Report: Controlled Codex Manager Executor

Date: 2026-08-31

Status: accepted offline verification; Board 14 remains in progress

## Delivered

Board 14 now has a two-stage local authorization path for a future real Codex
Manager pilot:

1. an already-approved experiment is revalidated and armed; then
2. a separate start approval binds the complete experiment digest, Manager
   identity, prompt digest, transport, permissions and limits.

The start approval has its own SHA-256, must be approved exactly, and can be
consumed only once. Consumption revalidates the experiment again before any
process may start. It is recorded as `external_invocation: false`; process
startup is implemented only through the controlled executor.

The executor requires a disabled strict Codex App Server candidate:

- `invoke_enabled: false`;
- `strict_no_approvals: true`;
- read-only sandbox;
- `approval_policy: "never"`;
- synthetic prompt only, zero files and zero Artifacts;
- one process, one turn, zero retries and sequential execution.

It sends the exact stored prompt only after consuming the start approval. A
server-side approval request is declined and terminates the run. Response text
is not retained as evidence: only a SHA-256, byte count, bounded usage and
assertion metadata are stored.

## Offline fixture verification

All execution tests start only repository-controlled Python fixtures:

- a fixed-plan fake App Server proves exact prompt delivery, one process, one
  turn, response hashing and provider-reported usage handling;
- a fake App Server requesting command approval proves terminal rejection;
- a low token cap proves the executor fails without response evidence.

No test runs `codex.cmd`, contacts PackyAPI, accesses credentials, sends HTTP,
or invokes a model.

## Verification

```text
116 offline tests passed
Python compilation passed for model_council, tests and scripts
Current-tree privacy scan passed
git diff --check passed
```

The loopback-only evaluation redirect fixture now uses HTTP/1.1, resolving the
repeated Windows `WinError 10053` test-server race. The full suite passed after
that fixture-only correction.

## Next authorization boundary

The existing Board 14.1 local manifest remains approved but unarmed. It
predates the strict policy and the separate start approval scope; it must not
be armed or executed.

The next step is local-only preparation of a new strict candidate. It must be
displayed as `pending` with its exact experiment scope SHA-256. After the user
approves that experiment, a separate arming authorization is required. After
arming and fresh revalidation, a second displayed start-approval SHA-256 is
required before one App Server startup and exactly one `turn/start`.

No GitHub push, tag, Release, real Codex process, Provider call or model call
occurred.

The local CLI can request, display and approve the second scope. The command
which consumes it and starts a process is intentionally not part of normal
operating instructions; it remains reserved for the separately approved
one-turn pilot.
