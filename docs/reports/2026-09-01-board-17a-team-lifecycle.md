# Board 17A Report: Team Lifecycle and Project-Run Authorization

Date: 2026-09-01

Status: accepted offline; local private development only

## Contribution to PROJECT_GOAL

Board 17A closes an important part of the canonical user lifecycle: a normal
project run now has an explicit local authorization boundary tied to the
current ready team and exact project goal.

## Delivered

- Added a project-run approval action distinct from the synthetic
  Manager-platform approval.
- Bound each project-run approval to the current Supervisor team snapshot and
  exact normalized goal.
- Revalidated the team snapshot and goal immediately before any Adapter
  invocation.
- Consumed the project-run approval atomically and only once.
- Persisted team snapshot, approval and scope digest provenance on `runs`.
- Required `--start-approval` on the normal CLI `run` command.
- Added `supervisor request-run` for creating an exact project-run scope.
- Projected Supervisor team, snapshots, approvals and events through the local
  Web state and approval center.

## Safety and privacy

The board is offline and local-only. It does not invoke a Provider, App Server,
A2A, MCP or model. Project goals and approval scopes remain in ignored SQLite
runtime state. No runtime Artifact body, prompt instance, response, credential,
private path or downstream project content was added to tracked files.

The low-level `Orchestrator.run()` API remains compatible for existing internal
offline callers when no approval ID is supplied. The user-facing CLI path is
gated; removing the internal compatibility escape is deferred to a separately
scoped migration.

## Verification

```text
Focused Supervisor/Orchestrator/Web tests: 20 passed
Full offline suite: 134 tests passed
Python compilation passed
Tracked JSON validation passed
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

## Explicit non-goals

- no Artifact retention or purge;
- no new Provider or external call;
- no real Agent readiness transport;
- no repository-context or writing-Agent authorization;
- no worktree, Git publish, tag or GitHub Release.

## Next direction

The next board should extend synthetic readiness toward one narrowly scoped
local Agent lifecycle fixture (start/connect/attach and actual Model identity)
without adding a new external call. Artifact retention/purge remains a
separate future board and is not part of this completion.
