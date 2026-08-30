# Board 8 Report: Controlled Live-Model Pilot and Outbound Context Approval

Date: 2026-08-30

Status: accepted offline control implementation; live invocation not executed

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
policy. Before a Turn starts, Model Council:

1. renders the prompt without local run IDs or filesystem paths;
2. evaluates source class, byte limit, Artifact limit and exclusion patterns;
3. stores an ignored local manifest with the exact prompt, section digests,
   prompt SHA-256, byte count, limits and status;
4. stops before App Server process startup unless the exact manifest has a
   pending-to-approved local decision;
5. atomically consumes the approval before startup.

An approval cannot target a different endpoint, different prompt, changed byte
sequence or second invocation.

### Local review and audit evidence

The operator may list local manifests and inspect the exact prompt:

```powershell
python -m model_council interop contexts --config <LOCAL_CONFIG>
python -m model_council interop context <MANIFEST_ID> --show-prompt `
  --config <LOCAL_CONFIG>
```

Approval requires the displayed SHA-256:

```powershell
python -m model_council interop context <MANIFEST_ID> `
  --approve-sha256 <DISPLAYED_SHA256> --config <LOCAL_CONFIG>
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
- zero files, zero Artifacts, zero Artifact bytes and an 8,192-byte prompt cap.

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
- non-mock manager/reviewer, another enabled remote Agent, enabled MCP and
  repository source are rejected;
- an approved manifest resumes a synthetic one-Codex-role run through mock
  review and synthesis;
- existing Board 1 through 7 local-fake protocol coverage continues to pass.

The full suite, Python compilation and JSON configuration parsing were run
locally. Full-history privacy scanning remains required before push.

## Live-pilot boundary

No real Codex App Server, model, A2A endpoint, MCP server or other external
service was called for this board. `invoke_enabled` remains false in all
committed examples.

Before a real synthetic pilot, the user must be shown the exact prompt for the
new manifest and explicitly authorize that specific context. Repository content
or derived private material remains excluded; it requires a separate explicit
review and authorization rather than a reused Board 8 approval.

## Deferred

Board 8 does not include worktrees, write permission, tests against a live
endpoint, repair loops, merge approval, another real Agent family, A2A/MCP
live verification, or product UI changes. Those remain later boards.
