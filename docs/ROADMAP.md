# Roadmap

Productization work is tracked in `docs/DEVELOPMENT_BOARDS.md`. Every board
produces an implementation, tests, a report and a dedicated commit.

## Productization Board 1: Settings and registry foundation

Status: complete

- Provider, Model and Agent persistence;
- manual, automatic and hybrid role assignment records;
- application settings persistence;
- config seed synchronization;
- user override protection;
- nested sensitive-value redaction;
- CLI settings operations;
- acceptance report.

Report: `docs/reports/2026-08-29-board-1-settings-registry.md`

## Productization Board 2: Artifact provenance

Status: next

- producing Provider, Model and Agent;
- contributors, reviewer and final integrator;
- internal audit metadata;
- compact, detailed and hidden display modes.

## Milestone 0: Offline collaboration loop

Status: complete

- manager-generated task graph;
- deterministic plan validation;
- parallel worker execution;
- SQLite shared state;
- content-addressed Artifacts;
- independent review;
- final synthesis;
- mock, CLI and HTTP Adapter foundations;
- automated tests and offline demo.

## Milestone 1: One real Codex worker

Status: in progress

- [x] resolve and launch the npm-installed Codex CLI from Python;
- [x] add a no-invocation Adapter doctor check;
- [x] parse `codex exec --json` JSONL output;
- [x] capture thread, usage, event, timing and process metadata;
- [x] add local regression fixtures and tests;
- [x] document Windows launch behavior;
- [ ] obtain explicit authorization to send private repository context;
- [ ] run one read-only Codex architect through `codex exec`;
- [ ] verify Artifact, review, synthesis and database evidence;
- [ ] keep all other roles on mocks during the pilot.

## Milestone 2: Persistent sessions and a second model family

- implement `CodexAppServerAdapter`;
- add request IDs, event streaming, cancellation and thread persistence;
- select one second real provider or CLI;
- add capability-based routing;
- introduce context-size limits and summarization;
- compare declared capability with observed task performance.

## Milestone 3: Real coding projects

- create one Git worktree per writing agent;
- define read, write, test and merge permissions;
- collect diffs, test output and evidence bundles;
- add writer-reviewer repair loops;
- require human approval before merge or destructive action;
- add failure recovery and resumable checkpoints.

## Milestone 4: Interoperability

- expose agent cards and task endpoints through A2A;
- add an MCP tool broker;
- support remote agent nodes;
- sign or authenticate messages;
- add Artifact size, media-type and retention policies.

## Milestone 5: Product interface

- local web control console;
- live task graph and model status;
- message and Artifact browser;
- approvals and permission templates;
- token, time and cost budgets;
- run comparison and evaluation dashboards;
- optional Electron packaging.

## Questions intentionally left open

- Which model should become the long-term manager?
- Should direct worker-to-worker messages be allowed, or always mediated?
- Which decisions require human confirmation?
- Should the first UI be browser-based or Electron?
- Which A2A version should be targeted when interoperability work begins?
- How should model quality be measured independently of self-reported confidence?
