# Board 14 Plan: Controlled Local Multi-Agent Experiments

Date: 2026-08-31

Status: Board 14.0 and 14.1 preparation scope frozen before implementation

## Goal

Create a durable local experiment control plane, verify it completely with a
fake Manager and two fake Workers, and prepare one exact Codex Manager plus two
fake Worker candidate without invoking Codex.

Board 14 is not complete until a separately authorized real 14.1 run occurs.

## Sequence

### Board 14.0: offline control-plane experiment

- one deterministic fake Manager;
- two distinct local mock Workers;
- one current Board 13 team snapshot;
- exact local approval before simulation;
- persisted events and hash/count/assertion evidence;
- zero Adapter invocations and zero network requests.

### Board 14.1: Codex Manager candidate preparation

- one registered `cli` or `codex_app_server` Manager;
- two distinct local mock Workers;
- synthetic prompt only;
- zero files and zero Artifacts;
- read-only sandbox;
- tools, workspace writes and Git disabled;
- exactly one allowed future call, zero automatic retries and sequential
  execution;
- exact command, Model, working directory, disabled features, timeout, response
  limit, token limit and cost limit in the approved SHA-256 scope.

The repository contains no Board 14 real executor. A `real_codex` experiment
can be prepared, inspected, approved and armed, but cannot invoke an Adapter.

## State and approval

```text
pending
  -> approved / rejected / stopped
approved
  -> armed / stale / stopped
armed synthetic_fake
  -> running -> completed / failed
armed real_codex
  -> stop; wait for a later exact real-run authorization and implementation
```

Approval binds:

- current team snapshot ID and SHA-256;
- Manager and Worker Agent/Model identities and configuration hashes;
- exact prompt hash and UTF-8 byte count;
- transport command, working directory, Model, sandbox and approval policy;
- permissions, call/retry/concurrency/timeout/response/token/cost limits;
- expected two-task JSON-plan contract;
- deterministic stop rules.

Fresh readiness evidence, team configuration drift, Agent/Model changes,
prompt changes or scope changes make the experiment stale.

## Threat model

- a plan-level approval is mistaken for authorization to call a model;
- the Manager, Model, command, working directory or disabled features change;
- private paths, credential-shaped text, files or Artifacts enter the scope;
- an Agent requests tools, workspace writes, Git or interactive escalation;
- the host performs a redirect, auxiliary request, retry or extra call;
- raw model output or machine-specific diagnostics enter Git;
- a prior approval is replayed after configuration or readiness drift.

## Excluded

- any real Codex, Reasonix, ZCode or Provider call;
- repository, workspace, repair, evaluation or other private-derived context;
- file or Artifact transfer;
- tool execution, workspace write, Git action, merge, deployment or publish;
- parallel real Agents;
- Web UI changes;
- GitHub push, tag or Release.

## Acceptance criteria

- Board 14.0 completes with exactly two fake Worker tasks and zero external
  calls;
- Board 14.1 prepares a disabled exact Codex candidate and stops pending;
- a wrong digest cannot approve a candidate;
- the real candidate cannot run through the fake simulator;
- private context, permission expansion, retries and non-mock Workers fail;
- team or Agent/Model drift makes an approval stale;
- public examples keep `invoke_enabled: false`;
- focused and complete offline tests, compilation, JSON validation, current
  tree scan and reachable-history privacy scan pass;
- one local-only preparation commit is created with no push or tag.
