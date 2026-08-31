# Board 14.3 Plan: Controlled Codex Manager Executor

Date: 2026-08-31

Status: frozen before implementation

## Goal

Add the missing Board 14 execution control plane without performing a real
invocation. The implementation must make a future Codex App Server startup and
one `turn/start` request impossible until a separate, durable, SHA-256-bound
start approval is approved and consumed exactly once.

## Scope

- Board 14.1 `real_codex` experiments only;
- current experiment must already be `armed`;
- a separate local start-approval record binds the complete experiment scope
  digest, command, cwd, model, prompt hash, limits and action name;
- an approval decision requires the displayed start-scope SHA-256;
- execution consumes that approval before starting a process;
- exact prompt is sent over stdio without repository, Artifact or task context;
- read-only sandbox, `approval_policy: "never"` and
  `strict_no_approvals: true` are mandatory;
- one process and one turn, no retry and no parallelism;
- bounded response bytes and provider-reported token limits;
- response text stays in memory and is persisted only as a hash and byte count.

## Offline fixture

All tests use the repository-controlled `fake_codex_app_server.py` with
synthetic text. The fixture is the only process started by tests. No test
starts `codex.cmd`, opens a network listener, accesses credentials, calls
PackyAPI or invokes a model.

## Stop rules

The executor must fail and retain only bounded local evidence when:

- the experiment, team or Agent/Model identity has drifted;
- the start approval is absent, stale, rejected or already consumed;
- the Manager is not a strict, read-only Codex App Server candidate;
- the process requests command or file approval;
- the response exceeds its byte, token or timeout limit;
- the protocol is malformed or the turn does not complete successfully.

## Deferred authorization

This board authorizes no real startup or model call. After offline acceptance,
a new local runtime candidate must be prepared with the strict policy and
reviewed. The user must then separately approve:

1. arming after readiness revalidation; and
2. one displayed start-approval SHA-256 for startup and exactly one turn.

No previous Board 14.1 approval can be reused.

The local CLI exposes the staged path:

```powershell
python -m model_council experiment request-start <EXPERIMENT_ID> --config <LOCAL_CONFIG>
python -m model_council experiment show-start <START_APPROVAL_ID> --config <LOCAL_CONFIG>
python -m model_council experiment approve-start <START_APPROVAL_ID> `
  --scope-sha256 <START_SCOPE_SHA256> --config <LOCAL_CONFIG>
```

`experiment execute-start` is intentionally omitted from normal operating
instructions because it starts the configured process and is reserved for a
later separately authorized one-turn pilot.
