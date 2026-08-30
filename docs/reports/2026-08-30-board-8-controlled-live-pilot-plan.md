# Board 8 Plan: Controlled Live-Model Pilot and Outbound Context Approval

Date: 2026-08-30

Status: acceptance scope frozen before implementation

## Goal

Establish one narrow, reviewable path for a real Codex App Server pilot without
claiming that a live endpoint has been verified. The initial path is limited to
one read-only architect role on a synthetic project. The manager and reviewer
remain local `mock` roles.

No repository content, private downstream-project material, credentials or
derived private information may be sent during the initial synthetic pilot.
Any later repository-context pilot requires a separate Board 8 review and
explicit user confirmation for the exact outbound context of that invocation.

## Frozen acceptance scope

1. A Codex App Server invocation must stop before process startup unless an
   exact outbound-context manifest has been approved once.
2. The manifest must bind approval to the endpoint, prompt, resolved `cwd`,
   model, sandbox, approval policy and exact UTF-8 byte count. A changed scope,
   wrong endpoint or replayed approval must fail locally.
3. The first allowed configuration must have exactly one Codex App Server
   Agent, `sandbox: "read-only"`, a mock manager, a mock reviewer, no other
   enabled remote Agent and no enabled MCP tool execution.
4. The initial source class is `synthetic` only. Repository source class,
   Artifact transfer and derived private context are excluded from the Board 8
   live path.
5. The local user can inspect the exact prompt, transport context and a
   non-secret inventory before approval. Approval requires entering the
   displayed combined scope SHA-256.
6. Offline tests use only the local fake App Server. They must prove pending,
   approved, consumed, rejected and blocked transitions, prompt mismatch,
   exclusion rules and the one-role pilot topology.
7. Protocol events must retain manifest ID, digest and byte count rather than
   duplicating the outbound prompt. The exact prompt remains only in ignored
   local runtime state to support the user's preview.

## Threat model and controls

| Threat | Board 8 control |
| --- | --- |
| Accidental external invocation | Existing `invoke_enabled: true` gate plus mandatory one-time context approval before App Server startup |
| Scope drift after review | Approval is tied to one combined prompt/transport SHA-256; any scope change fails |
| Repository or private data in first pilot | `synthetic` source only; `repository` source is rejected by controlled-pilot validation |
| Credential or identity disclosure | Environment-only credentials; content regex excludes common credential headers, private keys and Windows/POSIX home paths |
| Artifact over-sharing | Initial pilot permits zero Artifacts and zero Artifact bytes |
| Excessive context | Maximum 0 files, 8,192 prompt bytes, 0 Artifacts and 0 Artifact bytes in the example |
| Replay of approval | Approved manifest is atomically marked consumed before transport startup |
| Model requests command/file access | App Server approval requests remain recorded and declined |
| Sensitive content leaked into public evidence | Prompt text stays in ignored runtime SQLite; protocol audit records only bounded manifest metadata |
| Pilot failure after approval | Session becomes failed with local diagnostics; no automatic retry, role expansion, write permission or fallback external call |

## Exact outbound-context inventory

For every proposed call, the local manifest records:

- endpoint and local Agent identity;
- source class;
- SHA-256 and UTF-8 byte count for the full rendered prompt;
- resolved `cwd`, model, sandbox and approval policy plus their combined digest;
- individually hashed, byte-counted system/request, goal, instruction and
  prior-context sections;
- Artifact name, media type, digest and byte count when policy permits any;
- all configured limits and exclusion-pattern identifiers;
- pending/approved/rejected/consumed/blocked status and local timestamps.

The local `interop context <MANIFEST_ID> --show-prompt` command displays the
actual prompt before approval. This command is local inspection only; it does
not contact an App Server or model host.

## Exclusions

The initial pilot rejects:

- every Artifact and every selected input file;
- source class `repository`;
- credentials, authorization headers, bearer-token-like assignments and private
  key blocks;
- Windows and POSIX home-directory path patterns;
- prompt totals above the configured byte cap;
- non-read-only sandboxes;
- non-mock manager/reviewer configurations;
- another enabled Codex/A2A Agent or enabled MCP server.

## Deliberate failure and rollback behavior

No destructive rollback is needed because Board 8 creates only ignored local
runtime rows before a live call. A rejection, policy violation, digest mismatch,
expiry/future extension failure or transport failure leaves the worktree
unchanged and does not retry automatically. A consumed approval cannot be
reused. The operator must create and review a fresh exact manifest for any
changed scope.

## Deferred work

Board 8 does not add Git worktrees, write permission, merge authority,
reviewer-writer loops, a second real Agent family, real A2A/MCP verification,
repository-context authorization UI, or any release/deployment capability.

## Post-pilot privacy correction

The first live synthetic run revealed that the original manifest covered the
Turn prompt but not `thread/start.cwd`. Because Codex may include working
directory information in upstream environment context, the acceptance scope is
amended:

- the exact manifest must include resolved `cwd`, model, sandbox and approval
  policy;
- one approval digest binds prompt and transport metadata together;
- Windows and POSIX personal home paths are blocked before process startup;
- public configuration obtains the synthetic working directory from
  `MODEL_COUNCIL_SYNTHETIC_CWD`;
- the deterministic pre-start correction may close with automated local
  evidence under `docs/PRIVACY.md`; another live call is optional because the
  control does not depend on provider behavior.
