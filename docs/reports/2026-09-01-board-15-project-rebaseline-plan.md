# Board 15 Plan: Project Rebaseline and Documentation Consistency

Date: 2026-09-01

## Goal

Make the project’s public-safe status documentation accurately distinguish
delivered control-plane capabilities, local-private incubation results and
deferred work. Add an offline regression test that prevents the authoritative
entry documents from regressing to an obsolete Board 14 state.

## Scope

- add one public-safe project-status page;
- update AGENTS, README, roadmap, development-board and handoff entry points;
- reclassify Milestones 2 through 5 into completed core controls and genuinely
  deferred work;
- add a documentation consistency regression test;
- record a Board 15 acceptance report and next-session handoff.

## Exclusions

- no Provider, App Server, A2A or MCP invocation;
- no credential, runtime, prompt, response, JSONL, usage or billing inspection;
- no workspace, Git permission, merge, backup/restore or release behavior
  change;
- no push, tag or GitHub Release;
- no attempt to reproduce or mask a one-off Windows loopback socket interruption
  without a reproducible product-side cause.

## Acceptance criteria

1. The authoritative entry documents state that Board 14 is complete only for
   one terminal local-private synthetic execution and that it cannot be
   replayed.
2. They no longer claim that Board 14 is in progress or has no executor.
3. The roadmap marks delivered infrastructure separately from unverified or
   deferred expansion.
4. A deterministic offline test verifies the status-page links and Board 14
   terminal wording.
5. Full offline tests, compilation, tracked JSON validation, current-tree and
   reachable-history privacy scans and `git diff --check` pass.

## Next authorization boundary

Board 15 creates no external-call authority. Any Board 16 reliability change
or Board 17/18 capability expansion must be separately frozen and authorized.
