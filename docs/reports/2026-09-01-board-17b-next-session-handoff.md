# Board 17B Next-Session Handoff

Date: 2026-09-01

Status: local private development checkpoint; no external-call authority

## Current product goal

Model Council remains a local-first control plane: configure or accept a
heterogeneous Agent+Model team, verify every member, explicitly authorize the
exact project run, and deliver auditable, source-aware, budget-aware and
recoverable results.

## Completed in Board 17B

- Deterministic local fixture transitions: start, connect, attach, detach,
  stop.
- Ignored-runtime SQLite session and event records.
- Bounded process, login, actual-Model, permission, version, protocol and
  connectivity evidence.
- Remediation and `user_confirmation_required` handling.
- Lifecycle evidence bound into Supervisor snapshots and project-run approval
  stale-on-drift validation.
- Shared Supervisor service methods consumed by CLI and loopback Web state.

No Provider, model, App Server, A2A, MCP, network endpoint, repository,
worktree, Git operation or `runtime-board14/` content was used.

## Remaining goal-alignment gaps

1. The lifecycle fixture is deterministic control-plane evidence, not proof
   that a third-party Agent process or Model is operational.
2. Real project/repository-context execution, writing Agents and real Reviewer
   integration remain unauthorized.
3. Remote authentication/signing, live A2A/MCP validation, dynamic replanning
   and full pause/resume UX remain deferred.
4. Artifact retention/cleanup/purge remains a separate future board.

## Safe next route

The next candidate is a separately frozen real-Agent qualification board. Before
any implementation or call, it must define the exact Agent family, local-only
or external boundary, input/context inventory, process and permission scope,
token/cost limits, approval ladder, privacy threat model, acceptance criteria,
failure stop rules and exclusions. Prior login, readiness, connectivity or
consumed approvals do not authorize it.

Until that board is frozen and explicitly authorized:

- keep the public candidate disabled;
- do not invoke Provider, App Server, A2A, MCP or model;
- do not use repository context, worktrees, writes, Git or Artifact purge;
- keep all runtime state ignored and local.

## Verification checkpoint

The accepted Board 17B report is:

```text
docs/reports/2026-09-01-board-17b-agent-lifecycle-verification.md
```

The implementation must retain a local commit, full offline tests,
compilation, tracked JSON validation, current-tree and reachable-history
privacy scans, and `git diff --check` evidence before any next-board planning.
