# Board 20 Report: CLI Local Agent Lifecycle Sequence

Date: 2026-09-03

Status: accepted for local private development

## Contribution to PROJECT_GOAL

Board 20 makes the Agent-verification lifecycle observable through the
operator-facing CLI while retaining a strictly local, bounded fixture
boundary.

## Delivered

- Added a built-in `model_council.local_fixture` process with no network or
  project-file behavior.
- Added `supervisor lifecycle-sequence` with explicit ordered operations.
- Kept the sequence in one Supervisor process so process handles never cross
  CLI boundaries and the fixture is stopped before exit.
- Reused existing lifecycle evidence, hashes, remediation and stale-on-drift
  controls.
- Added CLI regression coverage for start/connect/attach/detach/stop.

## Verification

```text
Full offline suite: 140 tests passed
CLI lifecycle-sequence test: passed
ResourceWarning-enabled fixture test: passed
AST parsing: passed
Python compilation: passed
Tracked JSON validation: 12 files passed
Current-tree privacy scan: passed
Reachable-history privacy scan: passed
git diff --check: passed
```

## Safety and privacy

The built-in fixture is local-only. It does not invoke a Provider, model,
network endpoint, repository, worktree or Git operation. The CLI does not
accept arbitrary shell strings or persist raw process handles, stdout, stderr,
credentials or private paths.

## Explicit non-goals

- no real Agent or third-party endpoint qualification;
- no Provider/model call or external transport;
- no repository context, writes, worktrees or Git publication;
- no Artifact retention/purge or expanded pause/resume UX.
