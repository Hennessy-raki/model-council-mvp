# Board 11 Plan: Second Agent Family and Objective Evaluation

Date: 2026-08-30

Status: acceptance scope frozen before implementation

## Goal

Add exactly one second real Agent family: DeepSeek through its
OpenAI-compatible Responses HTTP API. Its only Board 11 role is
`synthetic_evaluator`. It evaluates one fixed, non-repository synthetic task
and records local, objective evidence. Board 11 does not change manager,
reviewer, worktree, repair, merge, discard or product UI behavior.

## Frozen candidate and invocation boundary

| Field | Frozen value |
| --- | --- |
| Agent family | DeepSeek via `openai_compatible` HTTP Responses |
| Sole role | `synthetic_evaluator` |
| Endpoint | `https://api.deepseek.com` |
| Model | `deepseek-v4-flash` |
| Credential reference | `MODEL_COUNCIL_DEEPSEEK_API_KEY` only |
| API style | `responses` |
| Default execution state | `invoke_enabled: false` |
| External context source | `synthetic` only |
| Maximum outbound files | 0 |
| Maximum outbound Artifacts | 0 |
| Maximum Artifact bytes | 0 |
| Maximum prompt plus transport bytes | 4,096 |
| Maximum HTTP response bytes | 16,384 |
| Invocation count per prepared evaluation | 1 |
| Default response deadline | 30 seconds |
| Redirect policy | reject all HTTP redirects |
| Non-loopback transport | HTTPS only |

No credential value belongs in configuration, SQLite registry records, terminal
output, tests, reports or Git.

## Frozen synthetic task and objective metrics

The only task asks the Agent to return the following ASCII token exactly and
nothing else:

```text
MC-EVAL-ORBIT-42
```

Acceptance is deterministic:

1. exactly one configured `openai_compatible` candidate is selected for the
   evaluation;
2. the candidate has the `synthetic_evaluator` role and objective-evaluation
   capability;
3. the response equals the fixed 16-byte token, with matching SHA-256;
4. the request has zero files and zero Artifact references;
5. one approved manifest binds the rendered prompt and complete HTTP transport
   metadata: endpoint URL, request path, model, API style, request fields,
   static headers and credential environment-variable name;
6. the response completes within the configured 30-second deadline;
7. the existing usage ledger records one completed or failed call with its
   observed/provider-reported measurement sources;
8. the local evidence store records only IDs, hashes, byte counts, assertion
   outcomes, timing/ledger references and failure class. It does not copy
   response text into public documentation.

The comparison baseline is the deterministic local oracle: the known expected
token, byte count and SHA-256. The candidate's declared capability is compared
with those observed assertions, rather than with self-reported confidence.

## Exact outbound authorization flow

The CLI must prepare a local evaluation before it can run:

1. render the fixed synthetic prompt and transport metadata;
2. persist a pending one-time manifest with total and per-section byte counts;
3. show the exact prompt only through an explicit local inspection command;
4. require the operator to confirm the displayed combined scope SHA-256;
5. require both the approved manifest ID and `invoke_enabled: true` to consume
   the approval and start the HTTP request.

An `invoke_enabled` setting, a prior Board 8 approval, a Board 9 worktree
permission, a Board 10 repair acceptance, a credential being present or a
prepared manifest does not authorize a different call. A changed endpoint,
model, API style, prompt, credential reference, request schema or byte count
makes the scope unusable.

Loopback fake-server tests may enable invocation only inside temporary test
configuration. They send the fixed token task to `127.0.0.1`, use a
test-only environment variable and never contact an external model service.

## Failure and privacy behavior

- Invocation stays blocked while `invoke_enabled` is false.
- Missing credentials, a non-approved or stale manifest, changed transport
  metadata, a network failure, an empty response, a wrong token and a deadline
  breach all record a bounded local failure outcome; there is no automatic
  retry, fallback, route change, worktree action or external disclosure.
- Non-loopback HTTP endpoints and all redirects are rejected so an
  Authorization header cannot move to an unapproved host.
- Repository files, Artifact files, repair bundles, worktree paths, prompts
  derived from private projects and real credential values are rejected before
  transport startup.
- Evaluation prompts and response text remain local runtime data. Public
  reports use only the fixed synthetic task and aggregate test evidence.

## Required verification

- local fake Responses-server tests for approval, exact payload, metrics,
  ledger evidence, failure recording and rejection paths;
- complete offline suite;
- Python compilation;
- `python scripts/privacy_scan.py --history`;
- staged-diff, tracked-file, `.gitignore` and commit-author review before
  public push.

## Deferred

The default implementation does not make a live external call. After offline
verification, the user may separately authorize exactly one displayed
synthetic scope. Board 11 does not introduce a second evaluation task, connect
repair evidence to an Adapter, change Board 8/9/10 approval rules or implement
Board 12 UI, backup or release scope.
