# Board 18 Report: Local Fake Subprocess Agent Lifecycle

Date: 2026-09-01

Status: accepted for local private development

## Contribution to PROJECT_GOAL

Board 18 strengthens the Agent-verification stage by tying Supervisor
lifecycle evidence to one explicitly configured local fake subprocess. It
demonstrates process control without claiming external Agent, Provider or
Model qualification.

## Delivered

- Added `SubprocessAgentLifecycleFixture` with argument-array,
  `shell=False` process control.
- Added a tracked deterministic fake lifecycle process fixture.
- Persisted only safe process markers, exit codes, reason codes and hashes.
- Reused Board 17B session/event, snapshot and approval stale-on-drift
  controls.
- Added duplicate-start, stop/restart and resource-cleanup coverage.

## Verification

```text
Board 18 subprocess lifecycle test: passed
Board 17B Supervisor tests: passed
Full offline suite: 138 tests passed
Python compilation: passed
Tracked JSON validation: 12 files passed
Current-tree privacy scan: passed
Reachable-history privacy scan: passed
git diff --check: passed
```

## Safety and privacy

The fixture is local-only and opt-in through dependency injection. It does not
invoke a Provider, model, App Server, A2A, MCP or network endpoint. It does not
read `runtime-board14/`, repository context or private project data. Process
stdout/stderr, credentials, cwd and raw handles are not persisted.

## Explicit non-goals

- no real Agent or third-party endpoint qualification;
- no repository context, workspace, worktree, writes or Git;
- no Artifact retention/purge;
- no remote auth/signing, dynamic replanning or pause/resume UX.
