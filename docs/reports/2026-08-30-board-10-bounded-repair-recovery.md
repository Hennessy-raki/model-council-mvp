# Board 10 Report: Bounded Reviewer-Writer Repair and Recovery

Date: 2026-08-30

Status: accepted and complete

## Objective

Deliver a persistent, bounded and recoverable reviewer-writer loop on top of
the isolated Board 9 workspace. The control plane, not either Agent, decides
when another iteration is allowed and whether evidence is sufficient for
acceptance or a later merge request.

The frozen scope and threat model are recorded in
`docs/reports/2026-08-30-board-10-bounded-repair-recovery-plan.md`.

## Delivered

### Persistent repair state

SQLite now stores:

- `repair_sessions`;
- `repair_iterations`;
- `repair_events`.

A session binds a worktree lease, writer, reviewer, goal, test command, policy,
usage totals, last bounded feedback and accepted Git head. Each iteration binds
its starting head, resulting checkpoint, Board 9 test/diff evidence, changed
file inventory, reviewer decision, bounded feedback and recovery outcome.

### Deterministic bounds

`RepairPolicy` enforces:

- one to twenty iterations;
- one second to 86,400 seconds elapsed time;
- one to 1,000 changed files;
- at most 128,000 diff bytes;
- at most 64,000 UTF-8 feedback bytes;
- optional hard token and cost limits.

Unknown token or cost consumption remains unknown. When the corresponding hard
budget exists, the next writer/reviewer call is blocked conservatively.

### Evidence-driven review

Every writer stage begins at a clean Git head. Capture checkpoints dirty
changes when required, runs the configured argument-array test and collects the
existing bounded diff evidence and changed-file inventory.

The local review bundle contains the exact checkpoint head, changed files,
bounded test output, bounded diff output and full evidence hashes. A reviewer
may return only `accept` or `repair`. The control plane rejects `accept` when
tests failed, regardless of reviewer preference.

An accepted session may request a Board 9 merge approval only when the
worktree remains clean at the accepted head. Merge itself remains a separate
SHA-256-confirmed, single-use human action.

### Recovery

Board 10 distinguishes:

- writer interruption before changes: safe retry as a new bounded attempt;
- writer interruption after changes: explicit capture or explicit failure;
- reviewer interruption: retry the reviewer against existing evidence;
- invalid acceptance: return to `waiting_review`;
- operator cancellation: stop repair state without deleting the worktree.

No recovery action silently resets, discards, rebases, merges or deploys.

### Local CLI and driver boundary

The CLI adds:

```text
repair start
repair list
repair show
repair begin
repair capture
repair bundle
repair review
repair recover
repair cancel
repair request-merge
```

`run_local_until_terminal` exists for injected local callbacks and synthetic
tests. It does not build or invoke an Adapter and has no network transport.
The CLI likewise performs only local state, Git, test and evidence operations.

## Verification

```text
73 tests passed
```

Eleven new synthetic-repository tests verify:

- a failing first iteration receives feedback and a passing second iteration is
  accepted;
- accepted evidence can request and complete the existing exact Board 9 merge;
- iteration limits stop without merge or discard;
- changed-file limits stop before reviewer execution;
- unknown token usage blocks a follow-up under a hard token budget;
- missing currency makes cost unavailable and blocks a follow-up under a hard
  cost budget;
- dirty writer interruption is explicitly captured;
- writer interruption before changes retries safely as a new bounded attempt;
- reviewer interruption reuses captured evidence;
- failing tests cannot be accepted;
- elapsed-time and feedback-byte limits are deterministic;
- the manual CLI cycle persists state across separate commands.

The complete Board 1-10 suite, Python compilation and full-history privacy scan
pass. Automated verification used only temporary synthetic Git repositories.
No Model Council worktree, real Agent, external endpoint or repository-context
model call was used.

## Privacy review

Repair goals, reviewer feedback, changed-file inventories, error diagnostics
and bounded test/diff excerpts may contain private project information. They
remain in ignored local runtime SQLite and are shown only through local CLI
inspection. Public reports contain only synthetic aggregate results.

Board 10 records:

- `PRIV-009`: numeric `max_total_tokens` policy was initially over-redacted by
  the generic credential sanitizer and now uses validated raw numeric JSON;
- `PRIV-010`: repair session evidence is private local runtime data;
- `PRIV-011`: review bundles could disclose repository content if forwarded;
  Board 10 exposes no Adapter/network path, and future real review requires a
  new exact outbound authorization.

## Deferred

Board 10 does not add a second real Agent family, external review, automatic
merge/discard, conflict resolution, Web approval center, backup or release
packaging. Boards 11 and 12 are handed to a fresh session and must be completed
sequentially.
