# Board 18 Plan: Local Fake Subprocess Agent Lifecycle

Date: 2026-09-01

Status: frozen for local implementation; no external-call authority

## Contribution to PROJECT_GOAL

Board 18 advances the Agent-verification step of the canonical lifecycle from
deterministic state-only evidence to evidence tied to one bounded local fake
process. It demonstrates that the control plane can start, observe, attach,
detach and stop an Agent-like process without treating external connectivity,
login or Model metadata as verified by assumption.

## Business objective

For a configured role, the operator must be able to inspect a local fake
subprocess lifecycle with explicit process identity and exit evidence while
keeping all other readiness checks independent and fail-closed.

## Scope

- Add a tracked deterministic fixture process under `tests/fixtures/`.
- Add a subprocess-backed lifecycle fixture usable only with an explicit local
  fixture command array.
- Execute command arrays with `shell=False`, bounded environment and no private
  repository cwd.
- Persist only safe process state, synthetic pid marker, exit code, bounded
  reason codes and hashes; never stdout/stderr or credentials.
- Reuse Board 17B Supervisor session/event APIs and snapshot/approval drift
  binding.
- Keep CLI/Web projections read-only unless a caller explicitly invokes the
  local fixture service method.

## Inputs and outputs

Inputs are registered role bindings and an explicit synthetic fixture command
array. Outputs are lifecycle state, safe process marker, exit status and
transition evidence. No Provider, model, network, repository, Artifact or
runtime-board14 data is an input or output.

## Authorization and safety

The fixture command must be an exact argument array and is launched only by a
local service call. There is no Provider, App Server, A2A, MCP, network,
repository, worktree, Git or project-task execution authority. Prior approvals
do not authorize a new process beyond this fixture scope.

## Acceptance criteria

- deterministic fixture process starts and exits under service control;
- duplicate start, missing process, attach-after-exit, detach and stop are
  fail-closed and auditable;
- process evidence includes only bounded safe metadata;
- login, actual-Model, permission, version, protocol and connectivity remain
  separate checks;
- lifecycle evidence drift stales team snapshots and project-run approvals;
- no shell string execution, private cwd, credential capture or output
  retention;
- CLI/Web and existing offline tests remain green;
- compile, tracked JSON validation, current/history privacy scans and
  `git diff --check` pass.

## Exclusions

No real Agent, Provider, model call, external endpoint, repository context,
workspace/write permission, Git operation, Artifact purge, remote auth,
dynamic replanning or pause/resume UX is included.
