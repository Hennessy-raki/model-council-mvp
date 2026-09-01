# Board 17A Plan: Team Lifecycle and Project-Run Authorization

Date: 2026-09-01

Status: frozen and implemented locally; no external-call authority created

## Contribution to PROJECT_GOAL

This board advances the central user lifecycle from configured team to
explicitly authorized project start. It makes the existing Supervisor snapshot
and approval model usable by the normal CLI project-run entry point, while
keeping the cognition/control separation and local-first boundary intact.

## Business objective

The operator must be able to bind a Manager, Worker and Reviewer team, inspect
current readiness, approve one exact project goal, and know that the run cannot
start after team or goal drift.

## Scope

- add a project-run approval scope bound to the current ready team snapshot and
  exact normalized goal;
- consume that approval once immediately before the orchestrator creates a run;
- record the snapshot, approval and scope digest on the run;
- expose Supervisor state and approvals through the local Web projection;
- preserve the existing local synthetic Supervisor platform approval as a
  separate action.

## Authorization ladder

1. Configure the required role bindings.
2. Run local synthetic readiness checks and resolve failures or confirmations.
3. Create a current team snapshot.
4. Request a project-run approval for the exact goal.
5. Approve the displayed scope SHA-256.
6. Run the CLI with the same goal and approval ID; the service revalidates and
   consumes the approval once before any Adapter invocation.

## Privacy and storage

Project goals and approval scopes remain in the ignored local SQLite runtime.
Tracked files contain only synthetic examples and aggregate documentation.
The board does not read, copy or display runtime Artifact bodies and does not
invoke Providers, App Servers, A2A, MCP or models.

## Threat model

The implementation fails closed for missing approval, wrong goal, wrong action,
consumed approval, team configuration drift, readiness evidence drift and
concurrent approval consumption. It records a local authorization event and
persists the exact scope digest on the run.

## Acceptance criteria

- exact project-run approval binds the goal and current team snapshot;
- wrong goal and stale team state are rejected;
- approval consumption is single-use and race-safe;
- normal CLI `run` requires `--start-approval`;
- authorized runs persist approval provenance;
- Web state and approval center expose Supervisor evidence without adding an
  external action;
- existing offline tests remain green;
- no retention/purge behavior, new Provider, network transport, worktree,
  Git publishing or private-content export is added.
