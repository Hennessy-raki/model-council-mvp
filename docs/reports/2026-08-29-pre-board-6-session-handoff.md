# Pre-Board-6 Session Handoff

Date: 2026-08-29

Status: accepted checkpoint; Board 6 implementation has not started

## Purpose

This checkpoint freezes the complete local-first product baseline after
Productization Boards 1 through 5. It is a documentation and verification
handoff, not a local-interface implementation.

## Authoritative repository state

- Repository: `Hennessy-raki/model-council-mvp`.
- Visibility: public.
- License: MIT.
- Default branch: `main`.
- Privacy-cleaned Board 5 implementation commit:
  `f386ecea1dda471921e331dd0cb0f354f926ba3a`.
- The public Git remote and GitHub API both returned that SHA before this
  checkpoint was created.
- The worktree was clean after the implementation commit and history rewrite.

All reachable history was rewritten to replace an older README home-directory
example with a generic placeholder. Current-tree and full reachable-history
privacy scans passed. GitHub's low-level object store may retain unreferenced
objects until garbage collection. A private GitHub Support purge is the
recommended follow-up when immediate physical deletion is required.

## Completed productization boards

| Board | Result | Clean-history commit |
| --- | --- | --- |
| 1. Settings and registry | Durable Provider, Model, Agent, role and application settings with protected user ownership | `93ebd34` |
| 2. Artifact provenance | Immutable producer snapshots and participation attribution | `ab20480` |
| 3. Startup discovery | Separated observations, capability-based discovery and isolated probes | `8c81c14` |
| 4. Usage and cost ledger | Per-call measurements, totals, budgets and supported balance snapshots | `e88c7f6` |
| 5. Routing policy | Deterministic role selection, constraints, locks, separation and durable explanations | `f386ece` |

The detailed Board 5 evidence is in:

```text
docs/reports/2026-08-29-board-5-routing-policy.md
```

## Refreshed verification baseline

- `python -m unittest discover -s tests -v`: 41 tests passed;
- offline demo run `0179d65d-91c2-4cd6-b6fe-448fe178cad6` completed;
- the demo stored four completed tasks, ten messages and five Artifacts;
- five routing decisions were resolved before Adapter invocation;
- the demo ledger stored six completed calls and 2,282 estimated tokens;
- no budget alert was created;
- `doctor` resolved `codex.cmd` without invoking it;
- discovery scanned local commands without a connectivity probe;
- `python scripts/privacy_scan.py --history` passed after history cleanup;
- no real Codex model, paid Provider, balance endpoint or external model service
  was called.

## Stable control-plane contracts

### Registry and settings

SQLite remains authoritative for Providers, Models, Agents, role assignments
and application settings. JSON remains seed data. User-owned values survive
later synchronization.

### Discovery

Executable, authentication, permission, connectivity and model observations
remain separate. Discovery does not assign project roles and does not probe
connectivity implicitly.

### Artifact provenance

Every new Artifact records immutable producer identity plus contributor,
reviewer and final-integrator attribution. Display suppression never deletes
the internal audit trail.

### Ledger and budgets

Every Adapter invocation records normalized usage evidence. `actual`,
`provider_reported`, `estimated` and `unavailable` remain distinct. Hard
budgets block conservatively when required evidence is unavailable.

### Routing

Every manager, worker and reviewer role is resolved before invocation.

- manual assignments fail without silent fallback;
- automatic assignments use only eligible configured Adapters;
- hybrid assignments preserve preferences and fall back only when unlocked;
- capability, availability, cost, latency, hard-budget and Agent/Model/Provider
  separation constraints are deterministic;
- missing cost and latency remain unknown;
- every success or failure stores selected evidence, rejected candidates and
  reason codes in `routing_decisions`.

### Privacy and execution safety

Public-push privacy checks are mandatory after every board. They scan the
current repository, reachable historical blobs and commit-author domains
without printing possible secret values.

All model hosts remain behind Adapters. CLI commands remain argument arrays with
`shell=False`. Credentials do not belong in source, JSON or SQLite. Real coding
Agents start read-only, and private repository content requires explicit user
authorization before external model use.

## Board 6 acceptance scope

Board 6 is the local settings interface. It should:

1. provide a local control surface over the stable SQLite registry;
2. edit Providers, Models, Agents, roles and application settings;
3. expose discovery, provenance, ledger, budget and routing state;
4. display routing explanations and rejected-candidate evidence safely;
5. preserve user-owned values and validated routing constraints;
6. keep state local by default;
7. add tests, a Board 6 report and safe additive migrations when required;
8. run the full privacy gate before public push.

## Explicitly out of scope for Board 6

- Codex App Server and persistent real-model sessions;
- A2A, MCP and remote Agent interoperability, which belong to Board 7;
- automatic worktree creation, merge or deployment;
- a universal price catalog or new billing claims;
- broad real-model startup;
- replacing deterministic routing with browser-side or model-generated
  authorization.

## Known limitations carried forward

- one manager planning pass and one synthesis pass;
- no dynamic replanning after worker failure;
- no interactive worker-to-worker question loop;
- no automatic price refresh or time-based budget policy;
- Codex CLI JSONL is processed after completion rather than streamed live;
- no App Server, A2A, MCP, worktree automation or approval screen;
- intentionally narrow OpenAI-compatible response handling;
- unreferenced GitHub objects can require platform-side garbage collection or
  Support intervention after a history rewrite.

## Exact opening prompt for the next session

```text
Continue development directly in the existing Model Council repository supplied
for this task. Do not create a replacement repository.

Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/PROJECT_HANDOFF.md,
docs/ROADMAP.md, docs/DEVELOPMENT_BOARDS.md, docs/PRIVACY.md,
docs/START_HERE_NEXT_SESSION.md, all completed Board 1-5 reports and
docs/reports/2026-08-29-pre-board-6-session-handoff.md.

Verify the clean public main baseline, run the 41 tests, offline demo, doctor,
discovery scan, ledger summary, routing decision inspection and
python scripts/privacy_scan.py --history before implementation.

Then implement only Productization Board 6: the local settings interface over
the existing registry, discovery, provenance, ledger, budget and routing
contracts. Keep SQLite authoritative, preserve user-owned values and keep all
state local by default.

Do not begin Board 7 Codex App Server, A2A, MCP or remote interoperability. Do
not invoke real external models without separate explicit authorization.

Finish Board 6 with tests, its report, documentation updates, the full privacy
gate, commit, push and remote-main verification. Stop for a user-facing report
before Board 7.
```

## Resume checklist

1. Confirm the exact repository, clean branch and public remote SHA.
2. Read this checkpoint and all required project documents.
3. Rerun the offline and privacy baselines.
4. Review the current SQLite and routing presentation contracts.
5. Implement only Board 6.
6. Stop for a user-facing board report before Board 7.
