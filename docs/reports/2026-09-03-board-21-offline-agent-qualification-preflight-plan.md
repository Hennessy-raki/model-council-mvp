# Board 21 Plan: Offline Agent Qualification Preflight

Date: 2026-09-03

Status: frozen for local offline implementation; no execution authority

## Contribution to PROJECT_GOAL

This board advances the lifecycle from configured Agent+Model bindings toward
pre-run verification by making the proposed qualification scope explicit,
reviewable and fail-closed before any real Agent or Provider work is
considered.

## Business objective

An operator must be able to inspect whether a proposed Agent qualification
scope is sufficiently specified and privacy-safe before asking for any
runtime or external verification. Missing identity, permissions, limits,
approval stages or context exclusions must be reported as blockers rather than
silently inferred.

## Scope

- add a pure local `QualificationPreflightService`;
- accept a JSON-serializable candidate declaration;
- validate Agent, Model and Provider identity, lifecycle checks, permissions,
  context inventory, repository/worktree/write exclusions, budget and stop
  rules, approval ladder and evidence policy;
- reject credentials, personal absolute paths, repository/private context,
  unbounded limits and implied external execution;
- return a sanitized normalized scope, deterministic SHA-256, blockers,
  warnings and `execution_authorized: false`;
- expose the same service through a local CLI command;
- keep all output public-safe and do not persist candidate text or private
  details.

## Inputs and outputs

Input is a local JSON file supplied explicitly to
`supervisor qualification-preflight`. It must contain only declared metadata,
not credentials, prompts, repository files, responses or runtime identifiers.

Output contains normalized public-safe metadata, scope digest, status
(`eligible_for_separate_review` or `blocked`), fixed check results and
`execution_authorized: false`.

## Authorization ladder

1. Prepare and inspect the offline preflight declaration.
2. Freeze and separately review a future Board for any real Agent or Provider.
3. Obtain exact user authorization for the displayed external scope.
4. Only a later implementation may consume execution approval.

Board 21 itself stops after step 1 and cannot start an Agent, Provider,
network endpoint, App Server, A2A, MCP, repository, worktree or model.

## Privacy rules

- no credentials or credential values;
- no personal home paths or machine-specific paths;
- no repository/worktree/private-project context;
- no prompt instances, responses, runtime database or Artifact body;
- only sanitized metadata and hashes may appear in terminal output;
- the input file is operator-owned local data and is not copied into Git.

## Threat model

The preflight must fail closed for missing required fields, malformed values,
credential-shaped text, personal paths, private-context declarations, write or
worktree permissions, missing cost/token/time/retry bounds, incomplete approval
ladder and attempts to set execution authority. A digest must change when any
validated scope field changes.

## Acceptance criteria

- valid synthetic declarations produce deterministic normalized output and a
  stable digest;
- missing identity, limits, approval stages or evidence policy are blockers;
- repository context, worktrees, writes, credentials and personal paths are
  rejected without echoing sensitive values;
- execution authority is always false;
- CLI uses the service and prints only the bounded result;
- no Provider, model, network, process, runtime DB or Artifact is touched;
- full offline tests, compilation, JSON validation, privacy scans and
  `git diff --check` pass.

## Explicit exclusions

No real Agent qualification, process start, login, actual-Model query,
Provider call, external endpoint, repository context, worktree, write/test/
merge, Artifact retention/purge, remote authentication/signing or dynamic
replanning is included.
