# Board 10 Plan: Bounded Reviewer-Writer Repair and Recovery

Date: 2026-08-30

Status: acceptance scope frozen before implementation

## Goal

Add a persistent reviewer-writer repair state machine on top of one Board 9
worktree lease. Every writer attempt must produce a checkpoint, test evidence,
diff evidence and a reviewer decision. The deterministic control plane limits
iterations, elapsed time, changed files, diff size, feedback size and optional
token/cost consumption.

Board 10 is local-only. It does not connect an Adapter, invoke a model, transmit
a review bundle, merge automatically, discard automatically, add a second real
Agent family or add product UI scope.

## Frozen acceptance scope

1. Persist repair sessions, iterations and bounded audit events in SQLite.
2. Bind one session to one active worktree lease, its writing Agent and a
   distinct reviewer identity.
3. Require read, write and test permission before session creation.
4. Default to at most three iterations, with a configurable hard maximum of
   twenty.
5. Enforce configurable elapsed-time, changed-file, diff-byte and reviewer
   feedback limits.
6. Support optional hard token and cost budgets. Unknown usage under a hard
   budget must block conservatively rather than becoming zero.
7. Each writer iteration starts from a clean recorded Git head. Capture either
   checkpoints dirty changes or accepts an already clean new commit, then runs
   the configured test and collects Board 9 diff evidence.
8. A reviewer decision is exactly `accept` or `repair`. `accept` is rejected
   deterministically when the bound test evidence did not pass.
9. A `repair` decision persists bounded feedback for the next writer
   iteration. Reaching any hard limit stops the session without another call.
10. Interrupted writer or reviewer stages become explicitly recoverable:
    - retry a writer only when no Git change occurred;
    - capture existing writer changes only through an explicit local action;
    - reuse already captured evidence for a reviewer retry;
    - explicitly fail without deleting the worktree.
11. An accepted session may request the existing Board 9 exact merge approval
    only while its accepted Git head remains unchanged.
12. Provide local CLI operations for start, list, show, begin, capture, bundle,
    review, recover, cancel and merge-approval request.

## Default and absolute limits

| Dimension | Default | Absolute Board 10 maximum |
| --- | ---: | ---: |
| Iterations | 3 | 20 |
| Elapsed time | 1,800 seconds | 86,400 seconds |
| Changed files | 50 | 1,000 |
| Diff bytes | 128,000 | 128,000 |
| Reviewer feedback | 16,000 bytes | 64,000 bytes |
| Tokens | optional | user-supplied hard limit |
| Cost | optional | user-supplied amount and currency |

## Threat model and controls

| Threat | Board 10 control |
| --- | --- |
| Infinite reviewer-writer loop | Persisted hard iteration and elapsed-time limits |
| Scope grows across iterations | Per-iteration changed-file and diff-byte limits |
| Reviewer accepts known failing code | Deterministic test-status gate before acceptance |
| Unknown usage bypasses a budget | Unknown token/cost evidence blocks the next call under a hard budget |
| Stale acceptance reaches merge | Accepted head is rechecked before delegating to Board 9 approval |
| Crash silently retries or deletes work | Explicit recovery inspection and actions; no automatic discard |
| Interrupted reviewer causes a writer rerun | Captured test/diff evidence can be retried independently |
| Private repository evidence reaches another party | Board 10 has no Adapter/network integration; review bundles are local runtime/CLI data |
| Goals or feedback reach public GitHub | All session data remains ignored runtime SQLite; reports contain synthetic aggregate evidence only |

## State model

Session states:

```text
waiting_writer
  -> writer_running
  -> waiting_review
  -> reviewer_running
  -> waiting_writer | accepted | limit_reached
```

Interrupted stages move to `recovery_required`. Terminal states are
`accepted`, `limit_reached`, `failed` and `cancelled`.

Iteration states retain writer start, evidence capture, reviewer start,
`repair_requested`, `accepted`, interruption and limit/failure outcomes.

## Failure and recovery behavior

- A callback/process failure records only bounded local diagnostics and stops.
- Dirty changes after a writer interruption are never retried over or deleted;
  an operator may explicitly capture them or fail the session.
- A reviewer interruption retains the exact checkpoint/test/diff bundle and may
  retry review without invoking the writer again.
- Invalid acceptance returns to `waiting_review`.
- Cancellation changes only repair state; the worktree remains available for
  Board 9 inspection, approval or discard.
- Merge and destructive cleanup remain Board 9 single-use human approvals.

## Deferred work

Board 11 will connect and objectively evaluate a second real Agent family under
new outbound-context authorization. Board 12 will add the product approval
center, run comparison, backup and release preparation. Neither is implemented
in Board 10.
