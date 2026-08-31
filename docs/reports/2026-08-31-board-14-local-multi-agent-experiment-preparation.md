# Board 14 Report: Offline Harness and Codex Candidate Preparation

Date: 2026-08-31

Status: Board 14.0 accepted; Board 14.1 prepared and pending exact authorization

## Delivered

`ExperimentService` adds a durable local state machine for controlled
multi-Agent experiments. It stores:

- one Board 13 team snapshot binding;
- exact Manager and two fake Worker Agent+Model identities;
- the synthetic prompt hash and byte count;
- exact transport, permission, budget and stop-rule scope;
- pending, approved, rejected, armed, running, completed, failed, stale and
  stopped states;
- bounded events and evidence.

Approval uses the canonical scope SHA-256. Arming revalidates the current team
snapshot, prompt and every Agent/Model identity. Drift marks an approved
experiment stale.

## Board 14.0 result

The deterministic simulator creates exactly two synthetic Manager tasks and
two fake Worker result hashes. It records:

- zero external calls;
- zero Adapter invocations;
- zero files and zero Artifacts;
- read-only permissions;
- tools, workspace writes and Git disabled;
- task count, identity separation, output byte counts and SHA-256 values.

No fake output body is stored in evidence.

## Board 14.1 preparation

The tracked candidate configuration:

- uses a Codex App Server Manager and two local fake Workers;
- remains `invoke_enabled: false`;
- disables `plugins`, `remote_plugin` and `apps`;
- requires a local synthetic working directory;
- allows synthetic text only, with zero files and zero Artifacts;
- binds one future call, zero retry, sequential execution, timeout,
  response-byte, token and cost limits.

The `real_codex` experiment path can prepare, display, approve and arm an exact
scope. It has no execution method and cannot use the fake simulator. No real
Codex process, Adapter, model or network request occurred.

## Verification

Ten focused tests cover:

- exact pending Codex candidate preparation;
- wrong-digest rejection and arm-only behavior;
- complete fake Manager/two-Worker simulation;
- personal-path, credential-shaped text and permission/retry rejection;
- two distinct mock Worker enforcement;
- Agent/Model identity drift;
- team-readiness evidence drift;
- CLI preparation without prompt disclosure;
- disabled, synthetic-only public Codex configuration;
- rejection when a real candidate is already invocation-enabled.

Final preparation verification passed:

```text
110 offline tests passed
Python compilation passed for model_council, tests and scripts
12 configuration/protocol JSON files parsed
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

## Privacy and security

Experiment prompts, commands, working directories, Agent identities, approval
scopes, events and evidence remain in ignored runtime SQLite. The public files
contain only generic synthetic examples. Evidence stores hashes, byte counts
and assertions rather than raw fake or future model output.

`PRIV-017` records the experiment-manifest boundary. A later real run must
retain the same private-runtime handling and must not copy provider responses
or machine-specific diagnostics into Git.

## Remaining Board 14 work

Before 14.1 can run, the user must review and authorize one exact local
manifest containing the actual Manager Agent, selected Model, command,
resolved synthetic working directory, prompt, limits and scope SHA-256.

Reasonix, ZCode, real concurrency and a three-Agent experiment remain outside
this preparation commit.
