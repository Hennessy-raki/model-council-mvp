# Board 8 Report: Controlled Live-Model Pilot and Outbound Context Approval

Date: 2026-08-30

Status: accepted and complete

## Objective

Prepare one narrowly controlled real-model path without sending repository
content, derived private material or credentials to an external model host.
The path is intentionally limited to one read-only Codex App Server architect
role on a synthetic project, while manager planning, independent review and
final synthesis remain on local mocks.

The acceptance scope and threat model were frozen before implementation in
`docs/reports/2026-08-30-board-8-controlled-live-pilot-plan.md`.

## Delivered

### Exact outbound-context gate

Every configured Codex App Server Agent now requires an `outbound_context`
policy and an explicit `cwd` or `cwd_env`. Before a Turn starts, Model Council:

1. renders the prompt without local run IDs or Artifact paths;
2. combines it with resolved `cwd`, model, sandbox and approval policy;
3. evaluates source class, combined byte limit, Artifact limit and exclusion
   patterns, including personal home-directory paths;
4. stores an ignored local manifest with prompt and combined-scope digests,
   section digests, byte counts, limits and status;
5. stops before App Server process startup unless the exact manifest has a
   pending-to-approved local decision;
6. atomically consumes the approval before startup.

An approval cannot target a different endpoint, prompt, transport context,
changed byte sequence or second invocation.

### Local review and audit evidence

The operator may list local manifests and inspect the exact prompt:

```powershell
python -m model_council interop contexts --config <LOCAL_CONFIG>
python -m model_council interop context <MANIFEST_ID> --show-prompt `
  --config <LOCAL_CONFIG>
```

Approval requires the displayed combined `approval_sha256`:

```powershell
python -m model_council interop context <MANIFEST_ID> `
  --approve-sha256 <DISPLAYED_APPROVAL_SHA256> --config <LOCAL_CONFIG>
```

For an approved synthetic-only manifest, a resumed run supplies
`--outbound-manifest <MANIFEST_ID>`. Protocol-event audit evidence records
only the manifest ID, digest and byte count rather than copying prompt text.
Exact prompt text stays in ignored local runtime SQLite for user preview.

### Controlled pilot topology

`config.pilot.example.json` is disabled by default and constrains the first
live path to:

- exactly one Codex App Server architect;
- `sandbox: "read-only"` and declined interactive approvals;
- a mock manager and mock reviewer;
- no other enabled Codex/A2A Agent and no enabled MCP server;
- source class `synthetic`;
- zero files, zero Artifacts, zero Artifact bytes and an 8,192-byte combined
  prompt/transport cap;
- a resolved working directory from `MODEL_COUNCIL_SYNTHETIC_CWD`.

The controlled-pilot validator rejects repository source class and any topology
expansion. The public example contains no credential value or real endpoint.

## Verification

```text
55 tests passed
```

New offline coverage verifies:

- a pending manifest blocks App Server startup;
- the exact prompt can be inspected locally and approved only with its exact
  digest;
- approval is consumed once and cannot be replayed;
- excluded credential-like context is blocked;
- invalid approval confirmation is rejected;
- changed App Server transport context is rejected;
- personal home-directory working paths are rejected;
- non-mock manager/reviewer, another enabled remote Agent, enabled MCP and
  repository source are rejected;
- an approved manifest resumes a synthetic one-Codex-role run through mock
  review and synthesis;
- existing Board 1 through 7 local-fake protocol coverage continues to pass.

The full suite, Python compilation and JSON configuration parsing were run
locally. Full-history privacy scanning remains required before push.

## Live synthetic pilot evidence

After the user reviewed and explicitly approved the exact Turn prompt, one real
Codex App Server architect participated in a complete functional run:

- the outbound context was synthetic, 890 UTF-8 bytes, zero files and zero
  Artifacts;
- the approved SHA-256 manifest was consumed exactly once before process
  startup;
- the App Server used `sandbox: "read-only"` and `approval_policy: "never"`;
- no command-execution or file-change approval request occurred;
- one persistent Thread and one completed Turn were recorded;
- the architect task completed with a non-empty UTF-8 Artifact;
- the mock reviewer completed independent review;
- the mock manager completed final synthesis;
- the run had no failed or blocked task;
- local Turn audit stored manifest ID, digest and byte count instead of the
  outbound prompt body;
- the ignored synthetic working directory remained empty and the tracked Git
  worktree remained clean.

No file, Artifact, repository content, credential, private-derived detail, A2A
request or MCP request was intentionally supplied. However, `thread/start`
also passed the absolute synthetic working directory to the local Codex App
Server. Codex may include that working directory in upstream model environment
context. The original manifest did not display or bind this metadata, so the
run cannot be accepted as a complete privacy verification. The model output did
not reproduce the path, but absence from output does not prove non-disclosure.

## Post-pilot findings and mitigations

The live Turn succeeded, but three findings were recorded:

1. The original approval manifest covered only Turn text and omitted
   `thread/start.cwd`, model, sandbox and approval policy. The gate now binds
   these fields into one combined scope digest and rejects personal home paths.
   Public examples use `MODEL_COUNCIL_SYNTHETIC_CWD`.
2. App Server startup attempted an unrelated featured-plugin catalog refresh
   and received HTTP 401. The prompt was not part of that request. Public pilot
   examples now explicitly disable `plugins`, `remote_plugin` and `apps`. The
   installed CLI accepts those feature flags; no second live Turn was made.
3. App Server emitted `thread/tokenUsage/updated`, but the generic sanitizer
   redacted the `tokenUsage` container, so the live ledger used estimates. The
   sanitizer now preserves an explicit allowlist of numeric token metrics while
   continuing to redact credential-like token fields. The Adapter normalizes
   the latest Turn breakdown into provider-reported ledger usage. Local fake
   protocol and redaction tests verify the correction.

These corrections are offline-verified. The combined-scope and personal-path
controls execute locally before App Server process startup, so their
effectiveness does not depend on provider behavior. Under the privacy triage
policy, this deterministic evidence is sufficient to close Board 8. The report
does not claim that a second live Turn revalidated the mitigations.

## Continuing live boundary

Committed examples keep `invoke_enabled: false`. Every future live attempt
requires a fresh exact prompt-plus-transport manifest, explicit user
authorization and a generic working directory outside personal home paths.
Repository content or derived private material remains excluded. Board 8
is complete; an optional future live call must still use a fresh exact approval
but is not a prerequisite for Board 9.

The findings and disposition are recorded in `docs/PRIVACY_ISSUES.md`.

## Deferred

Board 8 does not include worktrees, write permission, repository-context
testing, repair loops, merge approval, another real Agent family, A2A/MCP live
verification, or product UI changes. Those remain later boards.
