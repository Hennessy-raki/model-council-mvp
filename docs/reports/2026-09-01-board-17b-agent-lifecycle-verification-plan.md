# Board 17B Plan: Deterministic Local Agent Lifecycle Verification

Date: 2026-09-01

Status: frozen for implementation planning; no code or runtime state changed by
this freeze

## Contribution to PROJECT_GOAL

This board advances the lifecycle from a configured, synthetically ready team
to evidence that each bound Agent can be started, connected, attached and
detached under a deterministic local fixture. It strengthens the existing
Supervisor gate without authorizing a Provider call, external endpoint,
repository context or project write.

## Business objective

Before a project-run approval can be considered current, the operator must be
able to inspect a bounded lifecycle record for each Manager, Worker and
Reviewer binding:

- the local Agent process was started or observed;
- the configured session was connected and, when applicable, attached;
- login/authentication state was observed without storing credentials;
- the actual Model identity was observed and matched to the bound Model;
- permission, version, protocol and connectivity evidence were captured;
- detach/stop leaves an explicit terminal lifecycle state;
- failures include deterministic remediation and
  `user_confirmation_required` where machine evidence is unavailable.

The fixture is a control-plane test instrument, not a substitute for a live
Provider or a claim that a real Agent has been qualified.

## Scope

### In scope

1. Add a local deterministic Agent lifecycle fixture with explicit operations:
   `start`, `connect`, `attach`, `detach` and `stop`.
2. Add a Supervisor service layer for one lifecycle session per bound role.
3. Persist bounded lifecycle state, evidence digests, transitions, remediation
   and confirmation references in the existing ignored local SQLite runtime.
4. Normalize separate checks for:
   `process`, `login`, `actual_model`, `permission`, `version`, `protocol` and
   `connectivity`.
5. Keep existing Board 13/17A readiness and approval semantics:
   readiness is fail-closed, snapshots are immutable, drift stales approvals,
   and approval consumption is atomic and single-use.
6. Bind the current lifecycle evidence digest into the existing team snapshot
   validation. A project-run approval must become stale if lifecycle evidence
   changes after snapshot or approval.
7. Expose the same service operations through CLI and the loopback Web
   projection. Web actions must not perform an implicit external action.
8. Use only deterministic local fixtures and temporary SQLite databases in
   tests. Keep Manager, Worker and Reviewer execution synthetic and local.

### Inputs

- Existing registered Agent+Model role bindings.
- A tracked, synthetic lifecycle fixture profile containing only bounded
  observations and transition outcomes.
- Existing team snapshot and project-run approval identifiers when testing
  run-start revalidation.
- Optional explicit confirmation text for a displayed
  `user_confirmation_required` check.

No repository files, workspace paths, credentials, Provider responses,
prompts, Artifacts or ignored Board 14 runtime data are inputs.

### Outputs

- Current lifecycle session state per role.
- Ordered local transition events with timestamps and safe reason codes.
- Bounded evidence for the seven checks, including expected/observed Model
  identifiers and protocol/version values where applicable.
- Deterministic remediation text and confirmation-required markers.
- Lifecycle evidence SHA-256 bound to readiness reports and team snapshots.
- CLI JSON and Web read-only projections using the same Supervisor service.

Raw process output, credentials, response text, repository content and private
paths are not outputs.

## State and transition model

The fixture supports the following fail-closed states:

```text
configured
  -> starting
  -> started
  -> connecting
  -> connected
  -> attaching
  -> attached
  -> detached
  -> stopped
```

Any operation may enter `failed` with a bounded reason code. `attach` is
required only for `attach` and `attach_or_spawn` bindings; `remote` and
`manual` remain explicit non-process modes and must not be reported as
machine-started. Repeated or out-of-order operations are rejected or recorded
as deterministic no-ops; they never create a false `ready` state.

## Authorization ladder

1. Configure the existing Manager, Worker and Reviewer bindings and a local
   fixture profile.
2. Start/connect/attach only the selected local fixture session.
3. Run lifecycle evidence checks and inspect remediation or confirmation
   requirements.
4. Resolve failures or record an exact user confirmation for a displayed
   check.
5. Re-run checks and create a team snapshot containing the lifecycle evidence
   digest.
6. Request and approve the exact project-run scope.
7. Run with the same goal and approval; revalidate lifecycle, team and goal
   immediately before any Adapter boundary.
8. Detach/stop the fixture and retain only bounded local audit evidence.

This ladder grants no new model-call authority. Existing synthetic
Manager-platform approval remains a separate action.

## Privacy and storage rules

- Use the approved existing checkout only; do not copy the repository or
  create a worktree.
- Never read, display, quote, copy, commit, transmit or pass to a model any
  content from `runtime-board14/`.
- Store lifecycle state only in ignored local runtime SQLite tables.
- Persist identifiers, statuses, hashes, bounded reason codes and redacted
  metadata only. Never persist credentials, environment values, raw stdout or
  stderr, prompts, Provider responses, repository paths, file contents,
  Artifact bodies or private project material.
- Tracked fixtures and tests must use synthetic labels, loopback-neutral
  values and non-personal paths.
- Run current-tree and reachable-history privacy scans before board
  acceptance.

## Acceptance criteria

### Functional

- A fixture can deterministically start, connect, attach, detach and stop.
- Each role exposes the seven checks with independent status and evidence.
- Actual Model mismatch, process absence, login failure, insufficient
  permission, version mismatch, protocol mismatch and connectivity failure
  produce `not_ready` plus deterministic remediation.
- Missing machine evidence produces `user_confirmation_required` and cannot
  be silently promoted to ready.
- A current lifecycle evidence digest is included in readiness/snapshot
  validation.
- Evidence drift after snapshot or approval stales the approval before run.
- No task or Adapter invocation occurs before a valid project-run approval.
- CLI and Web use the same service methods and expose equivalent state.
- Detach/stop and failed transitions are auditable and recoverable locally.

### Negative and race coverage

- Missing process; failed login; wrong observed Model; denied permission;
  version/protocol mismatch; connectivity failure.
- Manual confirmation required, incorrect confirmation, and confirmation
  against a changed check.
- Out-of-order attach/detach, duplicate start, and concurrent transition or
  approval consumption.
- Lifecycle evidence drift, team binding drift, goal drift, wrong approval
  action, consumed approval replay and stale snapshot.
- Assert no Provider, App Server, A2A, MCP, network, repository, worktree or
  Git subprocess is reached by the fixture path.

### Quality and delivery

- Full offline test suite, compilation, tracked JSON validation and both
  privacy scans pass.
- `git diff --check` passes.
- Add a public-safe implementation report, roadmap/status/handoff updates and
  one identifiable local commit.
- Do not push, tag, create a GitHub Release or claim remote verification.

## Threat model

The control plane must fail closed against:

- treating a configured or discovered Agent as started without process
  evidence;
- treating login, Model, permission, version, protocol or connectivity as
  successful by assumption;
- reporting a stale lifecycle record as current;
- bypassing snapshot/project-run approval through CLI, Web or low-level service
  calls;
- replaying a consumed transition or approval;
- concurrent updates causing two starts or two approvals to succeed;
- leaking credentials, process output, private paths or repository content into
  tracked files or audit records;
- interpreting prior login, readiness, connectivity or consumed approvals as
  authorization for a new model call.

## Explicit exclusions

- No Provider, App Server, A2A, MCP, model or other external call.
- No real third-party endpoint, remote authentication or message signing.
- No repository context, workspace lease, worktree, file write, test command,
  Git operation, merge, publish, tag or release.
- No real Manager/Worker/Reviewer execution or Reviewer integration.
- No Artifact retention, cleanup preview or purge.
- No generic context summarization, dynamic replanning or expanded pause/
  resume user experience.
- No removal of the existing low-level `Orchestrator.run()` compatibility
  path; that remains a separate migration scope.

## Implementation deliverables after separate execution start

- Service, storage, CLI and Web changes limited to this frozen scope.
- Deterministic fixture and regression tests for all acceptance cases.
- `docs/reports/2026-09-01-board-17b-agent-lifecycle-verification.md`.
- Updated roadmap, project status, handoff and privacy issue register.
- Local identifiable commit only; no publication.
