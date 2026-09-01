# Board 14.9 Report: Provider Input Budget Boundary

Date: 2026-09-01

Status: accepted offline verification; Board 14 remains in progress

## Trigger

The fifth separately authorized one-turn synthetic Manager execution completed
the v2 output-contract path but failed closed at the total-token gate. Complete
Provider usage indicated input far above the 2,000-token cap despite the
byte-bounded synthetic prompt.

The response body was not retained. The consumed experiment and start approval
are terminal and were not retried.

## Delivered

Board 14 now supports optional, exact-scope token budgets:

- `max_input_tokens` caps all complete Provider-reported input tokens;
- `max_output_tokens` caps all complete Provider-reported output tokens;
- `max_total_tokens` remains the combined hard cap.

If any component budget is present, a total-token cap is required. No component
cap may exceed that total, and configured input plus output caps may not exceed
it together. All limits are bound into the experiment and start-approval
SHA-256 scopes.

The executor enforces input, output, then total limits against the complete
Provider usage record. Input/output failures are classified as
`input_limit_exceeded` or `output_limit_exceeded`; total failures retain the
existing `exceeded_limit` classification.

Each over-limit diagnostic retains only complete normalized usage, the one
applicable numeric limit, recognized source shapes, and
`response_text_stored: false`. It retains no raw JSONL, prompt, response text,
task content, stderr, stdout, transcript, credential, path, file, or Artifact.

The default 2,000-token cap is unchanged. This board does not estimate,
discount, or automatically approve host or Provider context. A future
candidate must explicitly present every changed limit for human approval.

## Offline verification

Repository fake App Server regressions prove:

- large Provider input succeeds only when explicit input, output, and total
  budgets each permit it;
- input and output cap failures preserve the exact applicable cap rather than
  redacting it;
- inconsistent component/total limit policies are rejected during preparation;
- existing absent, incomplete, total-over-limit, strict-approval, integrity,
  output-contract, one-time-consumption, and zero-retry checks remain intact.

No test starts `codex.cmd`, contacts a Provider, accesses credentials, sends
network traffic, or invokes a model.

## Verification

```text
Focused Board 14 plus registry privacy tests: 31 tests passed
Full offline suite: 126 tests passed
Python compilation passed for model_council, tests and scripts
Tracked JSON validation passed (12 files)
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

## Next authorization boundary

All five prior Board 14 real synthetic attempts and their consumed approvals
remain terminal and must not be reused. Board 14.9 creates no candidate and
grants no process-start or model-call authority.

Only after a new candidate is explicitly authorized for local preparation may
a future scope set explicit input, output, and total budgets. It must then
repeat the complete experiment, arm, start-approval, approval, and one-turn
execution sequence with zero retries.
