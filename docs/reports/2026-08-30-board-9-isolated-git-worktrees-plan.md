# Board 9 Plan: Isolated Git Worktrees and Permissions

Date: 2026-08-30

Status: acceptance scope frozen before implementation

## Goal

Allow a writing Agent to operate in one isolated linked Git worktree while the
local deterministic control plane retains authority over read, write, test,
merge and destructive cleanup. No Agent, manager proposal or Adapter may grant
itself permission or merge directly into the user's target checkout.

Board 9 uses only temporary synthetic Git repositories for automated
verification. It does not create an Agent worktree for the Model Council
repository, send repository content to an external model, add an automatic
repair loop, add a second real Agent family or add product UI scope.

## Frozen acceptance scope

1. Create one persistent lease and one linked Git worktree per writing Agent
   under the configured ignored runtime root.
2. Start every lease with `read=true` and `write=test=merge=false`.
3. Persist explicit permission changes in SQLite. Merge permission requires
   read, write and test permission.
4. Bind a CLI Adapter invocation to the assigned Agent, worktree path and exact
   read-only or workspace-write sandbox mode.
5. Create recoverable checkpoints on the isolated branch with a generic
   GitHub-noreply author, avoiding local Git author identity.
6. Run test command arrays with `shell=False`, a bounded timeout, at most
   64,000 retained bytes per output stream and SHA-256 over each complete
   stream.
7. Collect at most 128,000 retained bytes of diff output plus complete-output
   hashes and exact Git state metadata.
8. Require a clean target, clean Agent worktree, unchanged target SHA,
   fast-forward relationship, current diff evidence and passing test evidence
   before a merge approval can be requested.
9. Bind merge approval to the target/source SHAs and exact evidence IDs/hashes.
   Approval requires confirmation of the displayed scope SHA-256, is consumed
   once and becomes stale when state changes.
10. Require the same two-step exact approval before destructive worktree
    discard. Bind tracked changes plus untracked paths/content, limited to
    1,000 files and 64 MiB of hashed untracked content.
11. Preserve paths, diffs, commands, output excerpts and approval records only
    in ignored local runtime state.

## Threat model and controls

| Threat | Board 9 control |
| --- | --- |
| Agent writes into the user's primary checkout | Dynamic Agent execution resolves only to its assigned linked worktree |
| Manager or Agent grants itself authority | Permissions are local persisted operator decisions; default is read-only |
| Shell injection through repository, ref or test command | Generated paths/branches, validated refs, argument arrays and `shell=False` |
| Runtime worktree becomes public repository content | Any Git repository containing the runtime root must pass `git check-ignore` before worktree creation |
| Personal Agent label leaks through a pushed ref | Branch names contain only an opaque lease prefix |
| Unbounded test/diff evidence consumes memory | Concurrent draining retains fixed byte caps while hashing complete streams |
| Stale approval merges changed code | Approval binds target/source SHAs, diff and passing-test evidence; exact state is rechecked |
| Merge overwrites divergent target history | Clean target and `git merge --ff-only` only |
| Destructive discard deletes post-approval changes | Discard scope hashes tracked and bounded untracked content and becomes stale on drift |
| Local Git author reveals a personal email | Checkpoints use a fixed generic GitHub-noreply identity |
| Private evidence reaches GitHub | Runtime state is ignored; public reports use synthetic aggregate results only; staged/history privacy scans gate release |

## State model

SQLite adds:

- `worktree_leases`;
- `worktree_permissions`;
- `worktree_evidence`;
- `worktree_approvals`.

Lease states are `active`, `merged`, `discarded` or `failed`. Approval states
are `pending`, `approved`, `rejected`, `consumed`, `failed` or `stale`.
Persisted records allow a later local process to inspect and continue an
unchanged lease without adding Board 10 retry orchestration.

## Failure and rollback behavior

- Failed worktree creation removes only the branch/worktree that the same
  operation created.
- Failed tests and checkpoints preserve the isolated worktree and store bounded
  local evidence.
- State drift before approval consumption marks the approval stale and performs
  no merge or discard.
- An approval is consumed before an irreversible action. If that action fails,
  it is marked failed and cannot be replayed; a fresh inspection and approval
  is required.
- Merge cleanup failure does not roll back an already completed fast-forward;
  it is returned as local cleanup evidence for manual handling.

## Deferred work

Board 10 will define bounded reviewer-writer repair iterations, retry budgets
and recovery checkpoints. Board 11 will add and objectively evaluate a second
real Agent family. Board 12 will productize approvals, comparisons, backup and
release preparation. None of those capabilities is implemented in Board 9.
