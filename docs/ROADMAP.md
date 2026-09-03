# Roadmap

Productization work is tracked in `docs/DEVELOPMENT_BOARDS.md`. Every board
produces an implementation, tests, a report and a dedicated commit.

The product goal and user lifecycle are canonical in
`docs/PROJECT_GOAL.md`. Roadmap items are implementation means and may not
silently redefine that goal.

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

## Productization Board 13: Supervisor, team readiness and start approval

Status: complete for local private incubation

- configure persistent Manager, Worker and Reviewer Agent+Model bindings;
- support `spawn`, `attach`, `attach_or_spawn`, `remote` and `manual` modes;
- record synthetic local process, login, Model, permission, version and
  connection evidence;
- require `user_confirmation_required` instead of inferring readiness where
  machine evidence is unavailable;
- create SHA-256-bound team snapshots and one-time start approvals;
- stale start approval after configuration or readiness drift;
- send only local fake Manager-platform readiness and start events;
- retain a no-Adapter, no-network, no-task-execution boundary.

Plan: `docs/reports/2026-08-31-board-13-supervisor-team-readiness-plan.md`

Report: `docs/reports/2026-08-31-board-13-supervisor-team-readiness.md`

## Productization Board 14: Controlled local multi-Agent experiments

Status: complete for one local-private controlled synthetic Manager execution

- complete Board 14.0 with a fake Manager and two fake Workers;
- prepare Board 14.1 with a disabled Codex Manager candidate;
- verify the Codex App Server protocol only against a local fixture, and stop
  the candidate on every server-side approval request;
- require a second SHA-256-bound approval before one controlled App Server
  startup and turn, then verify that path only with local fixtures;
- accept only complete provider-reported usage from supported App Server
  locations, while failing closed when usage is unavailable;
- bind the executor and JSON-lines transport source hashes into every new
  one-turn start approval and stale it if either source changes;
- record privacy-safe local failure classification for unavailable, incomplete
  or over-limit usage while retaining no raw protocol or response content;
- validate the exact two-Worker Manager plan and retain only privacy-safe
  output-contract failure classification, hash and byte count;
- generate the exact v2 two-Worker JSON contract prompt from the bound Worker
  identities and reject generic or drifted prompts before approval;
- bind any future Provider input/output token headroom as explicit hard limits
  rather than inferring it from prompt bytes or allowing unbounded overhead;
- require a declared price schedule and worst-case cost feasibility before a
  high-input token envelope can enter a future approval scope;
- bind the current team, identities, exact synthetic prompt, transport,
  permissions, budgets and stop rules to one SHA-256;
- retain zero files, zero Artifacts, read-only, no tools, no writes, no Git,
  one future call, no retry and sequential execution;
- complete one separately authorized local-private Manager turn only after the
  exact experiment and second start-approval scopes are approved and
  revalidated;
- keep the public candidate `invoke_enabled: false`; do not repeat the
  terminal experiment or expand to repository context, tools, writes, Git,
  parallelism, another provider or another call without a new board scope;
- defer Reasonix, ZCode, real parallelism and the three-Agent experiment.

Plan:
`docs/reports/2026-08-31-board-14-local-multi-agent-experiment-plan.md`

Preparation report:
`docs/reports/2026-08-31-board-14-local-multi-agent-experiment-preparation.md`

Board 14.2 plan and report:
`docs/reports/2026-08-31-board-14-2-offline-app-server-execution-plan.md`
and `docs/reports/2026-08-31-board-14-2-offline-app-server-execution.md`

Board 14.3 plan and report:
`docs/reports/2026-08-31-board-14-3-controlled-executor-plan.md`
and `docs/reports/2026-08-31-board-14-3-controlled-executor.md`

Board 14.4 plan and report:
`docs/reports/2026-08-31-board-14-4-usage-compatibility-repair-plan.md`
and `docs/reports/2026-08-31-board-14-4-usage-compatibility-repair.md`

Board 14.5 plan and report:
`docs/reports/2026-08-31-board-14-5-executor-integrity-plan.md`
and `docs/reports/2026-08-31-board-14-5-executor-integrity.md`

Board 14.6 plan and report:
`docs/reports/2026-08-31-board-14-6-usage-failure-diagnostics-plan.md`
and `docs/reports/2026-08-31-board-14-6-usage-failure-diagnostics.md`

Board 14.7 plan and report:
`docs/reports/2026-08-31-board-14-7-output-contract-diagnostics-plan.md`
and `docs/reports/2026-08-31-board-14-7-output-contract-diagnostics.md`

Board 14.8 plan and report:
`docs/reports/2026-08-31-board-14-8-contract-bound-synthetic-prompt-plan.md`
and `docs/reports/2026-08-31-board-14-8-contract-bound-synthetic-prompt.md`

Board 14.9 plan and report:
`docs/reports/2026-09-01-board-14-9-provider-input-budget-plan.md`
and `docs/reports/2026-09-01-board-14-9-provider-input-budget.md`

Board 14.10 plan and report:
`docs/reports/2026-09-01-board-14-10-cost-feasibility-plan.md`
and `docs/reports/2026-09-01-board-14-10-cost-feasibility.md`

Board 14.11 closeout report:
`docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md`

## Productization Board 15: Project rebaseline and documentation consistency

Status: complete

- added a public-safe project-status page;
- reconciled Board 13/14 terminal state across the authoritative entry
  documents;
- reclassified Milestones 2 through 5 into delivered core controls and
  genuinely deferred expansion;
- added deterministic offline regression coverage for Board 14 terminal
  wording;
- did not change any external-call, workspace, runtime or publishing boundary.

Plan: `docs/reports/2026-09-01-board-15-project-rebaseline-plan.md`

Report: `docs/reports/2026-09-01-board-15-project-rebaseline.md`

## Productization Board 17A: Team lifecycle and project-run authorization

Status: complete for the local offline vertical slice

- bind the exact project goal to the current ready Supervisor team snapshot;
- require a one-time project-run approval on the normal CLI `run` entry point;
- reject wrong-goal, stale-team and replayed approvals before Adapter invocation;
- persist approval provenance on the run record;
- project Supervisor state and approvals through the loopback product surface;
- preserve separate synthetic Manager-platform approvals;
- defer Artifact retention/purge and all external transport work.

Plan: `docs/reports/2026-09-01-board-17a-team-lifecycle-plan.md`

Report: `docs/reports/2026-09-01-board-17a-team-lifecycle.md`

## Productization Board 17B: Deterministic local Agent lifecycle verification

Status: complete for the local fixture slice

- model deterministic `start`, `connect`, `attach`, `detach` and `stop`
  transitions per bound role;
- persist bounded lifecycle sessions, transition events and evidence digests in
  ignored local SQLite state;
- record process, login, actual-Model, permission, version, protocol and
  connectivity evidence with remediation and confirmation-required states;
- bind lifecycle evidence into Supervisor snapshots and project-run approval
  stale-on-drift validation;
- expose the same service state through CLI and loopback Web projections;
- keep all Provider, network, repository, worktree, Git and Artifact-purge
  behavior deferred.

Plan:
`docs/reports/2026-09-01-board-17b-agent-lifecycle-verification-plan.md`

Report:
`docs/reports/2026-09-01-board-17b-agent-lifecycle-verification.md`

## Productization Board 18: Local fake subprocess Agent lifecycle

Status: complete for the local subprocess fixture slice

- execute one explicit local fixture command array with `shell=False`;
- record bounded process markers, exit codes and lifecycle evidence;
- preserve Board 17B snapshot and project-run stale-on-drift controls;
- reject duplicate starts and cleanly stop/restart the fixture;
- keep real Agent, Provider, network, repository and Artifact-purge work
  separately scoped.

Plan:
`docs/reports/2026-09-01-board-18-local-subprocess-lifecycle-plan.md`

Report:
`docs/reports/2026-09-01-board-18-local-subprocess-lifecycle.md`

## Productization Board 19: Project-run approval hardening

Status: complete for local offline control

- production `Orchestrator.run()` requires `start_approval_id`;
- missing approval fails closed before run creation or Adapter invocation;
- existing exact-goal, snapshot, lifecycle-drift and single-use checks remain;
- only a private explicit offline test mode bypasses approval for pipeline tests.

Plan:
`docs/reports/2026-09-03-board-19-project-run-approval-hardening-plan.md`

Report:
`docs/reports/2026-09-03-board-19-project-run-approval-hardening.md`

## Productization Board 20: CLI local Agent lifecycle sequence

Status: complete for the local subprocess fixture slice

- provide a built-in local fake Agent process;
- run a bounded `supervisor lifecycle-sequence` in one controlled CLI process;
- reuse explicit `shell=False` process control and bounded lifecycle evidence;
- stop the fixture before the command exits;
- keep arbitrary command execution, cross-process PID control and all external
  Agent/Provider behavior out of scope.

Plan:
`docs/reports/2026-09-03-board-20-cli-local-lifecycle-plan.md`

Report:
`docs/reports/2026-09-03-board-20-cli-local-lifecycle.md`

## Productization Board 21: Offline Agent qualification preflight

Status: complete for the pure local validation slice

- validate a future Agent qualification declaration with no runtime or
  external side effects;
- require explicit identity, lifecycle checks, read-only permissions, context
  exclusions, bounded budgets, stop rules, approvals and evidence policy;
- produce a deterministic scope digest and bounded blocker diagnostics;
- keep real Agent, Provider, network, repository, worktree, Git and Artifact
  behavior deferred.

Plan:
`docs/reports/2026-09-03-board-21-offline-agent-qualification-preflight-plan.md`

Report:
`docs/reports/2026-09-03-board-21-offline-agent-qualification-preflight.md`

## Productization Board 22: Qualification preflight binding

Status: complete for the local offline Supervisor slice

- bind sanitized qualification preflight results to non-mock roles;
- include qualification provenance in snapshots and project-run approvals;
- fail closed and stale approvals on qualification or role drift;
- keep real Agent and all external execution separately scoped.

Plan:
`docs/reports/2026-09-03-board-22-qualification-binding-plan.md`

Report:
`docs/reports/2026-09-03-board-22-qualification-binding.md`

## Milestone 2: Persistent sessions and additional model families

Status: core controls complete; further qualification deferred

- [x] Codex App Server sessions, request IDs, event handling and thread
  persistence;
- [x] one additional Responses-family integration with objective synthetic
  evaluation and a single-use outbound approval;
- [x] capability-based routing and explicit context/byte limits;
- [ ] qualify another model family or any non-synthetic scope only under a new
  explicit authorization;
- [ ] add generic context summarization only with a separately reviewed
  retention and disclosure policy.

## Milestone 3: Real coding projects

Status: offline control plane complete; real writing-Agent validation deferred

- [x] one isolated Git worktree per writing Agent;
- [x] explicit read, write, test and merge permissions;
- [x] diffs, test evidence, repair loops, recovery and resumable checkpoints;
- [x] human approval before merge or destructive action;
- [ ] authorize a real writing/reviewing Agent only through a new workspace and
  outbound-context scope.

## Milestone 4: Interoperability

Status: local protocol clients complete; remote validation and policy expansion
deferred

- [x] A2A agent-card/task controls and MCP tool-broker approvals;
- [x] environment-only credentials, non-loopback HTTPS enforcement and
  persisted endpoint identity/session evidence;
- [ ] validate a live third-party A2A or MCP endpoint under a separate scope;
- [ ] define remote-node authentication/signing and Artifact retention policy.

## Milestone 5: Product interface

Status: local web product surface complete; packaging and operator expansion
deferred

- [x] loopback control console, approval/evidence views and message/Artifact
  browsing;
- [x] token, time and cost budgets, run comparison, evaluation views and
  privacy-safe backup/restore;
- [ ] optional Electron packaging and broader operator workflows.

## Questions intentionally left open

- Which model should become the long-term manager?
- Should direct worker-to-worker messages be allowed, or always mediated?
- Which decisions require human confirmation?
- Should the first UI be browser-based or Electron?
- Which A2A version should be targeted when interoperability work begins?
- How should model quality be measured independently of self-reported confidence?
