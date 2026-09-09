# Board 23 Plan: Qualification Provenance Integrity and Revalidation

Date: 2026-09-09

Status: frozen for local offline implementation; no execution authority

## Contribution to PROJECT_GOAL

Board 23 strengthens the verification-to-authorization boundary. A
qualification preflight bound to a Supervisor role must remain internally
consistent and must still match the current Agent, Model and Provider registry
before readiness, snapshots or project-run approvals can proceed.

## Scope

- re-compute the stored qualification scope SHA-256 on every read;
- compare stored preflight identity with the current Agent, Model and Provider
  registry relationship;
- expose bounded integrity status and failure codes;
- make tampered or identity-drifted preflights fail closed for non-mock roles;
- include integrity evidence in snapshot and project-run approval provenance;
- preserve existing mock/synthetic flows and existing Board 21/22 contracts;
- add CLI/Web read-only projection and offline regression tests.

## Inputs and outputs

Inputs are existing local runtime qualification records and current registry
metadata. No new candidate format, prompt, repository context or external
transport is introduced.

Outputs contain only role, status, bounded failure code and SHA-256 metadata.
Raw scope content remains runtime-only and execution authority remains false.

## Authorization ladder

Board 23 only revalidates previously bound local metadata:

1. read the current local preflight;
2. verify digest and registry identity;
3. fail closed or allow the existing local snapshot/approval flow.

No process, Provider, model, network, App Server, A2A or MCP call is allowed.

## Privacy and storage

No new private data is collected. Existing sanitized scope metadata remains
ignored runtime state. Tracked files contain only generic schemas, tests and
bounded status wording; `runtime-board14/` remains unread and excluded.

## Threat model

Fail closed for runtime scope tampering, digest mismatch, missing identity,
Agent/Model/Provider drift, disabled registry records or malformed stored
qualification data. Do not echo rejected scope values.

## Acceptance criteria

- an intact matching preflight reports `current` integrity;
- modified scope JSON reports a bounded integrity failure and blocks readiness;
- Agent, Model or Provider drift reports identity failure and blocks readiness;
- snapshot and project-run approval creation reject invalid qualification state;
- mock-only synthetic flows remain green;
- CLI and Web expose only bounded qualification status;
- no external call, process, repository, worktree, Git or Artifact operation.

## Explicit exclusions

No real Agent qualification, login, actual-Model query, Provider/model call,
network, remote authentication/signing, repository context, writing Agent,
worktree, Git merge, Artifact purge, dynamic replanning or pause/resume UX.
