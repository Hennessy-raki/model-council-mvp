# Board 17A Next-Session Development Handoff

Date: 2026-09-01

Status: handoff only; no new board is frozen by this document

## 1. Approved checkout and private-development boundary

Work must continue directly in the user-approved existing checkout:

```text
<ACTUAL_APPROVED_CHECKOUT>
```

Do not copy the repository, create a replacement repository or create a
worktree. Local code changes, tests and commits are allowed. Do not push, tag,
create a GitHub Release or publish incubation work.

The ignored `runtime-board14/` directory is private local state. Do not read,
display, quote, copy, commit or transmit its contents. This includes
`config.local.json`, `team.local.json`, runtime databases, WAL/SHM files,
prompts, approvals, manifests, Provider records, responses, backups and
private project material.

Previous login, connectivity, readiness and consumed-approval evidence does not
authorize a new model call or a broader external scope.

## 2. Current repository checkpoint

At handoff creation:

```text
branch: main
HEAD: f0b0fd4 Board 17A integrate project-run authorization
relative to origin/main: ahead 17
tracked worktree: clean
runtime-board14/config.local.json: present and ignored
```

No current-tree or reachable-history privacy finding is accepted. The latest
Board 17A commit contains only tracked code, tests and public-safe documents.

## 3. Canonical product goal

Read `docs/PROJECT_GOAL.md` before interpreting any board.

The product is a local-first control plane that lets a user configure or
accept a recommendation for a heterogeneous Agent+Model team, verify each
member, explicitly authorize the exact project run, and receive an auditable,
source-aware, budget-aware and recoverable result.

The intended lifecycle is:

```text
discover/register
  -> choose or recommend Provider/Model/Agent/Role bindings
  -> start/connect/attach required Agents
  -> verify process, login, actual Model, Provider, permission, version,
     protocol, connectivity and cost evidence
  -> report blockers and remediation
  -> freeze the current team and exact project scope
  -> ask the user for explicit authorization
  -> run bounded Manager/Worker/Reviewer collaboration
  -> exchange only structured messages, summaries and Artifact references
  -> independently review and integrate
  -> deliver source, evidence, risk, usage and cost information
  -> support safe pause, failure handling, recovery and termination
```

User authority, cognition/control separation, no silent substitution, explicit
permission boundaries, local privacy and fail-closed behavior are
non-negotiable.

## 4. Completed work through Board 17A

Boards 1–12 provide the public `0.2.0rc1` release candidate, still untagged,
unpublished and not pushed by this checkout.

Board 13 provides local-private Supervisor readiness controls based on
synthetic observations. It does not launch real processes or invoke a model.

Board 14 provides controlled local experiments and one terminal, read-only
synthetic Manager execution. Its experiments and approvals cannot be replayed.

Board 15 rebaselines project status and documentation.

Board 17A adds the first integration of the canonical user lifecycle into the
normal project entry point:

- `SupervisorService.request_project_run()` creates an exact project-run scope;
- the scope binds the current ready team snapshot and normalized project goal;
- `start_project_run()` revalidates team state and goal, then atomically
  consumes the approval once;
- `Orchestrator.run(..., start_approval_id=...)` consumes that gate before
  creating the run or invoking an Adapter;
- `runs` records team snapshot, approval and scope digest provenance;
- CLI `run` requires `--start-approval`;
- CLI `supervisor request-run` creates the project-run approval;
- the loopback Web projection exposes Supervisor state and approvals;
- synthetic Manager-platform approvals remain a separate action.

Implementation and evidence:

```text
docs/reports/2026-09-01-board-17a-team-lifecycle-plan.md
docs/reports/2026-09-01-board-17a-team-lifecycle.md
```

## 5. Current verification evidence

The latest completed quality gate passed:

```text
python -m unittest discover -s tests -v
  134 tests passed
python -m compileall -q model_council tests scripts
  passed
tracked JSON validation
  12 files passed
python scripts/privacy_scan.py
  passed
python scripts/privacy_scan.py --history
  passed
git diff --check
  passed
```

The first test attempt in the restricted session failed because the sandbox
could not create temporary directories. The same suite passed in the
authorized local writable environment; do not classify the sandbox failure as
a code regression.

## 6. Important remaining gaps

The final product goal is not complete yet.

1. Readiness is still synthetic/static. Real Agent start, connect, attach,
   login and actual-Model verification are not generally implemented.
2. The normal CLI path is now gated, but the low-level Python
   `Orchestrator.run()` API retains a compatibility path when no approval ID
   is passed. Removing that escape requires a separately scoped migration.
3. No real project/repository-context run, writing Agent or real Reviewer has
   been authorized or validated.
4. A2A/MCP live third-party validation, remote authentication and message
   signing remain deferred.
5. Dynamic replanning, interactive worker questions and a complete user-facing
   pause/resume/terminate experience remain incomplete.
6. Artifact retention, cleanup preview and purge are not implemented. Purge
   must be a separate board with its own exact approval and recovery design.
7. Board 16 remains deferred unless the Windows loopback interruption becomes
   reproducible.

## 7. Next recommended board

The next board should advance the lifecycle from synthetic readiness toward one
narrowly scoped local Agent lifecycle fixture. It must be separately frozen
before implementation.

Recommended scope:

- use a local fake process or deterministic fixture first;
- model start, connect, attach and detach states;
- capture separate process, login, actual-Model, permission, version,
  protocol and connectivity observations;
- expose remediation and `user_confirmation_required` states;
- bind the evidence to the existing team snapshot and project-run approval;
- preserve stale-on-drift and single-use authorization;
- exercise the same service methods from CLI and Web;
- keep Manager/Worker/Reviewer synthetic and local;
- add no Provider call, no external endpoint, no repository context, no write,
  no worktree and no Git operation.

Acceptance must include positive and negative tests for:

- missing Agent process;
- login failure;
- wrong observed Model;
- insufficient permission;
- version/protocol mismatch;
- connectivity failure;
- manual confirmation;
- evidence drift after snapshot;
- approval drift before run;
- no task delivery before approval.

Artifact retention/purge should remain deferred until its contribution to the
canonical lifecycle is explicitly justified.

## 8. Safe opening sequence for the next session

Use the actual checkout and perform read-only checks first:

```powershell
cd <ACTUAL_APPROVED_CHECKOUT>
git status --short --branch
git log -1 --oneline
git diff --check
git check-ignore -v runtime-board14/config.local.json
```

Read, in order:

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
docs/reports/2026-09-01-board-17a-team-lifecycle-plan.md
docs/reports/2026-09-01-board-17a-team-lifecycle.md
this handoff
```

Do not begin the next board merely because this handoff exists. First write
and freeze the next board's business objective, scope, inputs/outputs,
authorization ladder, privacy rules, acceptance criteria, threat model and
exclusions.

## 9. Local commit and publication boundary

The current local checkpoint is commit `f0b0fd4`. It is intentionally ahead of
`origin/main`. Do not push, tag, create a GitHub Release or claim remote-main
verification for this private incubation state.
