# Board 14.2 Report: Offline Codex App Server Execution Verification

Date: 2026-08-31

Status: accepted offline verification; Board 14 remains in progress

## Delivered

`CodexAppServerAdapter` now supports the optional
`strict_no_approvals: true` setting. When enabled, a server-side interactive
approval request is recorded as a bounded local rejected approval, answered
with a decline, treated as a terminal protocol failure, and prevented from
yielding a Manager answer or continuing the turn.

The setting is type-validated and defaults to false, preserving existing
generic interoperability behavior. The public Board 14 Codex candidate enables
it while retaining `invoke_enabled: false`.

## Local fixture result

The test uses only `tests/fixtures/fake_codex_app_server.py`, a
repository-controlled local JSON-lines subprocess. It does not run
`codex.cmd`, bind a network listener, send HTTP, access PackyAPI, or invoke a
model.

The fixture verifies initialize, thread/start, turn/start and a server-side
command-approval request. With the strict policy enabled, the Adapter declines
the request, marks the local session failed and records no agent-message delta.
It makes no retry.

## Verification

Focused checks passed:

- standard local fake App Server persistent-session protocol behavior;
- strict rejection and terminal stop behavior;
- external invocation remains blocked while `invoke_enabled` is false;
- public Board 14 candidate remains disabled, synthetic-only and strict.

Final local verification passed:

```text
111 offline tests passed
Python compilation passed for model_council, tests and scripts
12 tracked JSON files parsed
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

The first complete suite encountered one transient Windows loopback-server
`WinError 10053` in an existing redirect test. Its isolated rerun passed, and
the subsequent complete 111-test run passed. The failure did not involve the
Codex App Server fixture or a Board 14.2 code path.

## Privacy and future authorization

Only generic synthetic text appears in tracked tests and documents. Temporary
SQLite state and any real prompt, command, response, identity or approval
record remain ignored local runtime data.

The earlier Board 14.1 manifest is approved but unarmed. It did not authorize
App Server startup or a model call, and it does not bind this new strict policy.
Do not arm it for a real pilot. A future exact candidate must include
`strict_no_approvals: true`, be freshly prepared and displayed, then receive
separate approval for arming and for one exact startup-plus-turn request.

No GitHub push, tag, Release, real Codex process, Provider call or model call
occurred.
