# Board 14.6 Plan: Privacy-Safe Usage Failure Diagnostics

Date: 2026-08-31

Status: frozen before implementation

## Trigger

The second separately authorized Board 14 real Manager attempt consumed its
fresh start approval and failed closed after the Manager returned a structurally
valid two-task JSON plan. The executor could not distinguish whether
provider-reported usage was absent, incomplete, or above the hard 2,000-token
limit because failed turns intentionally retained no response or usage
evidence.

The failed experiment and consumed approval remain terminal. This board does
not retry, inspect a response body, or reconstruct the prior provider stream.

## Goal

Record a bounded, privacy-safe local diagnostic when the controlled executor
rejects a completed Manager turn for unavailable, incomplete, or over-limit
usage. The diagnostic must make the failure class reviewable without retaining
raw JSONL, prompts, response text, credentials, stderr, stdout, or a protocol
transcript.

## Scope

- retain only the existing three usage locations:
  - `thread/tokenUsage/updated.params.tokenUsage.last`;
  - `thread/tokenUsage/updated.params.tokenUsage.total`; and
  - `turn/completed.params.turn.usage`;
- classify a usage-gate failure as `unavailable`, `incomplete`, or
  `exceeded_limit`;
- for each observed source, retain only its stable source label and semantic
  input/output/total-field presence;
- retain non-negative normalized input/output/total counts only when all three
  are complete and only when needed to explain an over-limit failure;
- record the hard token limit alongside an `exceeded_limit` diagnostic;
- keep the diagnostic in the existing ignored runtime SQLite evidence store;
- add local fake-App-Server tests for unavailable, incomplete, and
  over-limit diagnostics, including assertions that prompt/response text is
  absent;
- preserve one process, one turn, zero retries, strict approval rejection,
  source-integrity binding, and every existing hard limit.

## Excluded

- real App Server startup, PackyAPI access, Provider request, or model call;
- a retry or replay of either consumed Board 14 real start approval;
- acceptance of partial, estimated, negative, boolean, or otherwise
  unverified usage;
- raw JSONL, response, prompt, stderr, stdout, transcript, credential, file,
  Artifact, workspace, Git, or private-project retention;
- changes to the 2,000-token or USD 0.25 limit;
- push, tag, GitHub Release, package publishing, or deployment.

## Acceptance criteria

1. A completed turn without any recognized usage records a failed local
   diagnostic classified as `unavailable`.
2. A recognized usage source missing a required semantic token field records
   a failed local diagnostic classified as `incomplete`.
3. Complete usage above the frozen hard limit records a failed local
   diagnostic classified as `exceeded_limit`, with only normalized numeric
   usage and the limit.
4. No failed usage diagnostic contains prompt, response, task, JSONL,
   transcript, stdout, stderr, credential, or private-path content.
5. All supported complete usage locations continue to pass within limits, and
   a direct unapproved `tokenUsage` location is not accepted.
6. Focused and complete offline tests, compilation, tracked JSON validation,
   current-tree privacy scan, reachable-history privacy scan, and
   `git diff --check` pass.
7. One local-only commit is created; no push, tag, or Release is created.

## Next real-pilot boundary

Only after offline acceptance may a future new candidate be prepared. It must
repeat every experiment and start-approval gate. This board grants no new
real-execution authority.
