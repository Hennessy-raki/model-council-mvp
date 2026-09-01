# Board 17B Report: Deterministic Local Agent Lifecycle Verification

Date: 2026-09-01

Status: accepted for local private development

## Contribution to PROJECT_GOAL

Board 17B advances the canonical lifecycle from synthetic team readiness to
auditable local Agent lifecycle evidence. The Supervisor can now model the
bounded start/connect/attach/detach/stop sequence for a deterministic fixture,
without treating configuration or prior readiness as proof of a live Agent.

## Delivered

- Added ignored-runtime SQLite records for one lifecycle session per bound role
  and ordered transition events.
- Added a deterministic fixture transition provider with explicit
  `start`, `connect`, `attach`, `detach` and `stop` operations.
- Added Supervisor service methods and CLI `supervisor lifecycle` entry point.
- Added independent process, login, actual-Model, permission, version, protocol
  and connectivity evidence keys while preserving Board 13 aliases.
- Added bounded remediation and `user_confirmation_required` handling.
- Bound lifecycle session/evidence digests into team snapshot revalidation so
  changed or stopped lifecycle state stales project-run approvals.
- Added loopback Web state projections for lifecycle sessions and events;
  projection refresh remains read-only.

## Verification

Focused Board 17B plus dependent tests:

```text
23 tests passed
```

Final full offline suite:

```text
137 tests passed
```

The restricted sandbox could not create temporary directories; that
environment error is not a code failure.

AST parsing, `git diff --check`, and local synthetic tests passed after the
implementation. Full suite, compilation, tracked JSON validation and both
privacy scans remain the final acceptance gate below.

## Safety and privacy

The implementation is local-only and deterministic. It does not create an
Adapter, invoke a Provider, open a network connection, start a real process,
read repository context, create a worktree, execute Git, or access
`runtime-board14/`.

Only bounded statuses, reason codes, redacted details, timestamps and
SHA-256 evidence digests are persisted. No credentials, raw process output,
prompts, Provider responses, private paths, file contents or Artifact bodies
are copied into tracked files.

## Explicit non-goals

- no real Agent, Provider, App Server, A2A or MCP validation;
- no remote authentication/signing;
- no repository-context or writing-Agent authorization;
- no worktree, Git, merge, publish, tag or release behavior;
- no Artifact retention/cleanup/purge;
- no dynamic replanning or expanded pause/resume UX.

## Remaining lifecycle gap

The fixture proves control-plane state transitions and evidence handling, not
that a third-party Agent process or Model is operational. Any future real
Agent pilot requires a separate frozen scope and independent exact
authorization.
