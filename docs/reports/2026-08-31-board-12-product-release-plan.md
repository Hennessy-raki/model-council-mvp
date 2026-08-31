# Board 12 Plan: Local Product Interface, Backup and Release Candidate

Date: 2026-08-31

Status: acceptance scope frozen before implementation

## Goal

Productize the existing loopback-only control surface without moving authority
out of SQLite or weakening any Board 8-11 gate. Add a unified approval center,
workspace/repair/evaluation evidence views, run comparison, privacy-safe local
backup/restore and repeatable release-candidate verification.

Board 12 does not invoke a model, merge or discard a worktree, accept a repair,
approve a different external context, deploy software or publish a release
outside the existing reviewed Git push.

## Frozen product interface scope

The existing dependency-free Web server remains bound to `127.0.0.1` or
`localhost`, with trusted Host, same-origin, per-process write token, CSP and
no-store protections.

The local product state adds:

1. one approval center for:
   - interoperability approvals;
   - outbound-context manifests;
   - workspace merge/discard approvals;
   - backup-restore approvals;
2. workspace leases, explicit permissions, bounded evidence and approval state;
3. repair sessions, iterations and bounded events;
4. objective evaluations, assertion results and linked usage evidence;
5. recent runs and deterministic pairwise comparison;
6. local backup records and restore status.

The browser may approve or reject only through the existing deterministic
service methods. An approval never consumes itself and never invokes, merges,
discards or restores automatically.

## Approval-center invariants

- Outbound-context approval requires the displayed scope SHA-256 and remains
  single-use.
- Workspace merge/discard approval requires the displayed scope SHA-256 and
  remains separate from merge/discard consumption.
- MCP approval remains separate from tool execution.
- Backup restore requires a new exact scope SHA-256 and a separate restore
  action after approval.
- Repair decisions and limits are displayed but not bypassed or synthesized by
  the browser.
- A page refresh performs no discovery, model, balance, Git, test or network
  operation.

## Run comparison

Pairwise comparison is deterministic and local. For each selected run it
reports:

- status and timestamps;
- task status counts;
- Artifact count;
- message count;
- usage calls, tokens, duration and cost-source evidence;
- budget alerts;
- routing-decision count;
- linked objective evaluation status when present.

The comparison reports exact numeric deltas only where both values are known.
Unknown cost remains unknown rather than zero.

## Backup and restore

Backups live only below ignored `state_dir/backups/<opaque id>/`.

Default backup:

- SQLite database only;
- no worktrees;
- no `.env` or credential stores;
- no repository files;
- no private paths in the public report or tracked manifest.

Artifact inclusion is explicit. When enabled, only files already registered in
the content-addressed Artifact store are copied. The backup manifest records
relative names, byte counts and SHA-256 values, not credential values.

Restore is destructive and therefore two-step:

1. request an approval bound to backup database hash, current database hash,
   Artifact inventory and target state directory identity;
2. approve the exact scope SHA-256 once;
3. revalidate current/backup state;
4. create an automatic pre-restore safety backup;
5. consume the approval and restore SQLite;
6. add missing verified Artifact files without deleting unrelated local files;
7. persist the consumed restore audit after migration.

Any state drift makes the approval stale. Restore never touches worktrees,
repositories, environment files or credential stores.

## Release candidate

Board 12 prepares version `0.2.0rc1` and a local release-verification command.
The command verifies:

- current branch is `main`;
- worktree and index are clean;
- `HEAD`, local `main` and tracked `origin/main` agree;
- full offline tests pass;
- Python compilation passes;
- all tracked JSON files parse;
- `python scripts/privacy_scan.py --history` passes;
- no runtime, worktree, database, `.env` or credential file is tracked;
- required Board 1-12 plans/reports and release documentation exist;
- commit author uses an intentionally public or GitHub noreply address.

Public remote verification remains a separate post-push `git ls-remote` check.
Board 12 does not create a tag or GitHub Release unless separately requested.

## Privacy and security verification

- Record every new observation in `docs/PRIVACY_ISSUES.md`.
- Never copy local evidence, absolute paths, evaluation response text, repair
  feedback, diffs, test output or backup contents into public reports.
- Test backup/restore only with temporary synthetic state.
- Run the complete suite, compilation, JSON validation, full-history privacy
  scan, staged-diff review and tracked-file review before commit.

## Deferred

Electron packaging, remote dashboards, cloud backup, automatic deployment,
automatic merge/discard/restore, repository-derived model evaluation and
additional real-model calls remain outside Board 12.
