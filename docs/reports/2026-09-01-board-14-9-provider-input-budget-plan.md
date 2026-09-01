# Board 14.9 Plan: Provider Input Budget Boundary

Date: 2026-09-01

Status: frozen before implementation

## Trigger

The fifth separately authorized Board 14 synthetic Manager execution consumed
its start approval and failed closed at the usage gate. The Provider reported
complete input usage far above the frozen total-token limit, while the exact
synthetic prompt remained small and contained no files, Artifacts, repository
content, credentials, or private project context.

The runtime diagnostic retained only complete usage shapes and bounded numeric
counts. It did not retain response text, JSONL, transcript, stderr, stdout, or
other raw Provider records. The terminal experiment and consumed approval must
not be retried.

## Goal

Make Provider-reported input usage an explicit, separately bounded part of a
future Board 14 experiment scope. Preserve the existing total-token hard gate
and fail-closed behavior; do not silently treat host or Provider input context
as free, prompt-derived, or approved.

## Scope

- add optional `max_input_tokens` and `max_output_tokens` hard limits to a
  Board 14 spec;
- bind supplied input/output limits into the exact experiment and start
  approval scopes;
- reject an inconsistent limit set where an individual limit exceeds the
  total-token cap or the input/output caps exceed the total cap together;
- enforce input, output, then total limits against complete Provider-reported
  usage;
- add privacy-safe `input_limit_exceeded` and `output_limit_exceeded`
  diagnostics that retain only usage, the applicable numeric cap, recognized
  source shapes, and `response_text_stored: false`;
- retain the existing `exceeded_limit` classification for total-token
  failures;
- add fake-App-Server fixtures and offline regressions for a large Provider
  input count, exact separate-budget success, incompatible policy rejection,
  and absence of raw response or prompt text from diagnostics.

## Excluded

- changing the current 2,000-token total cap in any existing experiment;
- estimating, discounting, or automatically approving unknown host/Provider
  overhead;
- changing the cost cap, retry count, timeout, permissions, App Server
  transport, output contract, or source-integrity rules;
- real App Server startup, Provider request, model call, retry, replay, new
  candidate preparation, or approval creation;
- retaining response text, raw protocol data, credentials, paths, files,
  Artifacts, workspaces, Git data, push, tag, Release, or deployment.

## Acceptance criteria

1. Existing total-token behavior remains fail-closed and unchanged.
2. A future spec may explicitly set a Provider input cap, which is bound into
   both approvals and enforced separately from the total cap.
3. Large fake input usage passes only when every explicit input, output, and
   total hard limit allows it.
4. Input/output cap failures record only the relevant numeric cap, complete
   normalized usage, source shape, and no-response assertion.
5. Focused and full offline tests, compilation, tracked JSON validation,
   current-tree and reachable-history privacy scans, and `git diff --check`
   pass.
6. One local-only commit is created without push, tag, Release, or real call.

## Next real-pilot boundary

Board 14.9 creates no candidate and grants no execution authority. A later
candidate must present all changed limits in its new experiment scope, then
repeat every separate approval and one-turn execution gate.
