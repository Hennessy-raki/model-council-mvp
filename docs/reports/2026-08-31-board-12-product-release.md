# Board 12 Report: Local Product Interface and Release Candidate

Date: 2026-08-31

Status: accepted and complete

## Objective

Complete the local product surface, unified approval center, workspace/repair/
evaluation evidence views, deterministic run comparison, privacy-safe local
backup/restore and release-candidate verification without weakening any
existing control-plane gate.

The frozen scope is recorded in
`docs/reports/2026-08-31-board-12-product-release-plan.md`.

## Delivered

### Loopback product and approval center

The dependency-free Web interface now projects one local product state from
SQLite:

- interoperability and MCP approval records;
- exact outbound-context manifests, including deliberate local prompt review;
- workspace leases, permissions, bounded evidence and merge/discard approvals;
- repair sessions, iterations, limits and events;
- objective evaluation assertions and linked local evidence;
- local backup records and restore approvals.

The interface remains restricted to `127.0.0.1` or `localhost` with trusted
Host, same-origin writes, a per-process token, CSP and no-store headers.
Approval delegates to the existing deterministic service methods. Approval
does not invoke, execute, merge, discard or restore, and page refresh performs
none of those actions.

### Deterministic run comparison

`RunComparisonService` reports run status, task counts, Artifact and message
counts, usage sources, token and duration totals, budget alerts, routing
decisions and linked objective-evaluation status. Pairwise comparison computes
numeric deltas locally. Unavailable cost evidence remains unavailable rather
than becoming zero.

The CLI exposes:

```text
compare show
compare runs
```

### Privacy-safe backup and restore

`BackupService` uses SQLite's consistent backup API. Database-only backup is
the default. Registered Artifacts may be included explicitly and only after
containment, byte-count and SHA-256 verification.

The manifest records relative names, sizes and hashes. It never includes
credentials, environment files, repositories or Git worktrees. Restore
requires:

1. a pending request bound to the backup, current logical database state,
   Artifact inventory and state-directory identity;
2. exact SHA-256 approval;
3. unchanged-state revalidation;
4. an automatic pre-restore safety backup;
5. single-use consumption and atomic SQLite replacement.

Missing verified Artifacts are added without deleting unrelated files or
overwriting a hash conflict. State drift marks the approval stale.

### Release candidate

The package version is `0.2.0rc1`. `ReleaseVerifier` and
`scripts/release_verify.py` validate:

- clean `main` and agreement among `HEAD`, `main` and `origin/main`;
- GitHub noreply commit-author metadata;
- version consistency;
- required Board 1-12 plans, reports and release documentation;
- safe tracked filenames;
- all tracked JSON;
- the full offline suite;
- Python compilation for package, tests and scripts;
- full reachable-history privacy scanning.

No Git tag, GitHub Release, deployment or external model call is part of Board
12.

## Verification

The final pre-commit gate passed:

```text
93 tests passed
Python compilation passed for model_council, tests and scripts
All tracked JSON files parsed
git diff --check passed
Full-history privacy scan passed
runtime/, runtime-*/, .env and Python caches remain ignored
No runtime database, worktree, backup or credential file is tracked
Git author uses the public GitHub noreply address
```

Seventeen focused Board 12 tests cover backup exclusions and Artifact restore,
tamper detection, stale approvals, safety backups, run comparison, exact
outbound/workspace/restore approval, Web security/read-only comparison and
release version/tracked-file policy.

The clean-main release verifier is run after the Board 12 commit so its clean
worktree and synchronized-ref checks can be meaningful. Public remote
verification remains a separate post-push check.

## Privacy review

The complete changed-file and reachable-history review found no credential,
personal email, real username path, runtime database, worktree, private repair
evidence, evaluation response text or private-project content in the tracked
Board 12 change.

The issue register records:

- `PRIV-013`: backups contain private local runtime state; mitigated and
  accepted with ignored storage, database-first defaults and exact restore
  approval;
- `PRIV-014`: the approval center deliberately displays private evidence
  locally; mitigated and accepted with loopback and browser security controls;
- `PRIV-015`: verifier failure diagnostics may contain local details;
  mitigated and accepted as bounded local-only output.

Board 8 outbound approval, Board 9 merge/discard approval and Board 10 repair
limits remain unchanged. The consumed Board 11 approval authorizes no further
external call.
