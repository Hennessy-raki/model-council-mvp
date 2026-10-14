# Project Status

Last updated: 2026-10-14

## Status boundary

The product purpose is defined in `docs/PROJECT_GOAL.md`: enable a user to
configure or accept a recommendation for a team of heterogeneous Agent+Model
members, verify each member before work, explicitly authorize the exact run,
and receive an auditable, source-aware and budget-aware result. This status
page describes implementation state against that goal; it does not replace it.

The canonical privacy requirement is that information about this machine must
not be recoverable by another party. That is wider than "do not publish": an
ignored file on disk is still recoverable from any copy, archive or migration of
the working tree. See the triage policy in `docs/PRIVACY_ISSUES.md`.

Board 25 (2026-10-14) independently audited Boards 1 through 23 rather than
inheriting their acceptance claims, widened the leakage model to offline copies,
removed machine-identifying values from newly persisted Artifact records, and
extended the privacy gate to inspect ignored local runtime state. Its report is
`docs/reports/2026-10-14-board-25-foundation-audit-and-trust-surface.md`.

Model Council is a local-first control plane with substantial offline control,
privacy and product-interface coverage. It is not a generally authorized
multi-model execution service.

- Boards 1 through 12 are the prepared public `0.2.0rc1` release candidate.
  The candidate is not tagged, pushed or published by this checkout.
- Board 13 is complete only for local-private Supervisor readiness controls.
- Board 14 is complete only for one local-private, read-only synthetic Manager
  execution. Its terminal experiment and consumed approval cannot be replayed.
- Board 17B is complete only for deterministic local Agent lifecycle fixtures;
  it does not qualify a real Agent or authorize a new model call.
- Board 18 is complete only for one explicitly configured local fake
  subprocess fixture; it does not qualify a real Agent or authorize a new
  model call.
- Board 20 is complete only for one bounded CLI sequence using the built-in
  local fake subprocess fixture; it does not qualify a real Agent or authorize
  a new model call.
- Board 21 is complete only for a pure local qualification preflight; it does
  not load project configuration, start a process, qualify a real Agent or
  authorize a new model call.
- Board 22 is complete only for binding eligible preflight results to non-mock
  Supervisor roles and approval provenance; it does not qualify a real Agent
  or authorize a new model call.
- Board 23 is complete only for local qualification provenance integrity and
  revalidation; it does not qualify a real Agent or authorize a new model call.
- Board 24's offline preparation scope is implemented as of 2026-10-14: the
  authorization package schema, the fact classification, the stale-on-drift
  digest and the read-only `authorization build` / `authorization verify`
  commands. It does not qualify a real Agent, start a process or authorize a
  new model call. Report:
  `docs/reports/2026-10-14-board-24-real-agent-qualification-authorization-implementation.md`.
- Board 26 is complete for the local offline binding slice: a built package can
  be bound to one role, captured against the current team snapshot, re-validated
  on every read and projected read-only through the CLI and the loopback Web
  view. Binding creates no start approval and grants no authority. Report:
  `docs/reports/2026-10-14-board-26-authorization-package-binding-and-projection.md`.
- Board 27 is complete for the local offline slice: a version comparison engine
  applies the operator's stated preference at the level of comparing two
  versions and at the level of ranking candidates, an explicit user preference
  always overrides the recommendation, and the discovery catalogue moved from a
  hardcoded four-vendor list into configuration so that a GUI-only application
  can be recorded without being treated as invocable. Report:
  `docs/reports/2026-10-14-board-27-version-preference-and-discovery.md`.

- Board 29 is complete for the local offline slice. It closes three gaps that
  the first real Agent observation exposed: the OpenAI-compatible adapter now
  records the service-reported model identity separately from the configured
  one, the Supervisor classifies authentication mode so an API-key Agent's login
  check is `not_applicable` rather than permanently unknown, and a provider may
  declare that `/models` is unavailable so the connectivity probe uses the
  completion endpoint instead of reporting a false failure. Report:
  `docs/reports/2026-10-14-board-29-gaps-from-first-real-observation.md`.

- Board 30 is complete for the local offline slice. A measured observation is now
  a first-class record: it requires an explicit measurement time and lifetime,
  records how each fact was obtained, is re-derived on every read, and is
  required before a non-mock role can be marked ready. A tampered record is
  `invalid`, an expired one is `stale`. The record is bound into the team
  snapshot, so a later measurement change makes the snapshot stale. Report:
  `docs/reports/2026-10-14-board-30-observed-evidence-qualification-record.md`.

Measured state at 2026-10-14, after Board 30: 284 offline tests across 28 test
files, 179 tracked files, 47 SQLite tables, 45 indexes and 33 recorded privacy
entries. Re-measure these rather than trusting them; they change with every
board.

One real Agent observation was performed on 2026-10-14 under explicit operator
authorization and is recorded in the Board 29 report. It confirmed process,
version, permission, protocol and connectivity, could not obtain `actual_model`
from a CLI-hosted Agent's output stream, and measured a fixed input-token
overhead of about 16,000 tokens per call regardless of prompt size. The consumed
call authorizes no further call.
- Its public-safe closeout is
  `docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md`.
- Local runtime databases, prompts, transport metadata, approvals, Provider
  records, responses and private project material remain ignored and must not
  enter Git.

## Delivered control-plane capabilities

| Area | Delivered state | Remaining boundary |
| --- | --- | --- |
| Registry, routing and budgets | Persistent settings, deterministic routing, usage/cost evidence and hard-budget handling are implemented. | Unknown usage/cost stays unavailable; a new Provider needs a new approved scope. |
| Sessions and interoperability | Codex App Server, A2A and MCP client controls are implemented with local/offline coverage. | No additional live A2A or MCP endpoint is verified. |
| Workspace and repair | Isolated worktrees, permission gates, evidence-bound merge and bounded repair/recovery are implemented. | A real writing Agent needs a distinct outbound-context and workspace authorization. |
| Product interface | Loopback approval/evidence views, comparison, backup/restore and release verification are implemented. | Electron packaging and broader operator workflows are deferred. |
| Controlled real execution | Exact experiment and start approvals, integrity binding, strict no-approval handling, output/usage/token/cost gates and one terminal synthetic Manager success are implemented. | No repeat, repository context, tools, writes, Git, parallelism or new Provider call is authorized. |
| Project-run authorization | Normal CLI and production Python `Orchestrator.run()` require a one-time approval bound to the current ready Supervisor team and exact goal; run provenance is persisted. | A private offline test harness remains for pipeline tests; real Agent lifecycle verification is deferred. |
| Agent lifecycle verification | Deterministic local fixture transitions and bounded lifecycle evidence are persisted and projected through CLI/Web. | Real Agent start/connect/attach, remote validation and external model calls remain separately scoped. |
| Local subprocess fixture | One explicit local command-array fixture can be started, observed, attached, detached and stopped with bounded evidence. | No real Agent, Provider, network or repository qualification. |
| CLI lifecycle sequence | A bounded single-process CLI sequence exercises the built-in fixture and stops it before exit. | No arbitrary command, cross-process PID control or real Agent qualification. |

## Board sequence after Board 15

Board 17B, Board 18, Board 19, Board 20, Board 21, Board 22 and Board 23 are
complete for local control-plane slices. Board 24 is frozen for offline
preparation; real Agent qualification still requires exact authorization.

1. **Board 16 — deterministic local transport-test reliability**: remains
   deferred unless the observed Windows socket interruption recurs under a
   reproducible test.
2. **Board 17A — team lifecycle and project-run authorization**: complete for
   the local offline vertical slice. The normal CLI `run` now requires a
   one-time approval bound to the current ready Supervisor team and exact goal.
3. **Board 19 — project-run approval hardening**: complete; production CLI and
   Python entry points now fail closed without exact approval.
4. **Board 20 — CLI local Agent lifecycle sequence**: complete for the local
   subprocess fixture slice.
5. **Board 24 — real-Agent qualification authorization package**: scope
   frozen; implement only offline schema, projection and tests until exact
   runtime identity and working directory can be separately authorized.
6. Artifact retention/purge, remote authentication/signing, generic context
   summarization and broader Provider coverage remain separate future scopes.

Board 21 (offline qualification preflight) and Board 22 (qualification
binding) are also complete local control-plane slices. Neither authorizes an
external call; the next real-Agent qualification board must build on their
scope, identity and stale-on-drift evidence.

Each future board must state its acceptance criteria, threat model, exclusions,
runtime storage rules and separate authorization ladder before implementation.

Board 15 acceptance report:
`docs/reports/2026-09-01-board-15-project-rebaseline.md`.

Board 17A plan and acceptance report:

```text
docs/reports/2026-09-01-board-17a-team-lifecycle-plan.md
docs/reports/2026-09-01-board-17a-team-lifecycle.md
```

Board 17B plan and acceptance report:

```text
docs/reports/2026-09-01-board-17b-agent-lifecycle-verification-plan.md
docs/reports/2026-09-01-board-17b-agent-lifecycle-verification.md
```

Board 18 plan, report and handoff:

```text
docs/reports/2026-09-01-board-18-local-subprocess-lifecycle-plan.md
docs/reports/2026-09-01-board-18-local-subprocess-lifecycle.md
docs/reports/2026-09-01-board-18-next-session-handoff.md
```

Board 19 plan and report:

```text
docs/reports/2026-09-03-board-19-project-run-approval-hardening-plan.md
docs/reports/2026-09-03-board-19-project-run-approval-hardening.md
```

Board 20 plan, report and handoff:

```text
docs/reports/2026-09-03-board-20-cli-local-lifecycle-plan.md
docs/reports/2026-09-03-board-20-cli-local-lifecycle.md
docs/reports/2026-09-03-board-20-next-session-handoff.md
```

Board 21 plan and acceptance report:

```text
docs/reports/2026-09-03-board-21-offline-agent-qualification-preflight-plan.md
docs/reports/2026-09-03-board-21-offline-agent-qualification-preflight.md
```

Board 22 plan and acceptance report:

```text
docs/reports/2026-09-03-board-22-qualification-binding-plan.md
docs/reports/2026-09-03-board-22-qualification-binding.md
```

Board 23 plan and acceptance report:

```text
docs/reports/2026-09-09-board-23-qualification-integrity-plan.md
docs/reports/2026-09-09-board-23-qualification-integrity.md
```

Board 24 plan and freeze record:

```text
docs/reports/2026-09-09-board-24-real-agent-qualification-authorization-plan.md
docs/reports/2026-09-09-board-24-real-agent-qualification-authorization-freeze.md
```

Board 24 is frozen for offline authorization-package preparation. It validates
the review boundary for a future Agent scope without starting a process or
authorizing a Provider/model call. Real Agent qualification remains separately
authorized work.

## Current quality gate

The required release-quality baseline is:

```text
full offline tests
Python compilation
tracked JSON validation
current-tree and reachable-history privacy scans
git diff --check
```

This status page is public-safe. It intentionally omits runtime identifiers,
exact prompts, responses, JSONL, stdout/stderr, exact Provider usage, billing
records, credentials, private paths and downstream project details.
