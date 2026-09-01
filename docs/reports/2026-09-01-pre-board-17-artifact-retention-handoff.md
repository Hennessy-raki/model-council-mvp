# Pre-Board 17 Artifact Retention Handoff

Date: 2026-09-01

Status: handoff only; Board 17 is not frozen, approved, or implemented

## Purpose and checkout

This record prepares the next local development session without authorizing a
new product board, external call, runtime mutation, or Artifact deletion.

Work only in the existing user-approved checkout. Do not copy the repository,
create a worktree, push, tag, or create a GitHub Release. Runtime data,
credentials, backups, Provider records, prompts, responses, private downstream
content, and worktrees remain outside Git.

At handoff preparation, the local checkpoint was:

```text
branch: main
HEAD: 76bfd46 Rebaseline project status and roadmap
relative to origin/main: ahead 14
tracked worktree: clean before this documentation update
```

The ignored local Board 14 configuration still exists below
`runtime-board14/`; it must remain ignored. No runtime record or private
supplement was copied into this report.

## Completed product boundary

- Boards 1 through 12 remain the prepared public `0.2.0rc1` release candidate.
  This checkout has not pushed, tagged, or published it.
- Board 13 is complete only for local-private Supervisor readiness controls.
- Board 14 is terminal local-private incubation. Board 14.11 completed one
  separately authorized, read-only synthetic Manager turn. Earlier attempts,
  that successful experiment, and all consumed approvals must never be
  replayed or treated as authority for another call.
- Board 15 is complete. It reconciled the project-status documents and added
  deterministic status regression coverage. It created no new external-call
  authority.
- Board 16 has not started. One Windows loopback interruption was observed,
  but it was not reproducible: the focused and full offline suites then passed.
  Do not implement a Board 16 repair unless a reproducible local fixture
  failure is first captured and its scope is frozen.

## Baseline evidence

The handoff preparation session ran:

```powershell
python -m unittest discover -s tests -v
```

Result: 129 tests passed.

Before accepting any follow-on documentation or implementation work, rerun the
full required quality gate:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q model_council tests scripts
python scripts/privacy_scan.py
python scripts/privacy_scan.py --history
git diff --check
```

Also validate all tracked JSON files using the repository's established JSON
validation command before a local commit. The privacy scan must cover both the
current tree and reachable history.

## Candidate direction only: Board 17A

The current candidate direction is **Artifact retention policy and safe cleanup
preview**. It is not a commitment to the broader Board 17 topics listed in
`docs/PROJECT_STATUS.md`, and it is not approval to change any code.

The suggested first sub-board is deliberately narrow:

- define a local retention-policy model;
- produce a read-only inventory/preview of prospective cleanup;
- model an exact, single-use human approval for any later destructive action;
- add no automatic deletion;
- defer actual purge to a separately frozen and separately authorized board.

This direction should remain entirely offline. It must not invoke a Provider,
start an App Server, use A2A or MCP, transmit context, access a private
downstream project, or inspect/copy real runtime Artifact contents.

## Read-only implementation findings

The next session should verify these findings before using them as design
inputs:

1. `model_council/artifacts.py` currently exposes content insertion and
   bounded text reading; it has no retention or purge API.
2. Artifact physical paths are content-addressed by SHA-256. Records with the
   same content can share one physical file, so deleting a database record
   does not by itself prove that deleting its path is safe.
3. The SQLite `artifacts` table retains an Artifact ID, run/task association,
   name, media type, SHA-256, path, provenance fields, and creation time.
4. `model_council/backup.py` supplies useful safety patterns: optional
   Artifact backup, SHA-256-bound approval, stale-on-drift validation, path
   containment checks, integrity checks, and a pre-restore safety backup.
5. Relevant existing test coverage begins in `tests/test_artifacts.py` and
   `tests/test_backup.py`.

These are source-level observations, not permission to read local runtime
Artifact bodies or mutate runtime state.

## Required Board 17A freeze before implementation

Do not prepare code until the user explicitly accepts all of the following.

| Topic | Required decision |
| --- | --- |
| Business objective | The operator problem that retention preview solves. |
| Scope | Whether this is policy + preview only, or includes a later purge board. |
| Retention inputs | Which metadata fields are eligible, and which protected states are excluded. |
| Preview output | Which aggregate/count/hash/path-safe fields may be shown locally. |
| Deletion semantics | Database record treatment, shared-file reference counting, and error handling. |
| Recovery | Exact safety-backup contents, location, bounds, and verification evidence. |
| Approval | Exact scope digest, stale-on-drift inputs, confirmation text, single-use state, and consuming action. |
| Privacy | Whether any runtime metadata leaves ignored local state; default is no. |
| Acceptance | Offline tests, negative tests, migration requirements, scans, and documentation updates. |
| Exclusions | No automatic purge, no Provider/App Server/A2A/MCP, no Git operation, no worktree, and no private-content display. |

The initial threat model must at least address stale previews, record/file
divergence, shared-content deletion, path traversal, concurrent state changes,
backup failure, partial cleanup failure, operator misconfirmation, and
retention of private metadata in logs or tracked documentation.

## Recommended sequence after a scope freeze

1. Re-verify the real checkout, status, HEAD, ignored runtime configuration,
   project documents, and current privacy register.
2. Write a Board 17A plan that fixes acceptance criteria, threat model,
   non-goals, runtime storage rules, preview schema, and authorization ladder.
3. Add offline tests before or alongside implementation. Include shared
   SHA-256 physical-file cases, zero-match previews, stale approval, safety
   backup failure, database/filesystem divergence, containment failure, and
   a guarantee that preview alone does not delete.
4. Implement only the frozen policy/preview/approval model. Do not call the
   destructive action unless the user later grants an exact separate
   authorization.
5. Add the board report and update the roadmap, project handoff, start-here
   entry point, and privacy register when the final scope requires it.
6. Run full tests, compilation, tracked JSON validation, current-tree and
   reachable-history privacy scans, and `git diff --check`.
7. Review the diff for private paths, runtime state, backups, credentials,
   prompts, Provider records, response bodies, or private project content.
8. Create one local commit only. Do not push, tag, or publish.

## Opening instructions for the next session

Read, in order:

```text
AGENTS.md
README.md
docs/ARCHITECTURE.md
docs/PROJECT_HANDOFF.md
docs/ROADMAP.md
docs/DEVELOPMENT_BOARDS.md
docs/PROJECT_STATUS.md
docs/START_HERE_NEXT_SESSION.md
docs/PRIVACY.md
docs/PRIVACY_ISSUES.md
docs/reports/2026-09-01-board-15-project-rebaseline.md
this handoff
```

Use `runtime-board14/` only for local-private Board 14 state when it is
strictly necessary for a user-authorized review. Never commit, quote, transmit,
or paste its contents into an external prompt. Previous login or connectivity
readiness evidence does not authorize a new model call.

Stop after planning if the user has not explicitly frozen Board 17A. This
handoff deliberately authorizes neither a candidate preparation nor a purge.
