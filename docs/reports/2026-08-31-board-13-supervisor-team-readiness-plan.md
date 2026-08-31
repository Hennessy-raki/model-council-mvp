# Board 13 Plan: Supervisor, Team Readiness and Start Approval

Date: 2026-08-31

Status: acceptance scope frozen before implementation

## Goal

Add one independent local Model Council Supervisor that configures a required
Manager, Worker and Reviewer team, records readiness evidence and gates a
synthetic Manager-platform start request behind exact human approval.

## Frozen scope

The Supervisor persists three required role bindings:

1. Manager;
2. Worker;
3. Reviewer.

Each binding includes an existing local Agent and Model identity, one launch
mode (`spawn`, `attach`, `attach_or_spawn`, `remote` or `manual`), one declared
first-stage transport (`cli`, `acp`, `a2a`, `mcp`, `http` or `manual`) and a
local synthetic readiness-check profile.

The Supervisor evaluates process, login, selected Model, permission, version
and connection. Every check is one of:

- `passed`;
- `failed`;
- `not_applicable`;
- `user_confirmation_required`.

Missing or non-machine-verifiable evidence never becomes a passing result.
Instead it requires a deliberate local user confirmation tied to the current
binding. Failed and confirmation-required checks show an Agent-specific
remediation suggestion.

Only a current ready report for all three required roles can create an
immutable team snapshot. The snapshot has a canonical SHA-256 digest.

## Start gate

The Supervisor creates a local Manager-platform `team_ready` event when it
creates a snapshot. It can then queue a `task_start_requested` event carrying
an exact scope SHA-256. A user must provide that exact digest to approve the
request. Approval and consumption are separate operations.

Any binding change immediately marks pending or approved start requests
`stale`. Fresh readiness evidence also changes the snapshot payload, so a
request cannot be reused after evidence drift. Consuming an approved request
only emits a `task_start_authorized` event to the first-stage local fake
Manager platform.

## Local experiment boundary

Board 13 uses injected local fake CLI, ACP, A2A, MCP and HTTP observations plus
synthetic Model, login, permission, version and connection data. The production
default is a static local inspector; it does not construct an Adapter, spawn a
real process, open a socket, make an HTTP request or invoke a model.

## Excluded

- real process launch, login verification, model discovery or endpoint probing;
- any real CLI, ACP, A2A, MCP, HTTP or Provider call;
- model invocation, task execution, workspace permissions, Git action or Web
  product-surface expansion;
- credentials, runtime database rows, Manager events, reports from private
  projects or fake-service responses in Git;
- GitHub push, tag or release creation.

## Acceptance criteria

- all five launch modes and all six first-stage transport labels validate;
- Manager, Worker and Reviewer Agent+Model bindings are checked separately;
- missing machine evidence is `user_confirmation_required`;
- failed checks include per-Agent remediation;
- ready roles create a persisted SHA-256-bound team snapshot;
- a local Manager-platform receives `team_ready` and exact start-request
  events;
- exact user confirmation is required before one synthetic start authorization;
- configuration or readiness drift makes approval stale;
- focused and complete offline tests plus current-tree and reachable-history
  privacy review pass.
