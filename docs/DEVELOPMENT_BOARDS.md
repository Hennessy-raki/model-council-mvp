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

The canonical purpose, user lifecycle and success criteria are in
`docs/PROJECT_GOAL.md`. When a new idea conflicts with that document, pause
implementation and update the goal only after an explicit product decision.
Board reports must include a short "Contribution to PROJECT_GOAL" section.

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

Status: complete

- added the product approval center and repair/workspace evidence views;
- added deterministic run comparison and objective-evaluation views;
- added privacy-safe backup/restore with exact approval and safety backup;
- completed privacy, security and public-release verification;
- prepared release documentation and reviewable candidate `0.2.0rc1`.

Plan: `docs/reports/2026-08-31-board-12-product-release-plan.md`

Report: `docs/reports/2026-08-31-board-12-product-release.md`

### Board 13: Supervisor, team readiness and start approval

Status: complete for local private incubation

- independent local Supervisor with Manager, Worker and Reviewer bindings;
- `spawn`, `attach`, `attach_or_spawn`, `remote` and `manual` launch modes;
- local fake CLI, ACP, A2A, MCP and HTTP readiness-observation profiles;
- process, login, Model, permission, version and connection checks;
- explicit `user_confirmation_required` state and per-Agent remediation;
- immutable SHA-256-bound team snapshots and start approvals;
- stale approval on binding or readiness evidence drift;
- local fake Manager-platform `team_ready`, start-request and start-authorized
  audit events;
- no real external invocation, task execution, Git publishing, tag or release.

Plan: `docs/reports/2026-08-31-board-13-supervisor-team-readiness-plan.md`

Report: `docs/reports/2026-08-31-board-13-supervisor-team-readiness.md`

### Board 14: Controlled local multi-Agent experiments

Status: complete for one local-private controlled synthetic Manager execution

- Board 14.0 offline experiment harness and fake Manager/two-Worker simulation
  are implemented;
- Board 14.1 Codex Manager candidate preparation is implemented;
- Board 14.2 verifies the local fake App Server protocol and makes any
  server-side approval request terminal for the public Codex candidate;
- Board 14.3 adds a two-stage, one-time start authorization and verifies the
  controlled executor only against local fake App Server fixtures;
- Board 14.4 repairs usage-shape compatibility while preserving fail-closed
  limits and verifies it only with local fixtures;
- Board 14.5 binds executor and transport source integrity into every new
  start approval and stales it on code drift;
- Board 14.6 records privacy-safe local diagnostics that distinguish
  unavailable, incomplete and over-limit usage without retaining raw protocol
  or response content;
- Board 14.7 validates the exact two-Worker Manager plan and records
  privacy-safe output-contract diagnostics without retaining raw output;
- Board 14.8 binds the complete v2 output contract into the exact synthetic
  prompt and scope, rejecting generic prompts and extra JSON fields;
- Board 14.9 adds separately bounded Provider input/output token limits and
  privacy-safe component-limit diagnostics without changing the default cap;
- Board 14.10 requires an explicit declared price schedule before a high-input
  token envelope may be prepared under a cost cap;
- exact team, identity, prompt, transport, permission, budget and stop-rule
  scope is SHA-256-bound;
- public Codex candidate remains `invoke_enabled: false`;
- five separately authorized one-turn synthetic Codex Manager attempts consumed
  their approvals and failed closed without retry; none may be reused;
- a sixth separately authorized one-turn synthetic Manager experiment completed
  once after the exact experiment and start-approval ladder; it is terminal
  and cannot be replayed;
- no Board 14 experiment, approval, prompt, response, JSONL stream, usage
  record or runtime identifier is public or reusable.

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

### Board 15: Project rebaseline and documentation consistency

Status: complete

- establish one public-safe project-status page;
- reconcile authoritative entry documents with Board 13/14 terminal state;
- distinguish delivered control-plane capabilities from deferred expansion;
- add deterministic offline regression coverage for Board 14 status wording;
- do not change any external-call, workspace, runtime or publishing boundary.

Plan:
`docs/reports/2026-09-01-board-15-project-rebaseline-plan.md`

Report:
`docs/reports/2026-09-01-board-15-project-rebaseline.md`

### Board 17A: Team lifecycle and project-run authorization

Status: complete for the local offline vertical slice

- bind the exact project goal to the current ready Supervisor team snapshot;
- require a one-time project-run approval on the normal CLI `run` entry point;
- reject wrong-goal, stale-team and replayed approvals before Adapter invocation;
- persist approval provenance on the run record;
- expose Supervisor state and approvals through the loopback product surface;
- keep synthetic Manager-platform authorization separate;
- do not add Artifact retention/purge, Provider calls, network transports,
  worktrees or Git publishing.

Plan: `docs/reports/2026-09-01-board-17a-team-lifecycle-plan.md`

Report: `docs/reports/2026-09-01-board-17a-team-lifecycle.md`

### Board 17B: Deterministic local Agent lifecycle verification

Status: complete for the local fixture slice

- deterministic local start/connect/attach/detach/stop transitions;
- bounded lifecycle session and transition-event persistence;
- process, login, actual-Model, permission, version, protocol and connectivity
  evidence with remediation and explicit confirmation handling;
- lifecycle evidence bound into team snapshots and project-run approvals;
- shared Supervisor service consumed by CLI and loopback Web projections;
- no Provider, network, repository, worktree, Git or Artifact-purge behavior.

Plan:
`docs/reports/2026-09-01-board-17b-agent-lifecycle-verification-plan.md`

Report:
`docs/reports/2026-09-01-board-17b-agent-lifecycle-verification.md`

### Board 18: Local fake subprocess Agent lifecycle

Status: complete for the local subprocess fixture slice

- explicit command-array subprocess control with `shell=False`;
- bounded process marker, exit and transition evidence;
- duplicate-start failure and clean stop/restart handling;
- no Provider, network, repository, worktree, Git or Artifact-purge authority.

Plan:
`docs/reports/2026-09-01-board-18-local-subprocess-lifecycle-plan.md`

Report:
`docs/reports/2026-09-01-board-18-local-subprocess-lifecycle.md`

### Board 19: Project-run approval hardening

Status: complete for local offline control

- production `Orchestrator.run()` requires `start_approval_id`;
- missing approval fails closed before run creation or Adapter invocation;
- existing exact-goal, snapshot, lifecycle-drift and single-use checks remain;
- only a private explicit offline test mode bypasses approval for pipeline tests;
- no Provider, model, network, repository, worktree, Git or Artifact authority.

Plan:
`docs/reports/2026-09-03-board-19-project-run-approval-hardening-plan.md`

Report:
`docs/reports/2026-09-03-board-19-project-run-approval-hardening.md`

### Board 20: CLI local Agent lifecycle sequence

Status: complete for the local subprocess fixture slice

- built-in local fake Agent process;
- bounded single-process `lifecycle-sequence` CLI command;
- safe lifecycle evidence and fixture stop before exit;
- no arbitrary shell, cross-process PID, Provider, network or repository
  authority.

Plan:
`docs/reports/2026-09-03-board-20-cli-local-lifecycle-plan.md`

Report:
`docs/reports/2026-09-03-board-20-cli-local-lifecycle.md`

### Board 21: Offline Agent qualification preflight

Status: complete for the pure local validation slice

- validate a future Agent/Model/Provider qualification declaration without
  loading project configuration or runtime state;
- require canonical lifecycle checks, read-only permissions, explicit private
  context exclusions, bounded token/cost/time limits and a one-attempt stop
  rule;
- require a separate approval ladder and runtime-only evidence policy;
- reject credentials, personal paths, protected runtime references, unknown
  fields and execution-authority claims;
- return a deterministic scope digest and bounded blocker codes;
- do not start a process or invoke a Provider, model, network, repository,
  worktree or Git operation.

Plan:
`docs/reports/2026-09-03-board-21-offline-agent-qualification-preflight-plan.md`

Report:
`docs/reports/2026-09-03-board-21-offline-agent-qualification-preflight.md`

### Board 22: Qualification preflight binding

Status: complete for the local offline Supervisor slice

- require a current matching qualification preflight for non-mock Agent roles;
- persist only sanitized preflight scope metadata and SHA-256 in ignored
  runtime state;
- bind qualification provenance to team snapshots and project-run approvals;
- stale preflight and downstream approvals on role or scope drift;
- expose binding through CLI and read-only Web state;
- keep all process, Provider, model, network, repository, worktree and Git
  behavior out of scope.

Plan:
`docs/reports/2026-09-03-board-22-qualification-binding-plan.md`

Report:
`docs/reports/2026-09-03-board-22-qualification-binding.md`

### Board 23: Qualification provenance integrity and revalidation

Status: complete for the local offline Supervisor slice

- revalidate stored qualification scope digests;
- verify current Agent/Model/Provider registry identity and enabled state;
- fail closed on tampering or identity drift before readiness or snapshot;
- expose bounded integrity status through CLI and Web;
- keep all external execution and private project context out of scope.

Plan:
`docs/reports/2026-09-09-board-23-qualification-integrity-plan.md`

Report:
`docs/reports/2026-09-09-board-23-qualification-integrity.md`

### Board 24: Real-Agent qualification authorization package

Status: complete for the offline preparation scope frozen on 2026-09-09

- define a deterministic, privacy-safe package for one future real-Agent
  qualification request;
- distinguish declared registry identity, observed evidence and user
  confirmation;
- bind command, working-directory category, read-only permissions, synthetic
  context, limits and stale-on-drift provenance;
- keep actual Agent execution and every external call separately authorized.

Plan:
`docs/reports/2026-09-09-board-24-real-agent-qualification-authorization-plan.md`

Freeze record:
`docs/reports/2026-09-09-board-24-real-agent-qualification-authorization-freeze.md`

Implementation report:
`docs/reports/2026-10-14-board-24-real-agent-qualification-authorization-implementation.md`

Implemented on 2026-10-14: `model_council/authorization.py` plus the read-only
`authorization build` and `authorization verify` CLI commands. The working
directory is referenced by category and environment-variable name rather than by
value, missing evidence yields `user_confirmation_required` by construction, and
the fact state is bound into `package_sha256` so a changed observation makes a
prior approval stale. No Agent is started, no endpoint is contacted, and no
execution authority is created.

### Board 25: Foundation audit and recomputed trust surface

Status: complete for the local offline audit slice

- independently audit the documentation, report evidence chain, production entry
  points, privacy gate and unpublished commits rather than inheriting earlier
  acceptance claims;
- recompute the local disclosure surface against the owner's restated
  requirement that no information about this machine be recoverable by another
  party;
- inspect ignored local runtime state, which the privacy gate previously skipped
  entirely;
- remove machine-identifying values from newly written persistent Artifact
  records while keeping previously written databases working;
- remove a history-scan exemption that could only ever hide a future path;
- record the widened threat model in `docs/PRIVACY_ISSUES.md`.

Report:
`docs/reports/2026-10-14-board-25-foundation-audit-and-trust-surface.md`

Board 25 adds no external call, process start, Provider, network, repository,
worktree, Git-publish or Artifact-purge authority. Board 24's frozen scope is
unchanged, and its implementation still requires a separate new board number.

### Board 26: Authorization package binding and read-only projection

Status: complete for the local offline binding slice

- persist one bound authorization package per role together with its facts,
  digests, identity and captured team snapshot;
- re-derive the package digest, the bound facts and the registry identity on
  every read, so a tampered package is `invalid` and a contradicted one is
  `stale` rather than silently acceptable;
- report whether the captured team snapshot is still the latest one;
- project the result read-only through the CLI and the loopback product surface;
- refuse to bind a package that claims execution authority, carries a
  mismatched identity, or whose facts do not reproduce its digest;
- fix the Board 24 fact-shape mismatch so a freshly stored package does not
  report stale on first read.

Report:
`docs/reports/2026-10-14-board-26-authorization-package-binding-and-projection.md`

Board 26 creates no start approval, starts no process, contacts no endpoint and
adds no execution authority. Binding a package is a review record, not a
permission.

### Board 27: Version preference engine and configuration-driven discovery

Status: complete for the local offline slice

- compare installed Agent versions deterministically, with the operator's
  stated rule applied at two levels: a stable release outranks a pre-release of
  the same number when comparing two versions, and any stable release is
  preferred over any pre-release when ranking candidates;
- keep that rule a settable parameter, and let an explicit user preference
  always override the computed recommendation;
- report `undecidable` rather than guessing when versions have no comparable
  form, and never set `auto_switch`, because a recommendation is evidence for a
  decision the operator still makes;
- replace the hardcoded four-vendor discovery list with a catalogue supplied
  through configuration, so adding a tool never requires editing the module;
- probe each installed form with an argument-array, shell-free, time-limited
  command and record the versions it reports;
- record a GUI-only application for visibility and manual handoff while stating
  that it is not invocable, and never register an Agent profile for it.

Plan and reports: the changes, their verification and the defects found while
building them are recorded in the commits that carry them and in

```text
docs/reports/2026-10-14-board-27-version-preference-and-discovery.md
```

Board 27 starts no process beyond a version query, contacts no endpoint, and
creates no binding.

Note on numbering: Board 27 is the version and discovery board. It is not the
retired Board 24 scope, which was implemented under its own number, and it is
not the deferred transport board 16.

