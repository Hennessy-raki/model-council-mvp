# Development Boards

Model Council is developed in independently reviewable boards. Every completed
board must include:

1. implementation;
2. automated tests;
3. an acceptance report under `docs/reports/`;
4. roadmap and handoff updates;
5. one identifiable Git commit.
6. a full repository privacy scan before public push.

Ideas discovered during a board should be recorded for later prioritization
unless they are required to satisfy the current board's acceptance criteria.

## Board sequence

### Board 1: Settings and registry foundation

Status: complete

- persist Provider, Model and Agent records;
- persist manual, automatic and hybrid role assignments;
- persist application settings;
- synchronize JSON seed configuration without overwriting user choices;
- redact likely credentials before persistence;
- expose settings through CLI commands.

Report: `docs/reports/2026-08-29-board-1-settings-registry.md`

### Board 2: Artifact provenance

Status: complete

- record producing Provider, Model and Agent;
- record contributors, reviewer and final integrator;
- keep provenance internally even when display is disabled;
- add configurable compact, detailed and hidden presentation modes;
- migrate existing Artifact records safely.

Report: `docs/reports/2026-08-29-board-2-artifact-provenance.md`

### Board 3: Startup discovery and setup

Status: complete

- scan known local Agent commands;
- check executable, authentication and permissions separately;
- discover available models through Adapter capabilities;
- run an opt-in, non-project connectivity test;
- support manual registration for GUI-only hosts.

Report: `docs/reports/2026-08-29-board-3-startup-discovery.md`

### Board 4: Usage, cost and balance ledger

Status: complete

- normalize per-call usage;
- distinguish actual, provider-reported, estimated and unavailable values;
- calculate project and role totals;
- add budget warnings and hard limits;
- expose provider balance only when a supported API exists.

Report: `docs/reports/2026-08-29-board-4-usage-cost-ledger.md`

### Board 5: Routing policy

Status: complete

- implement manual, automatic and hybrid role selection;
- add capability, availability, cost and latency constraints;
- allow user locks and required model separation;
- persist routing explanations for audit.

Report: `docs/reports/2026-08-29-board-5-routing-policy.md`

### Board 6: Local settings interface

Status: complete

- build a local web control plane on top of the stable registry;
- edit Providers, Models, Agents, roles and settings;
- show discovery, health and billing capability states;
- expose provenance and budget controls;
- keep all state local by default.

Report: `docs/reports/2026-08-30-board-6-local-settings-interface.md`

### Board 7: Persistent and remote interoperability

Status: complete

- Codex App Server sessions;
- second real model family;
- A2A transport;
- MCP tool broker;
- remote Agent identity and authentication.

The A2A Adapter is the second external Agent-family integration contract. Its
offline implementation is complete; no live third-party endpoint is claimed as
verified.

Report: `docs/reports/2026-08-30-board-7-persistent-remote-interoperability.md`

### Board 8: Controlled live-model pilot and outbound context approval

Status: complete

- one read-only Codex App Server architect role only;
- mock manager and reviewer only;
- exact outbound prompt inventory, byte limits and exclusion rules;
- local preview plus SHA-256-bound, single-use human approval;
- synthetic context only; no Artifacts, repository content or private-derived
  material in the initial pilot;
- local fake-App-Server regression coverage and one functionally successful
  live synthetic run;
- post-pilot correction binds `cwd`, model, sandbox and approval policy and
  blocks personal home paths before process startup;
- no repository-context, A2A or MCP live verification claim.

Plan: `docs/reports/2026-08-30-board-8-controlled-live-pilot-plan.md`

Report: `docs/reports/2026-08-30-board-8-controlled-live-pilot.md`

### Board 9: Isolated Git worktrees and write/test/merge permissions

Status: complete

- create one isolated Git worktree per writing Agent;
- separate read, write, test and merge permissions;
- collect diffs, test output and bounded evidence bundles;
- require explicit human approval before merge or destructive action;
- keep repository privacy scanning and the privacy issue register as release
  gates;
- do not add repair loops, a second real Agent family or product UI scope.

Plan: `docs/reports/2026-08-30-board-9-isolated-git-worktrees-plan.md`

Report: `docs/reports/2026-08-30-board-9-isolated-git-worktrees.md`

### Board 10: Bounded reviewer-writer repair loops and recovery

Status: complete

- freeze repair-loop iteration, time, cost and changed-file limits;
- checkpoint and review every writer iteration;
- recover persisted state after Agent, process, test or approval failure;
- require current evidence and human approval before merge or destructive
  cleanup;
- do not add the Board 11 second real Agent family or Board 12 product UI.

Plan: `docs/reports/2026-08-30-board-10-bounded-repair-recovery-plan.md`

Report: `docs/reports/2026-08-30-board-10-bounded-repair-recovery.md`

### Board 11: Second real Agent family and objective evaluation

Status: complete

- select DeepSeek Responses as the only second Agent family;
- freeze exact prompt/transport disclosure, environment-only credential,
  request/response byte limits and single-use approval before a live call;
- evaluate one fixed synthetic token task with persisted hash/count/assertion
  and usage evidence;
- preserve existing routing, budget, worktree, repair and approval controls;
- do not add Board 12 product UI scope.

Plan: `docs/reports/2026-08-30-board-11-second-agent-evaluation-plan.md`

Report:
`docs/reports/2026-08-30-board-11-second-agent-evaluation.md`

### Board 12: Product interface, backup and release preparation

Status: queued after Board 11; implementation not started

- add the product approval center and repair/workspace views;
- add run comparison and evaluation views;
- add local backup/restore safeguards;
- complete privacy, security and public-release verification;
- prepare release documentation and a reviewable release candidate.
