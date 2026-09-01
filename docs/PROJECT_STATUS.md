# Project Status

Last updated: 2026-09-01

## Status boundary

The product purpose is defined in `docs/PROJECT_GOAL.md`: enable a user to
configure or accept a recommendation for a team of heterogeneous Agent+Model
members, verify each member before work, explicitly authorize the exact run,
and receive an auditable, source-aware and budget-aware result. This status
page describes implementation state against that goal; it does not replace it.

Model Council is a local-first control plane with substantial offline control,
privacy and product-interface coverage. It is not a generally authorized
multi-model execution service.

- Boards 1 through 12 are the prepared public `0.2.0rc1` release candidate.
  The candidate is not tagged, pushed or published by this checkout.
- Board 13 is complete only for local-private Supervisor readiness controls.
- Board 14 is complete only for one local-private, read-only synthetic Manager
  execution. Its terminal experiment and consumed approval cannot be replayed.
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
| Project-run authorization | Normal CLI `run` requires a one-time approval bound to the current ready Supervisor team and exact goal; run provenance is persisted. | Low-level library callers retain a compatibility path; real Agent lifecycle verification is deferred. |

## Board sequence after Board 15

1. **Board 16 — deterministic local transport-test reliability**: remains
   deferred unless the observed Windows socket interruption recurs under a
   reproducible test.
2. **Board 17A — team lifecycle and project-run authorization**: complete for
   the local offline vertical slice. The normal CLI `run` now requires a
   one-time approval bound to the current ready Supervisor team and exact goal.
3. **Next — real Agent lifecycle verification**: first extend readiness from
   synthetic observations to one narrowly scoped local Agent fixture, then
   consider a separately authorized read-only real Agent pilot.
4. Artifact retention/purge, remote authentication/signing, generic context
   summarization and broader Provider coverage remain separate future scopes.

Each future board must state its acceptance criteria, threat model, exclusions,
runtime storage rules and separate authorization ladder before implementation.

Board 15 acceptance report:
`docs/reports/2026-09-01-board-15-project-rebaseline.md`.

Board 17A plan and acceptance report:

```text
docs/reports/2026-09-01-board-17a-team-lifecycle-plan.md
docs/reports/2026-09-01-board-17a-team-lifecycle.md
```

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
