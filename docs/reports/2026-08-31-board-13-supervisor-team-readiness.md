# Board 13 Report: Supervisor, Team Readiness and Start Approval

Date: 2026-08-31

Status: accepted and complete for local private incubation

## Objective

Implement the frozen Supervisor scope without changing existing Adapter,
outbound-context, worktree, repair, evaluation, backup or release authority.

The accepted scope is recorded in
`docs/reports/2026-08-31-board-13-supervisor-team-readiness-plan.md`.

## Delivered

`SupervisorService` is an independent SQLite-backed control plane. It binds the
required Manager, Worker and Reviewer roles to registered Agent and Model
identities. Every binding records one launch mode and one declared transport:
`spawn`, `attach`, `attach_or_spawn`, `remote`, `manual`; and `cli`, `acp`,
`a2a`, `mcp`, `http`, `manual`.

The local team wizard imports exactly these three bindings. Readiness reports
evaluate process, login, Model, permission, version and connection. A missing
check, malformed check or deliberately manual check becomes
`user_confirmation_required`, never ready by inference. A failed check contains
a role-specific repair suggestion.

After all required roles have a current ready report, the Supervisor creates a
canonical immutable team snapshot and SHA-256 digest. It writes a local
Manager-platform `team_ready` event, then creates a second exact SHA-256 scope
for `task_start_requested`.

Human approval requires the displayed scope digest. Its consumption is separate
and revalidates the current team. Binding changes immediately stale pending and
approved requests; new readiness evidence changes the snapshot payload and
therefore also prevents replay. A consumed approval emits only
`task_start_authorized` to the SQLite-backed local fake Manager platform.

## Local-only experiment

The default Supervisor inspector reads synthetic check data supplied to the
local wizard. It cannot construct an Adapter, invoke a model, spawn a real
process, connect to a service or make a network request. Tests inject local
fake CLI, ACP, A2A, MCP and HTTP observation profiles to verify all supervisor
transitions.

No real external Agent, Provider, CLI, ACP, A2A, MCP or HTTP endpoint was used.
No Manager task execution, workspace action, Git action or model call is
performed by the Supervisor start authorization.

## Verification

Seven focused Board 13 tests cover:

- complete ready team, local Manager notification and exact start consumption;
- `user_confirmation_required` blocking a snapshot until explicit confirmation;
- failed Agent checks with remediation;
- configuration drift staling an approved request;
- Model mismatch rejection;
- all launch modes and first-stage transport labels;
- CLI wizard and static local checks without Adapter invocation.

The full offline suite, Python compilation, current-tree review and
reachable-history privacy scan are completion gates for the local commit.

## Privacy review

Supervisor bindings, check reports, confirmations, snapshots, approvals and
Manager-platform events are local runtime SQLite state. They may contain local
Agent labels, version strings and diagnostic observations, so none is copied to
tracked configuration or public reports. Check details pass through the
existing storage sanitizer; operator notes are bounded.

`PRIV-016` records this local-runtime evidence boundary. The Board introduces
no credential field, no endpoint configuration, no non-loopback listener and
no outbound transport.

## Deferred

Real protocol-specific readiness probes, real process control, real Manager
delivery, Web wizard UI, automatic retries and actual task execution remain
separate future work requiring a new frozen scope and, where applicable,
precise external-call authorization.
