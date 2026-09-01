# Project Goal Rebaseline Report

Date: 2026-09-01

Status: accepted as the canonical goal statement

## Why this report was needed

The project was developed across several conversations and many independently
reviewed boards. That process delivered substantial control-plane capability, but
the increasing number of boards made it possible to mistake a local technical
milestone for the reason the project exists.

This report restores one stable reference point before further development.

## Original idea recovered

The user wants to choose, or let the computer recommend, which Agent＋Model is
the manager and which Agent＋Model instances are workers. The computer should
open or connect the required Agents, verify that every configured Model is
actually the one in use, detect login/configuration/permission/connectivity
problems, identify the exact failing Agent or Model, and notify the user when
the team is ready.

The system must then wait for explicit user permission before starting the
project. After authorization, the manager coordinates heterogeneous models,
passes structured messages and files, delegates specialized work, reviews
results and produces a source-aware final delivery. Usage, cost, balance and
failure evidence should remain visible and controllable.

## Canonical decision

`docs/PROJECT_GOAL.md` is now the highest-level product scope document.

It defines:

- the project初心 and user problem;
- the desired startup/readiness/authorization/work/delivery lifecycle;
- Provider, Model, Agent and Role boundaries;
- configuration, discovery, communication, provenance, billing and recovery
  goals;
- non-negotiable privacy, permission and user-control principles;
- user-facing success criteria;
- the board-level anti-drift checklist.

The document deliberately separates the final product goal from the current
implementation state. It does not claim that every part is already complete.

## Relationship to current implementation

The existing repository contains strong foundations for the goal:

- persistent Provider/Model/Agent and Role records;
- deterministic routing and budget gates;
- readiness, approval and privacy controls;
- local protocol clients and isolated workspaces;
- provenance, usage, review, recovery and local product views.

The remaining work must be judged by whether it closes the user lifecycle
described in the goal document. Adding another protocol or model family without
improving that lifecycle is not sufficient justification for a new board.

## Drift controls added

- README now links to the canonical goal;
- AGENTS.md requires reading and using it as the scope guard;
- DEVELOPMENT_BOARDS.md requires every board report to state its contribution;
- PROJECT_STATUS.md states its implementation status is subordinate to the goal;
- ROADMAP.md identifies roadmap items as implementation means;
- START_HERE_NEXT_SESSION.md requires the goal document before new work.

## Acceptance evidence

- tracked documentation parses as UTF-8;
- no runtime, credential, private prompt or provider response is included;
- all 130 offline tests pass after adding the canonical-goal regression test;
- Python compilation and the current-tree/reachable-history privacy scan pass;
- the report contains no local identifiers or private machine paths.

## Next decision

Before starting the next implementation board, explicitly choose which part of
the canonical user lifecycle is being advanced. The current project direction
should prioritize the user-visible team setup, readiness and authorization flow
over unbounded expansion of model or protocol coverage.
