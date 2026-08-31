# Board 14.7 Plan: Privacy-Safe Manager Output Contract Diagnostics

Date: 2026-08-31

Status: frozen before implementation

## Trigger

The third separately authorized Board 14 Manager attempt consumed its fresh
start approval and failed closed because the returned Manager text did not
satisfy the frozen two-task JSON plan contract. The response body was correctly
not retained, but the pre-14.7 runtime state recorded only the generic failure
message and could not classify the output-contract defect.

That experiment and its consumed approval remain terminal. This board does not
retry, reconstruct, display, or persist the previous response body.

## Goal

Make the `manager_two_worker_plan_v1` output contract explicit and record a
bounded, privacy-safe local diagnostic for a rejected Manager response.

## Scope

- validate JSON object output with a `tasks` list of exactly two entries;
- require every task to be an object with a unique non-empty `key`;
- require the two task `agent` values to match exactly the two distinct mock
  Worker Agent IDs frozen in the experiment scope;
- reject task dependencies so the two initial tasks remain independent;
- reject task fields that attempt to carry permissions, tools, workspace,
  Git, file, Artifact, or command control;
- classify failures such as invalid JSON, missing tasks, wrong task count,
  invalid task object/key/agent, Worker mismatch, dependency, or unsafe task
  field;
- retain only failure class, expected schema label, output SHA-256 and UTF-8
  byte count in ignored runtime SQLite;
- retain no raw JSONL, output text, prompt, task content, stderr, stdout,
  transcript, credential, path, file, or Artifact;
- preserve the existing response-byte bound, supported usage checks,
  fail-closed behavior, one process, one turn, zero retries, strict approval
  rejection, and executor-integrity binding;
- use repository fake App Server fixtures only.

## Excluded

- a real App Server startup, Provider request, model call, retry, replay, or
  new live candidate;
- unverified App Server structured-output request parameters;
- relaxation of the two-task, Worker-identity, token, cost, permission, or
  zero-retry limits;
- raw failed output storage, output repair, task execution, files, Artifacts,
  workspace writes, Git actions, push, tag, Release, or deployment.

## Acceptance criteria

1. Valid fixture output for the two frozen mock Workers still passes.
2. Invalid JSON and representative plan-structure violations record one
   `codex_app_server_output_diagnostic` with a deterministic failure class.
3. Diagnostics contain only schema label, SHA-256, byte count, class and the
   `output_text_stored: false` assertion.
4. Diagnostics contain no raw output field or synthetic prompt text.
5. Focused and full offline tests, compilation, tracked JSON validation,
   current-tree privacy scan, reachable-history privacy scan and
   `git diff --check` pass.
6. One local-only commit is created without push, tag, Release or real call.

## Protocol decision

Official OpenAI documentation describes JSON Schema Structured Outputs for the
Responses API, but this board does not assume that Codex App Server
`turn/start` accepts the same parameter. The App Server request remains
unchanged until an official App Server protocol source establishes an exact
supported field and semantics.

## Next real-pilot boundary

This board grants no execution authority. Any later real attempt must use a
fresh candidate prepared after the Board 14.7 commit and repeat every approval
gate.
