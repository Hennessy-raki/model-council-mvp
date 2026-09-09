# Board 24 Plan: Real-Agent Qualification Authorization Package

Date: 2026-09-09

Status: frozen for offline preparation only; no execution authority

## Contribution to `PROJECT_GOAL`

Board 24 prepares the missing handoff between local qualification metadata and
the user's exact authorization for one real Agent. It does not perform the
qualification. It makes the future request reviewable before any process,
Provider, model, network or private project context can be used.

## Business objective

The operator must be able to inspect one narrowly scoped Agent qualification
request and distinguish declared registry identity from observed identity,
local readiness evidence from real qualification evidence, and an approval
package from execution authority.

The first candidate is the read-only architecture role `codex_architect`,
using the configured `codex-local` Provider and `codex-configured-default`
Model. The configured Model remains unresolved until a separately authorized
observation identifies the actual Model.

## Scope

- define an offline authorization-package schema and bounded display;
- bind Agent, Provider, Model, role, command-array digest and qualification
  policy to existing team-snapshot and project-run approval provenance;
- require an explicit, resolved working directory at authorization time without
  storing or displaying a personal absolute path in tracked files;
- require read-only permissions, synthetic-only context, zero files,
  zero Artifacts, no worktree, no Git and no tools;
- require explicit limits for input/output/total tokens, cost currency and
  stop/retry/timeout behavior;
- produce `user_confirmation_required` when actual Model, process, login,
  permission, version, protocol or connectivity evidence is missing;
- expose only bounded, privacy-safe package status through shared service,
  CLI and Web projections.

## Inputs and outputs

Inputs are existing local registry records, current qualification integrity
state, team snapshot provenance and a future operator-supplied exact scope.
Tracked examples use placeholders such as `<EXACT_WORKING_DIRECTORY>`.

Outputs contain identities, digests, bounded status codes, limits and approval
state. Prompts, responses, credentials, runtime database values, private paths
and private project content remain local ignored state or are absent.

## Authorization ladder

1. Prepare and validate the package offline; no process or Adapter starts.
2. Display the exact redacted scope, including command digest, model field,
   resolved working-directory category, permissions, limits and exclusions.
3. Require the user to independently authorize that exact package.
4. Revalidate registry identity, qualification digest, team snapshot, goal and
   package digest immediately before any future execution board.
5. Consume execution authority once; stale, changed or reused approvals fail
   closed.

This plan does not grant step 3 or step 4 authority.

## Threat model

Fail closed for missing or ambiguous actual Model identity, missing process or
login evidence, permission expansion, personal-path disclosure, command drift,
registry drift, stale snapshots, changed goals, missing limits, reused
approvals and concurrent consumption. Never infer execution permission from
doctor, readiness, login, connectivity or prior approval evidence.

## Acceptance criteria

- package schema is deterministic and hashable;
- no tracked file contains a personal absolute path or runtime value;
- package status distinguishes declared, observed, confirmed and unknown facts;
- all missing real evidence yields `user_confirmation_required`;
- stale-on-drift and single-use approval semantics remain intact;
- CLI and Web use the same service projection;
- offline tests, compilation, JSON validation and both privacy scans pass;
- no Provider, model, process, network, App Server, A2A or MCP invocation.

## Explicit exclusions

No real Agent start/connect/attach, login query, actual-Model query, Provider
call, App Server, A2A, MCP, repository context, writing permission, worktree,
Git operation, Artifact retention/purge, remote authentication/signing,
dynamic replanning or expanded pause/resume UX.
