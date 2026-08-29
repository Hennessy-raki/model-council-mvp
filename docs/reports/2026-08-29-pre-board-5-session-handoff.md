# Pre-Board-5 Session Handoff

Date: 2026-08-29

Status: accepted checkpoint; Board 5 implementation has not started

## Purpose

This checkpoint refreshes the complete project context after Productization
Boards 1 through 4 and freezes the safe starting point for Board 5. It is a
documentation and verification handoff, not a routing implementation.

## Authoritative repository state

- Local repository: the existing `model-council-mvp` checkout supplied by the
  user; do not create a replacement repository for the next session.
- GitHub repository: `Hennessy-raki/model-council-mvp`.
- Visibility: public.
- License: MIT.
- Default branch: `main`.
- Verified pre-handoff implementation commit:
  `7947ef1a6edb88c73b8727d0371eca8343607ad3`.
- The local branch was clean and synchronized with `origin/main` before this
  checkpoint was written.
- The public GitHub API returned the same SHA for remote `main`.
- GitHub Issue #5 was not available during this verification. Board 5 scope is
  therefore governed by `docs/DEVELOPMENT_BOARDS.md`, the architecture
  invariants, the completed board contracts and this handoff.

The repository contains a repository-local HTTPS resolution workaround because
the original machine intermittently resolves `github.com` to an unreachable
edge. A successful push can occasionally be followed by a failed
`git ls-remote`; the public GitHub API is an acceptable independent remote-SHA
check when that occurs.

## Completed productization boards

| Board | Result | Commit |
| --- | --- | --- |
| 1. Settings and registry | Durable Provider, Model, Agent, role and application settings with protected user ownership | `d0e9051` |
| 2. Artifact provenance | Immutable producer snapshots, contributors, reviewer, final integrator and three display modes | `8b52181` |
| 3. Startup discovery | Separated setup observations, capability-based model discovery, isolated probes and GUI registration | `74c053b` |
| 4. Usage and cost ledger | Per-call measurements, totals, budgets, conservative blocking and supported balance snapshots | `7947ef1` |

The detailed acceptance evidence remains in:

- `docs/reports/2026-08-29-board-1-settings-registry.md`;
- `docs/reports/2026-08-29-board-2-artifact-provenance.md`;
- `docs/reports/2026-08-29-board-3-startup-discovery.md`;
- `docs/reports/2026-08-29-board-4-usage-cost-ledger.md`.

## Refreshed verification baseline

Verification was rerun on 2026-08-29 before any Board 5 implementation:

- `python -m unittest discover -s tests -v`: 29 tests passed;
- offline demo run `6ea1b1dd-c558-4ed4-ab2c-27fd5df1ffd8` completed;
- the demo stored four completed tasks, ten structured messages and five
  Artifacts;
- the final Artifact retained manager producer identity, four contributors,
  review status and final-integrator status;
- the demo ledger stored six completed calls and 2,097 estimated tokens with
  explicit `estimated` token and cost sources;
- no budget alert was created;
- `doctor` resolved the npm-installed `codex.cmd` without invoking a model;
- local discovery found Codex CLI and left authentication, permission and
  connectivity unclaimed where evidence was unavailable;
- discovery did not run a connectivity probe;
- no real Codex model, paid Provider or Provider balance endpoint was called.

PowerShell output on the original machine can display UTF-8 Chinese as
mojibake. The repository and Artifact files decode correctly as UTF-8; terminal
rendering must not be mistaken for data corruption.

## Current architecture and durable contracts

### Control and cognition

Model reasoning proposes plans and produces work. Deterministic Python code
owns identity validation, permissions, dependency scheduling, timeouts,
persistence, budgets and routing enforcement. A manager model cannot grant
itself access or bypass the control plane.

### Registry and settings

SQLite is the runtime authority for Provider, Model, Agent, role assignment and
application settings records. JSON remains seed configuration. Later
synchronization must not overwrite or delete user-owned values.

### Discovery

Executable presence, authentication, permission, connectivity and model
observations remain separate. Discovery evidence describes what was observed;
it does not itself assign a project role. Connectivity probes remain explicit
and project-neutral.

### Artifact provenance

Every newly produced Artifact keeps immutable producer identity. Contributor,
reviewer and final-integrator audit records remain available internally even
when the user selects the `hidden` presentation mode.

### Usage, budgets and balance

Every Adapter invocation creates an immutable usage event. `actual`,
`provider_reported`, `estimated` and `unavailable` remain distinct. Unknown
values are not zero. Hard budgets block conservatively when the required prior
measurement is unavailable. Provider balance is queried only through an
Adapter that declares a supported API.

### Adapter and execution safety

All model hosts are accessed through Adapters. CLI commands remain argument
arrays executed with `shell=False`. Credentials must not be stored in source,
JSON or SQLite. Real coding Agents start read-only, and future write access
requires isolation and an explicit approval design.

## Board 5 acceptance scope

Board 5 is routing policy. It must implement:

1. manual, automatic and hybrid role selection;
2. capability, availability, cost and latency constraints;
3. user locks that prevent automatic replacement;
4. required separation between designated roles, Agents, Models or Providers;
5. durable routing explanations for every resolved assignment;
6. safe additive migration for existing SQLite databases;
7. sufficient automated coverage plus a Board 5 acceptance report;
8. roadmap, handoff and next-session updates;
9. sensitive-information scanning, commit, push and remote-main verification.

### Required interpretation

- `manual` uses the explicit persisted assignment and fails clearly when its
  required identity is unusable; it does not silently route elsewhere.
- `auto` selects only from candidates that satisfy hard capability,
  availability, budget and separation constraints.
- `hybrid` preserves user preferences while allowing deterministic fallback
  only inside the recorded constraints. A lock disables fallback.
- Missing cost or latency evidence must remain unknown. The router must not
  invent favorable values to make a candidate win.
- Routing must consume the Boards 1 through 4 persisted evidence instead of creating a
  parallel registry, discovery cache, provenance system or ledger.
- Each decision must make the selected identity and rejected candidates
  auditable, including the relevant evidence, constraints and reason codes.
- Selection logic belongs to deterministic control-plane code. A model may
  suggest preferences but cannot override routing policy or permissions.

## Explicitly out of scope for Board 5

- local Web or Electron settings UI, which belongs to Board 6;
- Codex App Server, A2A, MCP or remote Agent interoperability;
- automatic Git worktree creation, merge or deployment;
- a universal price catalog, currency conversion or new billing claims;
- broad startup model invocation or implicit connectivity probes;
- replacing all mock roles with real Providers;
- dynamic multi-round debate or general failure replanning.

## Real Codex boundary

The real Codex pilot remains paused. Before sending repository content or
derived project details to an external model service, obtain explicit user
authorization. If authorized later:

1. use only the architect role with Codex;
2. keep manager, implementer and reviewer on mocks;
3. keep Codex read-only;
4. use the existing JSONL capture path;
5. record thread, events, usage, duration, exit state and final Artifact;
6. do not connect every configured model at once.

This pilot is independent of Board 5 and is not implied by permission to
implement routing.

## Known limitations carried forward

- one manager planning pass and one synthesis pass;
- no dynamic replanning after worker failure;
- no interactive worker-to-worker question loop;
- no automatic price refresh or time-based budget policy;
- Codex CLI JSONL is processed after completion rather than streamed live;
- no App Server, A2A, MCP, worktree automation, Web UI or approval screen;
- intentionally narrow OpenAI-compatible response handling.

## Exact opening prompt for the next session

```text
Continue development directly in the existing Model Council repository supplied
for this task. Do not create a copy in the new task's default directory.

Before changing code, read AGENTS.md, README.md, docs/ARCHITECTURE.md,
docs/PROJECT_HANDOFF.md, docs/ROADMAP.md, docs/DEVELOPMENT_BOARDS.md,
docs/START_HERE_NEXT_SESSION.md, the four completed Board 1-4 reports, and
docs/reports/2026-08-29-pre-board-5-session-handoff.md.

Verify that git main contains implementation commit 7947ef1 and the later
pre-Board-5 handoff checkpoint, that the worktree is clean, and that local main
matches the public GitHub repository. Run the 29 existing tests, offline demo,
doctor, discovery scan and ledger summary before implementation.

Then implement Productization Board 5: routing policy. Support manual,
automatic and hybrid selection; capability, availability, cost and latency
constraints; user locks; required model separation; durable routing
explanations; safe SQLite migration; and sufficient automated tests. Consume
the existing registry, provenance, discovery and ledger contracts. Preserve
JSON as seed configuration and protect user-owned settings.

Do not build the Board 6 Web UI, Codex App Server, A2A, MCP, worktree
automation, a new billing system or broad real-model startup. The real Codex
pilot remains paused unless the user separately gives explicit authorization
to send repository content or derived details to an external model service.

Finish Board 5 with its own report, roadmap and handoff updates, sensitive-data
scan, commit, push and remote-main verification. Report the board outcome to
the user before beginning any later board.
```

## Resume checklist

1. Confirm the exact repository and branch.
2. Read this checkpoint and all required project documents.
3. Confirm a clean synchronized worktree.
4. Rerun the full offline baseline.
5. Review the current SQLite schemas and role-assignment call sites.
6. Implement only Board 5.
7. Stop for a user-facing board report before Board 6.
