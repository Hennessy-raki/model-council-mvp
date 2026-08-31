# Board 14.6 Report: Privacy-Safe Usage Failure Diagnostics

Date: 2026-08-31

Status: accepted offline verification; Board 14 remains in progress

## Trigger

The second separately authorized one-turn Board 14 Manager attempt consumed its
new start approval and failed closed after the Manager returned a structurally
valid two-task JSON plan. The pre-14.6 executor intentionally stored no raw
Provider response or usage record on a failed usage gate, so the local
postmortem could not distinguish unavailable usage from incomplete usage or a
complete value above the hard token limit.

That experiment and its start approval remain terminal. This board neither
retried nor inspected their raw protocol records.

## Delivered

The controlled executor now writes one failed local evidence record with kind
`codex_app_server_usage_diagnostic` when a completed Manager turn fails its
hard usage gate.

The diagnostic class is one of:

- `unavailable`: no recognized usage source was observed;
- `incomplete`: a recognized source was observed but lacks a valid complete
  input/output/total token tuple; or
- `exceeded_limit`: complete normalized usage exceeded the frozen hard token
  limit.

It considers only the existing supported locations:

- `thread/tokenUsage/updated.params.tokenUsage.last`;
- `thread/tokenUsage/updated.params.tokenUsage.total`; and
- `turn/completed.params.turn.usage`.

For unavailable and incomplete cases, runtime evidence stores only the fixed
source labels and semantic field-presence booleans. For an over-limit case it
also stores the normalized non-negative numeric usage and the fixed hard limit.
The generic sensitive-value sanitizer remains active; `max_total_tokens` is
explicitly recognized as the same non-sensitive numeric metric class as the
existing token usage fields.

The diagnostic never stores raw JSONL, prompt, response text, task plan,
stderr, stdout, transcript, credentials, paths, files, or Artifacts.
Fail-closed behavior, one process, one turn, zero retries, strict approval
rejection, source-integrity binding, and all existing limits are unchanged.

## Offline verification

Repository fake App Server fixtures prove:

- complete `last`, `total`, and completion-turn usage still succeeds within
  limits;
- no recognized usage records `unavailable` without response evidence;
- a partial recognized usage source records `incomplete` with only
  field-presence shape;
- complete usage above the hard limit records `exceeded_limit` with bounded
  numeric evidence;
- a direct `thread/tokenUsage/updated.params.tokenUsage` payload outside the
  three approved locations is not accepted;
- the diagnostic contains no raw response field or synthetic prompt;
- existing strict approval, one-time consumption, and executor-integrity tests
  continue to pass;
- registry sanitization preserves the explicit non-sensitive hard token limit
  while retaining credential redaction behavior.

No test runs `codex.cmd`, contacts PackyAPI, accesses credentials, sends HTTP,
or invokes a model.

## Verification

```text
Focused Board 14 experiments: 20 tests passed
Registry privacy/redaction: 6 tests passed
Full offline suite: 121 tests passed
Python compilation passed for model_council, tests and scripts
Tracked JSON validation passed
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

## Real-pilot boundary

The two prior Board 14 real synthetic attempts and their consumed approvals
remain terminal and must not be retried. Board 14.6 grants no execution
authority. A future real attempt requires a newly prepared candidate after
this commit and the complete experiment/start-approval/execute authorization
sequence again.
