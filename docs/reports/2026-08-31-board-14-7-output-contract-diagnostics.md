# Board 14.7 Report: Privacy-Safe Manager Output Contract Diagnostics

Date: 2026-08-31

Status: accepted offline verification; Board 14 remains in progress

## Trigger

The third separately authorized Board 14 one-turn synthetic Manager attempt
consumed its start approval and failed closed because its response did not meet
the frozen two-task JSON plan contract. The raw output remained private and was
not retained.

## Delivered

`manager_two_worker_plan_v1` is now validated as an untrusted, deterministic
local contract:

- output must be a JSON object with a `tasks` list;
- the list must contain exactly two task objects;
- each task must have a unique non-empty `key`;
- the two task `agent` values must match exactly the two distinct mock Worker
  identities bound in the experiment scope;
- tasks must be independent, with no dependencies;
- task fields attempting to carry permissions, tools, workspace, Git, files,
  Artifacts, or commands are rejected.

When this contract fails, the executor records one failed local
`codex_app_server_output_diagnostic`. It retains only:

- deterministic failure class;
- expected schema label;
- output SHA-256;
- UTF-8 byte count; and
- `output_text_stored: false`.

It retains no raw JSONL, response text, prompt, task content, stderr, stdout,
transcript, credential, path, file, or Artifact. The hard response-byte and
usage limits, zero-retry behavior, strict approval rejection, single-use
approval consumption and source-integrity binding remain unchanged.

## Protocol decision

This board does not add a speculative structured-output field to Codex App
Server `turn/start`. Official OpenAI documentation describes JSON Schema
Structured Outputs for the Responses API, but the local review did not
establish the corresponding App Server request field and semantics. The
approved transport therefore remains unchanged.

## Offline verification

Repository fake App Server fixtures prove:

- valid two-Worker output still succeeds;
- invalid JSON, missing tasks, wrong task count, Worker mismatch, duplicate
  key, dependency and unsafe control field each fail with a distinct
  diagnostic class;
- diagnostics contain output hash/count rather than raw output or the
  synthetic prompt;
- existing usage, strict-approval, source-integrity and one-time-consumption
  tests continue to pass.

No test runs `codex.cmd`, contacts PackyAPI, accesses credentials, sends HTTP,
or invokes a model.

## Verification

```text
Focused Board 14 experiments: 21 tests passed
Full offline suite: 122 tests passed
Python compilation passed for model_council, tests and scripts
Tracked JSON validation passed
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

## Real-pilot boundary

All three prior Board 14 real synthetic attempts and their consumed approvals
remain terminal and must not be retried. Board 14.7 grants no execution
authority. A later real attempt requires a newly prepared candidate after this
commit and the complete experiment/start-approval/execute authorization
sequence again.
