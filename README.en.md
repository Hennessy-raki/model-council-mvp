# Model Council

**Language**: [Chinese](README.md) · [English](README.en.md)

A local-first orchestrator for collaboration between different models. It does not ask
the models to connect to each other over the network: one manager model passes results
between them through a shared task store, structured messages, and Artifact files.

One idea runs through the whole design: **cognition and control are separate.** The
manager model proposes plans and integrates results. Identity, dependencies,
permissions, budgets, approvals, timeouts, and persistence are enforced by deterministic
Python code. **A model cannot widen its own authority by going around the orchestrator.**

```text
user goal
   |
manager model -- produces a JSON task plan
   |
deterministic orchestrator -- validates identity, dependencies, concurrency, boundaries
   |
   +-- architecture model --+
   +-- implementation model +--> Artifact store + SQLite message board
   +-- research model ------+
   |
reviewer model
   |
manager model -- final synthesis
```

## What problem it solves

Not "run more models at once", and not "put several chat windows side by side".

The real problem is this: you own several Agents and models with different capabilities,
speeds, prices, and tool conditions, so **you** have to decide who is suited to what,
open and inspect every tool yourself, carry context and files between them yourself,
verify that the model you configured is the one that actually ran, and discover login or
permission problems yourself. And when the work is done, you still cannot tell **who
actually produced it** or what it cost.

Model Council moves that coordination into a trustworthy local control plane, while
leaving the decisions about **model choice, outbound data, task start, file modification,
cost, and final delivery** with you.

The goal is to make that loop configurable, inspectable, traceable, pausable, resumable,
and reviewable:

```text
configure or accept a recommended team of Agent+Model members
  (manager / worker / reviewer / integrator)
  -> start, connect or attach each member, checking its real state item by item
  -> if a member is unusable, report exactly which Agent, which model, which check
  -> once every member is ready, the system asks you to start
  -> you authorize, freezing the team, task, context, permissions, budget and stop rules
  -> the manager decomposes the task; workers exchange results via structured
     messages and Artifact references
  -> the reviewer checks independently; the manager integrates and delivers
  -> the delivery keeps the provenance chain
     Provider -> Model -> Agent -> Role -> Task -> Artifact
```

## Current status

**This is an experimental system, not a product where any Agent plus any model works out
of the box.** Read the boundaries below before judging what it can do.

**Solid and trustworthy, with measurement behind it**

- Control plane: registry, deterministic routing, usage and budget ledger, provenance;
- Approval chain: every real outbound call needs a **single-use, exact, SHA-256-bound,
  revocable** approval. Without one, the call cannot be made — this is measured;
- Isolated workspaces: explicit read, write, test and merge permissions. A merge happens
  only after human confirmation and uses `--ff-only`;
- Privacy gate: three scan scopes, covering reachable history and ignored local runtime
  data;
- Offline quality gate: **306 tests**, no third-party dependencies, Python 3.11+ only.

**Not verified — these are defects, not disclaimers**

- **The collaboration loop has never been run with two real models.** The project is
  called Model Council and its purpose is several different models completing a real
  project together, while the real calls so far amount to a few single-Agent synthetic
  tasks;
- **Board 14 is complete** only for one local-private, read-only, synthetic Manager
  execution. That execution **cannot be replayed**, and it does **not authorize** a
  repeat, repository context, tools, writes, Git or parallelism. Its public-safe closeout
  is
  [`docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md`](docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md);
- **A2A and MCP against a real third-party endpoint**: the protocol clients and approvals
  exist, but they have only ever been exercised against fake servers in this repository;
- **The model identity cannot be observed on this machine.** The tool's event stream
  carries no model field, and the configured relay endpoint answers a direct request with
  a Cloudflare 403. The system records that fact as `unknown` rather than substituting
  the configured value.

The full list is in [What is still wrong with this project](#what-is-still-wrong-with-this-project).

## Quick start

Requires **Python 3.11 or newer and nothing else**.

```powershell
python -m model_council demo "design a local project management tool with multi-model collaboration"
```

Output goes to `runtime/` (`council.db` plus `artifacts/`).

To see what exists on this machine without invoking any model:

```powershell
python -m model_council agents --config config.example.json
python -m model_council doctor --config config.codex.example.json
python -m model_council discovery scan --config config.codex.example.json
python -m model_council discovery show --config config.codex.example.json
```

To run a real project, first go through the local Supervisor flow to create and approve the
run authorization:

```powershell
python -m model_council supervisor wizard `
  --team-file config.supervisor.team.example.json `
  --config config.example.json
python -m model_council supervisor check --config <LOCAL_CONFIG>
python -m model_council supervisor snapshot --config <LOCAL_CONFIG>
python -m model_council supervisor request-run <SNAPSHOT_ID> "<YOUR GOAL>" `
  --config <LOCAL_CONFIG>
python -m model_council supervisor approve <APPROVAL_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council run "<YOUR GOAL>" `
  --start-approval <APPROVAL_ID> --config <LOCAL_CONFIG>
```

Usage, budgets, and the loopback-only local interface:

```powershell
python -m model_council ledger summary --config config.example.json
python -m model_council web --config config.example.json
```

**The full reference for 21 top-level commands and 96 subcommands is in
[`docs/CLI.md`](docs/CLI.md).** Configuration for a real Codex or an OpenAI-compatible API
is in [`docs/ADAPTERS.md`](docs/ADAPTERS.md).

## Core concepts

The project separates four identities. Conflating them produces wrong conclusions:

| Concept | Meaning |
| --- | --- |
| **Provider** | Supplies model service, authentication, endpoints, usage or billing |
| **Model** | The thing that actually infers, with capability, context, speed and price |
| **Agent** | The tool that hosts a model and exposes an execution interface, such as a CLI, an App Server or a desktop application |
| **Role** | The responsibility taken in one project, not a fixed vendor identity |

Four roles are the minimum:

- `manager` — understands the goal, decomposes the task, dispatches, follows up,
  arbitrates and integrates;
- `worker` — performs architecture, research, implementation, testing, documentation or
  another specialist task;
- `reviewer` — independently checks conclusions, code, evidence, risks and omissions;
- `integrator` — produces the final delivery; it may be the manager or a separate member.

One Agent+Model may hold several roles, but **the system must record the actual identity
behind each role for that run**. You may also require that key roles are held by different
models.

## Non-negotiable constraints

These parts of the design are not intended to be relaxed:

- **The user is the final authorizer**; the manager model is not the highest authority;
- **No approval means no outbound call.** A real call needs a single-use, exact, revocable
  authorization, and a consumed approval **cannot be replayed**;
- **Full history is never broadcast to every model**; only the minimum context needed for
  the current task is passed;
- **A registered item is not a runnable one**, and a configured model identity is not
  evidence that it served the request;
- **No silent substitution** of an Agent or Model you have locked;
- **An unknown value stays `unavailable`, never zero**, and an estimate never poses as a
  bill;
- **A real coding Agent starts read-only**; write permission needs an isolated workspace
  and a separate approval;
- **Failure must be visible, locatable and recoverable**; uncertainty is never hidden
  behind a fake success.

## What can be observed on this machine

The project's purpose is to verify each member's real state, so here is how far that
actually gets.

Seven qualification facts, measured on 2026-10-14 against codex 0.154.0:

| Fact | Observable | Why |
| --- | --- | --- |
| `process` | ✅ | the process starts, and its exit code is captured |
| `version` | ✅ | the version probe returns it directly |
| `protocol` | ✅ | the JSONL event stream completes a handshake |
| `connectivity` | ✅ | the synthetic token came back exactly |
| `login` | ➖ not applicable | API-key mode has no interactive login state |
| `actual_model` | ❌ **unreachable from both sides** | the tool's event stream has no model field, and the relay endpoint answers a direct request with Cloudflare 403 |
| `permission` | ❌ | the tool does not echo the sandbox it used, and the requested value is not the observed value |

**Four are observable, two are not, one does not apply.**

An observation record also has one of two origins, and only one can qualify a real Agent:

| Origin | Meaning | Usable for readiness |
| --- | --- | --- |
| `probe_run` | produced by a probe this system actually ran, with facts derived from captured output | ✅ |
| `operator_authored` | facts supplied by the caller | ❌ **refused by default** |

That distinction matters: an operator who can type `observed` into a JSON file has not
measured anything. A record therefore carries a provenance receipt — command digest,
output hash, and the probe's own start and finish times — and **the measurement time
cannot be chosen by the caller**.

**The honest limit**: this does not prevent a local operator with the right permissions
from fabricating evidence after the fact, because that operator owns the process, the disk
and the tool. What it changes is the **trust boundary**, not the possibility of
misrepresentation.

## What is still wrong with this project

The categories exist for different reasons. Treating them as one would misjudge progress.

### Capability gaps (not implemented)

- **Multi-round debate and dynamic replanning**: the manager plans once and synthesizes
  once; failure does not trigger a new plan;
- **Interactive question and answer between workers**: only persisted results and the
  final context pass between them;
- **Automatic price catalogue refresh, currency conversion and time-window budgets**: the
  price table is declared by the operator;
- **General context summarization**: needs a reviewed retention and disclosure policy
  first;
- **Remote node authentication and signing**: A2A remote identity stops at endpoint
  validation;
- **Artifact retention and purge policy**: the store only grows;
- **Electron packaging and broader operator workflows**.

### Verification gaps (implemented, only ever exercised against fakes)

**This is the category to watch: the code exists and the tests pass, but it has never met
the real world.**

- **The collaboration loop has never been run with two real models**;
- **A2A and MCP against a real third-party endpoint**: only fake servers so far;
- **Codex App Server**: few real runs, thin sample.

### Observation gaps (structurally unmeasurable here)

- **`actual_model`** and **`permission`**, for the reasons above. The system records them
  as `unknown` rather than substituting a configured value;
- **There is no exception policy for an unobservable fact yet.** Readiness requires all
  seven facts, so a non-mock role currently cannot reach ready on this machine.

### Interface gaps (the capability exists without a production entry point)

- `RepairService.run_local_until_terminal()` and `WorkspaceService.invoke_cli()` are used
  only by tests. They are **explicitly labelled** local callbacks and fake-CLI exercises,
  not missing wiring.

### Assessed and deliberately not started

Not a defect; a decision record, kept here so it stays traceable:

- **Local transport reliability hardening**: one non-reproducible Windows loopback
  interruption was observed. It will not be started unless a reproducible failing test is
  captured first, because blindly patching an unreproducible fault only adds new risk.

### In one line

What has not been verified is not these mechanisms but **how they behave against a real
Agent**. The control plane and the approval chain are trustworthy, with measurement behind
them; what is missing is coverage under real conditions.

## Privacy scanning

The scan has three distinct scopes. Do not mix them up:

| Command | Scope | When |
| --- | --- | --- |
| `privacy_scan.py` | Git-tracked plus non-ignored untracked files | the publication gate for every board |
| `privacy_scan.py --history` | adds every reachable historical blob and committer domain | the gate before a public push |
| `privacy_scan.py --local-state` | adds the ignored `runtime/` and `runtime-*` | before moving, archiving or migrating the working tree |

The third scope is ignored local runtime data. It never enters Git, but it **can still be
read from this machine or any copy of it**, so under a local privacy requirement it is
also a surface to check.

The scan prints `path:line:category` and **never echoes the matched value itself**.

## Project map

| What you want | Where |
| --- | --- |
| Full command reference (21 top-level commands) | [`docs/CLI.md`](docs/CLI.md) |
| Connecting a real Codex or an OpenAI-compatible API | [`docs/ADAPTERS.md`](docs/ADAPTERS.md) |
| The problem the project exists to solve, and the principles it will not bend | [`docs/PROJECT_GOAL.md`](docs/PROJECT_GOAL.md) |
| Current implementation state and each board's boundary | [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) |
| Scope and acceptance report for every board | [`docs/DEVELOPMENT_BOARDS.md`](docs/DEVELOPMENT_BOARDS.md) and [`docs/reports/`](docs/reports/) |
| Architecture and invariants | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Privacy triage policy and register | [`docs/PRIVACY_ISSUES.md`](docs/PRIVACY_ISSUES.md) |
| Working agreement to read before changing code | [`AGENTS.md`](AGENTS.md) |
| Handoff notes for a new session | [`docs/START_HERE_NEXT_SESSION.md`](docs/START_HERE_NEXT_SESSION.md) |

## Development gate

Run these before and after changing code:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q model_council tests scripts
python scripts/privacy_scan.py --history
python scripts/privacy_scan.py --local-state
python scripts/release_verify.py
```

Development proceeds in **boards**. A completed board delivers, together: the
implementation, automated tests, an acceptance report under `docs/reports/`, roadmap and
handoff updates, **exactly one** identifiable Git commit, and a full privacy scan.

## License

[MIT](LICENSE)
