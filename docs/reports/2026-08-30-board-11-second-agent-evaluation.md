# Board 11 Report: Second Agent Family and Objective Evaluation

Date: 2026-08-30

Status: accepted and complete

## Objective

Integrate exactly one second real Agent family without changing the existing
manager, reviewer, workspace, repair or merge topology. Compare its declared
capability with one objective, project-neutral synthetic task under exact
outbound-context approval.

The frozen candidate, task, metrics and limits are recorded in
`docs/reports/2026-08-30-board-11-second-agent-evaluation-plan.md`.

## Delivered

### Frozen DeepSeek candidate

`config.evaluation.example.json` defines:

- one DeepSeek `openai_compatible` Responses Agent;
- endpoint `https://api.deepseek.com`;
- model `deepseek-v4-flash`;
- role `synthetic_evaluator`;
- credential reference `MODEL_COUNCIL_DEEPSEEK_API_KEY`;
- `invoke_enabled: false`;
- zero files and zero Artifacts;
- 4,096 bytes of prompt plus transport context;
- a 16,384-byte HTTP response limit;
- a 30-second deadline.

The tracked configuration contains no credential value.

### Exact single-use external approval

The OpenAI-compatible Adapter now uses the same local manifest discipline as
the controlled Codex pilot:

- render a path-free outbound prompt;
- bind endpoint, request URL, model, API style, payload fields, static header
  shape, credential environment-variable name and response limit;
- require an approved, unused scope SHA-256;
- consume the approval once before transport;
- reject non-loopback HTTP and all redirects.

Changing the prompt or transport metadata makes the manifest unusable.
`invoke_enabled`, credential presence or any Board 8-10 permission is not a
substitute for the exact approval.

### Objective evaluation evidence

`EvaluationService` persists:

- `evaluation_runs`;
- `evaluation_cases`;
- the linked outbound manifest and usage-ledger event.

The fixed task asks for exactly the 16-byte token
`MC-EVAL-ORBIT-42`. Deterministic assertions cover exact text, output SHA-256,
output bytes, duration, zero files, zero Artifacts, one call and ledger
persistence. Wrong output, response overflow, redirect, missing permission or
transport failure does not trigger a retry, fallback, route change, worktree
action or merge.

Evaluation tables retain hashes, byte counts, assertions, failure class and
ledger references rather than response text.

### Local CLI

Board 11 adds:

```text
evaluation prepare
evaluation list
evaluation show
evaluation context
evaluation run
```

The exact prompt is hidden unless `evaluation context --show-prompt` is used.
Approval requires the displayed combined scope digest. Execution requires the
matching manifest ID.

## Verification

```text
81 tests passed
Python compilation passed
All tracked JSON configuration files parsed
Full-history privacy scan passed
git diff --check passed
runtime/ and runtime/council.db are ignored
Git author uses the public GitHub noreply address
```

Eight Board 11 tests cover:

- the public candidate configuration;
- exact CLI prompt display;
- zero-file/zero-Artifact manifest limits;
- independent `invoke_enabled` enforcement;
- loopback Responses payload and provider-reported usage;
- wrong-output objective failure without retry;
- response-size failure without retry;
- redirect, plaintext credential, non-HTTPS and unfrozen-endpoint rejection.

All HTTP execution tests use temporary `127.0.0.1` fake servers. No external
model, repository context, file, Artifact, repair bundle, worktree evidence or
private-derived material was sent.

## Authorized live synthetic evaluation

The user inspected and explicitly authorized one exact 937-byte scope. The
manifest was consumed once against the frozen DeepSeek Responses endpoint and
model. The request contained 563 bytes of fixed synthetic prompt, 374 bytes of
transport metadata, zero files, zero Artifacts and no repository, workspace or
repair context. No credential value appeared in the manifest or output.

The endpoint authenticated and returned a completed Responses result. Local
evidence recorded:

```text
Requests: 1
Duration: 1,009 ms
Input tokens: 200
Output tokens: 36
Total tokens: 236
Token source: provider_reported
Cost source: unavailable
Response bytes: 131
```

The response did not equal the required 16-byte token. Exact text, SHA-256 and
byte-count assertions therefore failed. Duration, zero-file, zero-Artifact,
single-call and ledger assertions passed. No response text is included in this
report, and no retry or fallback was attempted.

This is an accepted objective evaluation outcome: Board 11 required a
controlled second-family integration and evidence that can contradict a
declared capability. It did not require weakening the metric until the
candidate passed.

## Privacy review

`PRIV-012` records the evaluation prompt/response evidence boundary. The
prepared live candidate manifest contains only the fixed public synthetic
prompt and frozen transport metadata. Its superseded pre-template manifest was
explicitly rejected locally.

The credential remained an environment variable and was never printed,
persisted in tracked configuration or copied into the report. The approved
manifest was consumed once. Response text remained transient; only its hash,
byte count, assertions and ledger evidence are retained locally.

Board 12 may begin only after this report, final verification, commit, push and
independent public-remote verification complete.
