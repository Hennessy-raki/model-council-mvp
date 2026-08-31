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

## Productization Board 7: Persistent and remote interoperability

Status: complete

- persistent Codex App Server Thread and Turn Adapter;
- A2A v1.0 remote Agent Adapter and Agent Card observations;
- MCP 2025-11-25 stdio and Streamable HTTP tool broker;
- durable endpoint, session, event and approval evidence;
- HTTPS and environment-only authentication boundaries;
- explicit invocation gates and single-use MCP approvals;
- no live external-service verification claim.

Report:
`docs/reports/2026-08-30-board-7-persistent-remote-interoperability.md`

## Productization Board 8: Controlled live-model pilot and outbound context approval

Status: complete

- require local preview and one-time approval for the exact App Server prompt;
- bind approval to endpoint, SHA-256 and UTF-8 byte count;
- keep only one read-only Codex architect external;
- preserve mock manager and reviewer;
- reject Artifacts, repository context, private-derived details and excluded
  credential/path patterns during the initial synthetic pilot;
- retain local audit evidence while avoiding prompt duplication in protocol
  events.
- bind approval to App Server `cwd`, model, sandbox and approval policy;
- reject personal home-directory paths before process startup;
- keep repository-context, A2A and MCP live work behind separate approvals.

Plan: `docs/reports/2026-08-30-board-8-controlled-live-pilot-plan.md`

Report: `docs/reports/2026-08-30-board-8-controlled-live-pilot.md`

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

Status: complete for the synthetic read-only pilot

- [x] resolve and launch the npm-installed Codex CLI from Python;
- [x] add a no-invocation Adapter doctor check;
- [x] parse `codex exec --json` JSONL output;
- [x] capture thread, usage, event, timing and process metadata;
- [x] add local regression fixtures and tests;
- [x] document Windows launch behavior;
- [x] implement exact outbound-context preview and single-use approval for the
  App Server pilot;
- [x] obtain explicit authorization for one displayed synthetic prompt;
- [x] run one read-only Codex architect through the App Server;
- [x] verify Artifact, review, synthesis and database evidence from that
  authorized live run;
- [x] keep all other roles on mocks during the pilot.
- [x] identify and correct the unapproved App Server `cwd` disclosure gap;
- [x] accept deterministic pre-start privacy enforcement with local automated
  evidence; an additional live call is optional and not a Board 9 blocker.

## Productization Board 9: Isolated Git worktrees and permissions

Status: complete

- one isolated Git worktree per writing Agent;
- explicit read, write, test and merge permission states;
- diff, test and evidence collection;
- human approval before merge or destructive action;
- resumable local state without introducing Board 10 repair loops.

Plan: `docs/reports/2026-08-30-board-9-isolated-git-worktrees-plan.md`

Report: `docs/reports/2026-08-30-board-9-isolated-git-worktrees.md`

## Productization Board 10: Bounded reviewer-writer repair and recovery

Status: complete

- define a bounded reviewer-writer repair loop;
- bind every iteration to a worktree checkpoint and evidence bundle;
- limit retries, elapsed time, token/cost budget and changed-file scope;
- recover cleanly from Adapter, test, approval and merge failures;
- preserve human approval before merge or destructive cleanup;
- do not add a second real Agent family or Board 12 product UI scope.

Plan: `docs/reports/2026-08-30-board-10-bounded-repair-recovery-plan.md`

Report: `docs/reports/2026-08-30-board-10-bounded-repair-recovery.md`

## Productization Board 11: Second real Agent family and objective evaluation

Status: complete

- selected DeepSeek Responses as the sole additional Agent family;
- froze the exact endpoint, model, credential reference, synthetic prompt,
  context/response limits and one-time invocation gate;
- compare declared objective-evaluation capability with deterministic token,
  hash, byte, duration and usage evidence;
- keep Manager/Reviewer topology changes controlled and independently audited;
- preserve Board 8-10 invocation, worktree, repair and merge gates;
- do not add Board 12 product UI scope.

Plan: `docs/reports/2026-08-30-board-11-second-agent-evaluation-plan.md`

Report:
`docs/reports/2026-08-30-board-11-second-agent-evaluation.md`

## Productization Board 12: Product interface and release preparation

Status: complete

- productized the loopback-only interface and unified approval center;
- added workspace, repair and objective-evaluation evidence views;
- added deterministic run summaries and pairwise comparison;
- added database-first backup plus exact approved restore with safety backup;
- completed privacy/security release review and public documentation;
- prepared `0.2.0rc1` without weakening existing approval gates.

Plan: `docs/reports/2026-08-31-board-12-product-release-plan.md`

Report: `docs/reports/2026-08-31-board-12-product-release.md`

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
