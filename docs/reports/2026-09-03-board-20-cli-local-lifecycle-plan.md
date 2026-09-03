# Board 20 Plan: CLI Local Agent Lifecycle Sequence

Date: 2026-09-03

Status: frozen for local implementation; no external-call authority

## Contribution to PROJECT_GOAL

Board 20 advances the Agent-verification stage by making the local fake
subprocess lifecycle usable through the same CLI service boundary that an
operator will later use for real Agent checks.

## Scope

- Add a built-in local fake Agent process with no network or file access.
- Add one bounded CLI `supervisor lifecycle-sequence` command that runs an
  explicit ordered sequence in one Supervisor process.
- Reuse `SubprocessAgentLifecycleFixture`, `shell=False` semantics, bounded
  evidence and existing snapshot/approval drift controls.
- Keep the existing single-operation `supervisor lifecycle` command static and
  deterministic; it must not launch arbitrary commands.
- Persist only local runtime session/event evidence, not process output,
  credentials, private paths or raw handles.

## Authorization and threat model

The built-in fixture is opt-in and cannot be used to invoke a Provider, model,
network endpoint, repository, worktree or Git operation. The sequence rejects
invalid ordering and always stops the fixture before returning. No cross-process
PID control is introduced; process handles remain inside the bounded command.

## Acceptance criteria

- CLI sequence can complete start/connect/attach/detach/stop for one role.
- A failed or invalid transition is recorded and does not become ready.
- The fixture process is stopped before the command exits.
- No arbitrary shell string, output capture, credential persistence or private
  cwd is introduced.
- Existing Supervisor/Orchestrator/Web tests and full offline quality gates
  remain green.

## Exclusions

No real Agent, Provider, model call, external endpoint, repository context,
workspace, worktree, Git, Artifact purge, remote authentication, dynamic
replanning or pause/resume UX.
