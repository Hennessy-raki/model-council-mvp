# Board 22 Plan: Qualification Preflight Binding

Date: 2026-09-03

Status: frozen for local offline implementation; no execution authority

## Contribution to PROJECT_GOAL

Board 22 closes the control-plane gap between the standalone Board 21
qualification preflight and the Supervisor lifecycle. A non-mock Agent cannot
enter a current team snapshot or a project-run approval without a matching,
current qualification preflight.

## Scope

- persist one sanitized qualification-preflight summary per Supervisor role in
  ignored local SQLite;
- bind the preflight Agent/Model/Provider identity to the configured role;
- include preflight ID, status and SHA-256 in team snapshots and project-run
  approval provenance;
- make non-mock roles fail closed until a current preflight is bound;
- stale the preflight and downstream approvals when role binding or preflight
  scope changes;
- add CLI binding and read-only Web projection using the same service;
- preserve existing mock-only synthetic flows without requiring a redundant
  preflight;
- retain no candidate file, prompt, response, credential, private path or
  external evidence.

## Inputs and outputs

The CLI accepts a local Board 21 candidate file and role. The service evaluates
it, verifies the normalized scope digest and identity match, then stores only
the sanitized normalized scope and digest in ignored runtime state.

Snapshots and project-run approvals expose only bounded qualification
provenance: role, preflight ID, status and digest. Execution authority remains
separate and false.

## Authorization ladder

1. Run the offline Board 21 preflight.
2. Bind the eligible result to one configured non-mock role.
3. Re-run local readiness and create a current team snapshot.
4. Request and approve one exact project-run scope.
5. A future Board may separately authorize real Agent execution.

Board 22 itself cannot start a process or invoke any endpoint.

## Privacy and storage

Only runtime-local sanitized scope metadata and hashes are stored. Candidate
files remain operator-owned and are never copied into Git. Credentials,
personal paths, private project context, repository/worktree/write scope,
prompts, responses, Artifacts and `runtime-board14/` remain prohibited.

## Threat model

Fail closed for role/identity mismatch, invalid or tampered digest, stale
preflight, changed role binding, missing preflight on a non-mock Agent,
execution-authority claims, or approval reuse after drift.

## Acceptance criteria

- non-mock roles without a current preflight are not ready;
- an eligible matching preflight can be bound once and appears in snapshots;
- mismatched identity and tampered digest are rejected without echoing values;
- changing the role binding or preflight stales pending project approvals;
- project-run approval provenance contains the qualification digest;
- mock-only existing tests remain compatible;
- CLI and Web use the same Supervisor service projection;
- no Provider, model, network, process, repository, worktree, Git or Artifact
  operation occurs.

## Explicit exclusions

No real Agent qualification, login, actual-Model query, Provider/model call,
remote authentication/signing, repository context, writing Agent, worktree,
Git merge, Artifact purge, dynamic replanning or pause/resume UX.
