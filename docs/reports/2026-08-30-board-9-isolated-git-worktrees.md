# Board 9 Report: Isolated Git Worktrees and Permissions

Date: 2026-08-30

Status: accepted and complete

## Objective

Deliver a local, persistent and evidence-driven workspace boundary for writing
Agents. An Agent can be bound to one isolated linked Git worktree, but cannot
write, test, merge or discard without the corresponding deterministic
permission and approval checks.

The frozen scope and threat model are recorded in
`docs/reports/2026-08-30-board-9-isolated-git-worktrees-plan.md`.

## Delivered

### Persistent workspace control plane

`WorkspaceService` creates opaque worktree leases below ignored runtime state
and persists lease identity, assigned Agent, source/target Git state and
explicit read, write, test and merge permissions in SQLite. Leases start
read-only. Permission dependencies prevent merge authority without read, write
and test authority.

`CliAdapter.invoke_in_workspace` provides the dynamic working-directory entry
point. `WorkspaceService.invoke_cli` verifies the assigned Agent, persisted
permission and exact `read_only` or `workspace_write` sandbox observation
before using it. Board 9 exercises this only with the local fake CLI.

### Bounded evidence

The workspace CLI can create a recoverable isolated-branch checkpoint, run a
test command array and collect a Git diff. Checkpoints use the fixed author:

```text
Model Council <model-council@users.noreply.github.com>
```

Test execution retains at most 64,000 bytes per stdout/stderr stream and
records complete-stream SHA-256 values, total byte counts, exit code, duration
and timeout state. Diff evidence retains at most 128,000 bytes and binds the
base SHA, current head SHA, cleanliness and status hash.

### Exact merge and discard approval

Merge requests require:

- an active lease with merge permission;
- clean target and Agent worktrees;
- the original target branch and unchanged target SHA;
- a fast-forward Agent branch;
- current clean diff evidence;
- a passing test captured at the exact clean Agent head.

The pending approval binds all of those facts into one `scope_sha256`.
Confirmation must match exactly. Execution rechecks the scope, consumes the
approval once, and uses `git merge --ff-only`.

Destructive discard uses a separate exact approval. Its scope hashes tracked
changes and untracked paths/content with limits of 1,000 files and 64 MiB.
Changed content after approval makes the request stale rather than deleting the
new state.

### CLI

Board 9 adds `workspace prepare`, `list`, `show`, `permission`, `checkpoint`,
`test`, `diff`, `evidence`, `request-merge`, `request-discard`, `approvals`,
`approve`, `reject`, `merge` and `discard`.

All Git and test operations use argument arrays with `shell=False`. Base refs
are validated and worktree paths are generated/contained under runtime state.

## Verification

```text
62 tests passed
```

Seven new synthetic-repository tests verify:

- read-only lease defaults and permission dependencies;
- Agent identity and CLI sandbox binding;
- isolated checkpoint, bounded test output and diff collection;
- passing-test/current-diff requirements before merge;
- exact SHA-256 confirmation, fast-forward merge and replay rejection;
- dirty discard scope drift detection;
- generic opaque branch naming without Agent labels;
- cross-repository runtime roots must be ignored by their containing Git
  repository;
- credential-like inline test flags and unsafe Git refs are rejected;
- CLI preparation works against a temporary synthetic repository.

The full suite and Python compilation pass. No real Agent, external endpoint,
private repository or Model Council repository worktree was used.

## Privacy review

Board 9 local state intentionally may contain absolute paths, private filenames,
diffs and test output. It remains in ignored runtime SQLite/worktree paths and
is never copied into this report. The public implementation and tests use only
generic names and temporary synthetic repositories.

Four observations are recorded in `docs/PRIVACY_ISSUES.md`:

- `PRIV-005`: private/machine context in ignored local worktree evidence is
  mitigated through ignored runtime containment, bounded retention and release
  scans;
- `PRIV-006`: Agent labels were removed from generated Git branch names before
  public commit;
- `PRIV-007`: a non-personal synthetic email-shaped fixture was replaced with
  the fixed project GitHub-noreply identity after the release scanner flagged
  it;
- `PRIV-008`: runtime ignore enforcement now checks the Git repository that
  actually contains a custom `state_dir`, not only the target project.

The complete repository, reachable history, tracked filenames, ignore rules,
staged diff and commit-author metadata are release gates before push.

## Deferred

Board 9 does not add automatic reviewer-writer retries, rebases, conflict
repair, a second real Agent family, repository-context external calls, Web UI
controls or deployment. Board 10 is the next planning boundary.
