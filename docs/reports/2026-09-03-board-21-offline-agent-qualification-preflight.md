# Board 21 Report: Offline Agent Qualification Preflight

Date: 2026-09-03

Status: accepted for local offline development; no execution authority

## Contribution to PROJECT_GOAL

Board 21 advances the pre-run verification stage by requiring a future Agent
qualification scope to be complete, explicit and privacy-safe before any
runtime or external verification is considered.

## Delivered

- Added `QualificationPreflightService` as a pure local validator.
- Added `supervisor qualification-preflight --candidate-file`.
- Validated exact Agent/Model/Provider identifiers, launch mode, transport and
  canonical lifecycle checks.
- Required read-only permissions, explicit exclusion of repository/private
  context, worktrees, writes, prompts and Artifact bodies.
- Required bounded input/output/total tokens, cost/currency, duration, one
  attempt and no retry.
- Required the three-stage approval ladder and runtime-only evidence policy.
- Rejected credential-shaped values, personal paths, protected runtime
  references, unknown fields and any execution-authority claim.
- Returned only a normalized scope, deterministic SHA-256, bounded blocker
  codes and `execution_authorized: false`; no candidate is persisted.

## Verification

```text
Board 21 focused tests: 4 passed
Full offline suite: 144 tests passed
Python compilation: passed
Tracked JSON validation: passed
Current-tree privacy scan: passed
Reachable-history privacy scan: passed
git diff --check: passed
```

## Safety and privacy

The preflight command does not load the project configuration, initialize
SQLite, start a process, invoke an Adapter or contact a Provider, model,
App Server, A2A, MCP or network endpoint. It does not retain the submitted
candidate file. Blocker output contains codes and field labels only and never
echoes rejected values.

## Explicit non-goals

- no real Agent qualification or process start;
- no login or actual-Model query;
- no Provider/model/network call;
- no repository context, worktree, write/test/merge or Git operation;
- no Artifact retention/purge;
- no remote authentication/signing or dynamic replanning.
