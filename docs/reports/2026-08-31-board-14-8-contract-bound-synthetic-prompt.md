# Board 14.8 Report: Contract-Bound Synthetic Manager Prompt

Date: 2026-08-31

Status: accepted offline verification; Board 14 remains in progress

## Failure cause

The fourth separately authorized one-turn synthetic Manager attempt reached the
JSON task path but failed closed as `task_key_invalid`. Its response body was
not retained. The remaining SHA-256 and byte count are intentionally
non-reversible and are insufficient to diagnose any further response details.

The actionable root cause was product-side: the frozen prompt only requested
two independent synthetic tasks, but the local executor also required a
non-empty unique key, the two exact Worker identities, empty dependencies, and
no task-carried control fields. The requested output contract was therefore
underspecified relative to the enforced contract.

## Delivered

Board 14.8 introduces `manager_two_worker_plan_v2` and a single canonical
prompt builder:

- the prompt is generated from, and names, the two frozen mock Worker Agent
  IDs;
- it requires JSON only, exactly one `tasks` top-level property, exactly two
  task objects, and exact `key`, `agent`, and `depends_on` task fields;
- it requires a non-empty unique key, one task for each Worker, and
  `depends_on: []` exactly;
- it forbids permissions, tools, workspace, files, Artifacts, Git, commands,
  and other task control fields;
- preparation rejects any generic, edited, or otherwise non-canonical prompt;
- the expected-output portion of the SHA-256-bound scope records the v2 shape
  and Worker identity set.

The local response validator now matches the prompt: it rejects extra
top-level fields, extra or missing task fields, and `null` dependencies.
Existing privacy-safe diagnostics retain only failure class, v2 schema label,
output SHA-256, byte count, and the assertion that output text was not stored.

## Offline verification

The repository fake App Server fixture confirms the exact v2 prompt and emits
valid v2 JSON. Regressions cover:

- rejection of the earlier generic prompt;
- exact Worker identity binding;
- a successful complete v2 plan;
- invalid JSON, missing tasks, wrong task count, Worker mismatch, duplicate
  keys, dependencies, unsafe fields, extra top-level fields, and extra task
  fields;
- absent, incomplete, and over-limit usage; strict approval rejection;
  one-time consumption; and executor-integrity drift.

No test starts `codex.cmd`, contacts a Provider, accesses credentials, sends
network traffic, or invokes a model.

## Verification

```text
Focused Board 14 experiments: 22 tests passed
Full offline suite: 123 tests passed
Python compilation passed for model_council, tests and scripts
Tracked JSON validation passed (12 files)
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

## Next authorization boundary

All four prior Board 14 real synthetic attempts and their consumed approvals
remain terminal and must not be reused. Board 14.8 creates no candidate and
does not authorize a process start or model call.

Only after a new candidate is explicitly authorized for local preparation may
the v2 prompt be placed into ignored runtime state. Any subsequent real
attempt must pass the full separate experiment, arm, start-approval, approval,
and one-turn execution gates with zero retries.
