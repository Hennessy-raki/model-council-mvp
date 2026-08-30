# Roadmap

Productization work is tracked in `docs/DEVELOPMENT_BOARDS.md`. Every board
produces an implementation, tests, a report and a dedicated commit.

The refreshed context and verification baseline before Board 5 is recorded in
`docs/reports/2026-08-29-pre-board-5-session-handoff.md`.

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

Status: complete

- producing Provider, Model and Agent;
- contributors, reviewer and final integrator;
- internal audit metadata;
- compact, detailed and hidden display modes.

Report: `docs/reports/2026-08-29-board-2-artifact-provenance.md`

## Productization Board 3: Startup discovery and setup

Status: complete

- known local Agent command scanning;
- separate executable, authentication, permission and connectivity status;
- Adapter capability-based model discovery;
- opt-in project-neutral connectivity probes;
- manual GUI-only Agent registration;
- persistent discovery observations and protected user records.

Report: `docs/reports/2026-08-29-board-3-startup-discovery.md`

## Productization Board 4: Usage, cost and balance ledger

Status: complete

- immutable normalized records for every Adapter call;
- actual, provider-reported, estimated and unavailable source labels;
- project, run and role totals;
- user-protected warning and hard budget policies;
- conservative hard-limit enforcement when values are unavailable;
- explicit balance snapshots only for supported Provider APIs.

Report: `docs/reports/2026-08-29-board-4-usage-cost-ledger.md`

## Productization Board 5: Routing policy

Status: complete

- manual, automatic and hybrid selection;
- capability, availability, cost and latency constraints;
- user locks and required model separation;
- persisted routing explanations;
- no Web UI or real-model expansion within this board.

Report: `docs/reports/2026-08-29-board-5-routing-policy.md`

## Productization Board 6: Local settings interface

Status: complete

- local web control plane over the stable registry and router;
- Provider, Model, Agent, role and application-setting editing;
- discovery, provenance, ledger, budget and routing explanation views;
- local-only state and explicit approval boundaries;
- no Board 7 remote interoperability within this board.

Report: `docs/reports/2026-08-30-board-6-local-settings-interface.md`

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
- token, time and cost budget configuration and visualization;
- run comparison and evaluation dashboards;
- optional Electron packaging.

## Questions intentionally left open

- Which model should become the long-term manager?
- Should direct worker-to-worker messages be allowed, or always mediated?
- Which decisions require human confirmation?
- Should the first UI be browser-based or Electron?
- Which A2A version should be targeted when interoperability work begins?
- How should model quality be measured independently of self-reported confidence?
