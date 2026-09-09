# Model Council Development Handoff — Next Session

Date: 2026-09-09

Status: handoff checkpoint after Board 23; no external-call authority is
granted by this document.

## 1. Purpose of this handoff

This document is the authoritative continuation note for the next development
session. It preserves the project goal, the current implementation boundary,
the completed local evidence and the conditions that must be satisfied before
real-Agent work begins.

The tracked document is public-safe. It intentionally uses placeholders for
the approved checkout and excludes local runtime identifiers, credentials,
prompts, Provider responses, private project content and machine-specific
paths.

## 2. Approved working boundary

Continue directly in the already approved existing checkout:

```text
<ACTUAL_APPROVED_CHECKOUT>
```

Do not copy the repository, create a replacement repository or create a
worktree for routine maintenance. Local code changes, tests and commits are
allowed. Do not push, tag, create a GitHub Release or publish incubation work.

`runtime-board14/` is a private ignored directory. Do not read, display, quote,
copy, submit, commit or transmit anything below it. This includes local
configuration, databases, WAL/SHM files, prompts, approvals, manifests,
Provider records, responses, backups and private project material.

Credentials, runtime databases, backups, Provider responses, prompt instances,
private project contents and worktrees must remain outside Git. Previous login,
connectivity, readiness and consumed-approval evidence never authorizes a new
model call or a broader external scope.

## 3. Canonical product goal

Model Council is a local-first control plane that enables a user to configure
or accept a recommendation for a heterogeneous Agent+Model team, verify every
member, freeze the exact team and project scope, authorize one bounded run, and
receive a traceable, reviewable, recoverable result with usage and cost
evidence.

The target lifecycle is:

```text
discover/register
  -> configure Provider/Model/Agent/Role
  -> start/connect/attach Agents
  -> verify process, login, actual Model, Provider, permissions, version,
     protocol, connectivity and cost evidence
  -> report blockers and remediation
  -> freeze team and exact project scope
  -> obtain explicit user authorization
  -> run bounded Manager/Worker/Reviewer collaboration
  -> exchange structured messages, summaries and Artifact references
  -> independently review and integrate
  -> deliver source, evidence, risk, usage, cost and unresolved issues
  -> support pause, failure, recovery and termination
```

The control plane must remain separate from model cognition: a Manager may
propose work but cannot grant itself permission; the Supervisor and persisted
approvals enforce identity, scope, lifecycle, budget and stop rules.

## 4. Current repository checkpoint

Verified at the start of this handoff:

```text
branch: main
HEAD: 5f38b5a Update Board 23 development handoff
relative to origin/main: ahead 30
tracked worktree: clean
runtime-board14/config.local.json: present and ignored by runtime-*/
```

No push, tag or release has been performed.

## 5. Completed implementation

- Boards 1–12: public-safe `0.2.0rc1` release candidate, untagged and
  unpublished.
- Board 13: local-private Supervisor readiness, synthetic observations,
  immutable team snapshots and start approvals.
- Board 14: one terminal, read-only, synthetic Manager execution; all
  experiment approvals are consumed and cannot be replayed.
- Board 15: project-status and documentation rebaseline.
- Board 17A: exact-goal project-run approval bound to the current ready team;
  stale-on-drift and atomic single-use consumption; CLI/Web projection.
- Board 17B: deterministic Agent lifecycle fixture with
  start/connect/attach/detach/stop evidence and remediation states.
- Board 18: bounded local fake subprocess controlled with an explicit
  argument array and `shell=False`.
- Board 19: production Python and CLI project-run entry points fail closed
  without the exact Supervisor project-run approval.
- Board 20: one-process CLI `supervisor lifecycle-sequence` exercising
  `start -> connect -> attach -> detach -> stop`, with the fixture stopped
  before command exit. Cross-process PID control and arbitrary commands were
  deliberately rejected.
- Board 21: pure local `supervisor qualification-preflight` validation of a
  future Agent qualification declaration; it returns a deterministic digest
  and bounded blockers without loading runtime state or starting anything.
- Board 22: qualification preflight binding for non-mock roles, with snapshot
  and project-run approval provenance plus stale-on-drift handling.
- Board 23: qualification provenance integrity and revalidation against the
  stored digest and current Agent/Model/Provider registry.

Key implementation areas:

```text
model_council/supervisor.py       Supervisor state, snapshots and approvals
model_council/local_fixture.py    bounded local fake subprocess fixture
model_council/cli.py              lifecycle and project-run entry points
model_council/orchestrator.py     approval-gated production run path
model_council/web.py              loopback projection of local state
scripts/privacy_scan.py           current-tree and reachable-history checks
```

## 6. Verification evidence

The Board 23 quality gate is green:

```text
offline test suite: 150 tests passed
Python compilation: passed
tracked JSON validation: 12 files passed
current-tree privacy scan: passed
reachable-history privacy scan: passed
git diff --check: passed
```

No Provider, model, App Server, A2A, MCP or external endpoint was called for
this handoff. No repository context, writing permission, worktree creation or
Artifact purge was performed.

## 7. Remaining gaps against the final goal

1. Agent readiness is still synthetic/local-fixture based; a real Agent has
   not been generally qualified.
2. Real process identity, login, actual-Model, permission, version, protocol
   and connectivity evidence require a new exact scope.
3. Repository-context execution, writing Agents, real Reviewers and merge
   workflows are not authorized by the completed boards.
4. Live third-party A2A/MCP, remote authentication/signing and broader
   Provider coverage remain deferred.
5. Dynamic replanning, interactive worker questions and complete pause/resume/
   terminate UX remain incomplete.
6. Artifact retention, cleanup preview and purge remain a separate future
   board with its own recovery and approval design.
7. Board 16 remains deferred unless the Windows loopback interruption becomes
   reproducible.

## 8. Candidate next route (not yet frozen)

The next product-aligned candidate is a narrowly scoped real-Agent
qualification board. Before changing code, the next session must write and
review a new plan containing all of the following. Boards 21–23 are necessary
preparation but are not execution authorization:

- contribution to `docs/PROJECT_GOAL.md` and the exact lifecycle step advanced;
- one named Agent, Model and Provider (or an explicit offline-only fixture);
- process, login, permission and working-directory boundaries;
- complete input/context inventory and explicit repository/worktree/write
  exclusions;
- token, cost, duration and retry/stop limits;
- separate approval ladder for preparation, outbound context and execution;
- evidence schema, remediation and `user_confirmation_required` behavior;
- privacy threat model, disclosure controls and runtime-only storage rules;
- acceptance tests, rollback/recovery behavior and explicit non-goals.

Until that plan is frozen and separately authorized, do not call a real Agent,
Provider, network endpoint, App Server, A2A, MCP or model. A safer first
implementation remains an offline design/preflight slice using deterministic
fixtures only.

## 9. Safe opening sequence

Run from the existing checkout:

```powershell
Get-Location
git status --short --branch
git log -1 --oneline
git diff --check
git check-ignore -v runtime-board14/config.local.json
```

Read the canonical and latest handoff documents before planning:

```text
AGENTS.md
README.md
docs/PROJECT_GOAL.md
docs/ARCHITECTURE.md
docs/PROJECT_HANDOFF.md
docs/ROADMAP.md
docs/DEVELOPMENT_BOARDS.md
docs/PROJECT_STATUS.md
docs/START_HERE_NEXT_SESSION.md
docs/PRIVACY.md
docs/PRIVACY_ISSUES.md
docs/reports/2026-09-03-board-20-cli-local-lifecycle-plan.md
docs/reports/2026-09-03-board-20-cli-local-lifecycle.md
this handoff
```

Then run the offline quality gate before any code change:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q model_council tests scripts
python scripts/privacy_scan.py
python scripts/privacy_scan.py --history
git diff --check
```

If any check fails, diagnose locally and do not broaden scope. If a new board
would touch external calls, private context, credentials, worktrees or
destructive cleanup, stop and re-freeze its authorization and threat model.

## 10. Handoff completion rule

This checkpoint is complete when the next session can reproduce the stated
checkout and quality-gate evidence, read this document, freeze the next Board
before implementation and preserve every privacy and approval boundary above.
