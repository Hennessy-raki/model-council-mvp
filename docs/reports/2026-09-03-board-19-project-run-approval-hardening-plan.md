# Board 19 Plan: Project-Run Approval Hardening

Date: 2026-09-03

Status: frozen for local implementation; no external-call authority

## Contribution to PROJECT_GOAL

The canonical lifecycle requires explicit user authorization for the exact
project run. Board 19 closes the remaining normal-library bypass so every
production `Orchestrator.run()` call must present a current, one-time
Supervisor project-run approval bound to the exact goal and ready team.

## Scope

- Make `Orchestrator.run()` fail closed when `start_approval_id` is absent.
- Preserve exact goal, team snapshot, lifecycle evidence and scope-digest
  revalidation through `SupervisorService.start_project_run()`.
- Keep an explicitly named private offline test harness for tests that exercise
  the collaboration pipeline without constructing a Supervisor team; this
  harness is not a project entry point and is never used by CLI/Web.
- Update affected tests and public-safe documentation to distinguish the
  production entry point from the test harness.
- Add regression coverage for missing approval at the Python API boundary.

## Authorization and privacy

No Provider, model, App Server, A2A, MCP, network, repository, worktree, Git
or Artifact operation is added. Approval scopes and goals remain local ignored
runtime state. The hardening only narrows authority.

## Acceptance criteria

- `Orchestrator.run(goal)` raises a controlled authorization error.
- `Orchestrator.run(goal, start_approval_id=...)` preserves existing
  single-use, stale-on-drift and exact-goal checks.
- CLI `run` remains approval-gated.
- CLI/Web do not expose or invoke the private test harness.
- Existing offline tests pass through explicit test-only setup.
- No credentials, runtime state, prompts, responses or private project data
  enter tracked files.
- Full tests, compilation, tracked JSON validation, current/history privacy
  scans and `git diff --check` pass.

## Explicit exclusions

- no real Agent qualification;
- no Provider/model/network call;
- no repository context, writes, worktrees or Git publication;
- no Artifact retention/purge;
- no removal of low-level test-only harness until a separately reviewed test
  migration makes it unnecessary.
