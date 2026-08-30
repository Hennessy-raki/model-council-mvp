# Privacy and Public Repository Safety

Model Council is developed for publication in a public GitHub repository.
Local identity, credentials and private project material must therefore remain
outside the versioned repository.

## Never commit

- API keys, bearer tokens, refresh tokens, passwords or private keys;
- `.env` files or credential-store exports;
- absolute home-directory paths containing a real local username;
- personal email addresses unless the contributor intentionally publishes one;
- hostnames, account identifiers or machine-specific diagnostics that identify
  a private workstation;
- runtime databases, generated Artifacts, private prompts or copied user
  project content;
- local worktrees, diffs or logs from a private downstream repository.

Configuration examples must use environment-variable references and generic
placeholders. Runtime and discovery state remains local and ignored by Git.

## Privacy issue triage and recording

Record every privacy-related observation in `docs/PRIVACY_ISSUES.md`. Classify
it by the data at risk and the recipient:

- credential, private-key or private-project exposure is critical;
- personal or machine-specific data reaching GitHub or another party is high
  priority and must be fixed before the current board closes;
- correlatable but non-identifying metadata is medium priority;
- behavior carrying no personal, machine-specific, credential or
  private-project data is low priority and may be deferred.

Privacy work should be proportionate. Low-priority findings must be visible in
the register but should not delay unrelated product development. Deterministic
local gates may be accepted with automated local evidence when they prevent the
process or network request from starting; a repeated live call is not required
solely to retest such a gate.

## Required board-completion gate

After every development board:

1. inspect all changed and untracked files;
2. run the full automated test suite;
3. run `python scripts/privacy_scan.py --history`;
4. inspect `git diff` and the staged diff before committing;
5. inspect tracked filenames and `.gitignore`;
6. check commit-author metadata for an intentionally public or GitHub noreply
   address;
7. commit only after every finding is resolved or explicitly documented;
8. verify the pushed public commit contains no local runtime files.

The scanner reports only file, line and finding type. It deliberately does not
echo possible secret values.

## External model boundary

Repository contents and derived private-project details must not be sent to an
external model service without explicit user authorization. Discovery scans,
doctor checks and privacy scans must remain local and must not be treated as
authorization for a real model invocation.

## Interoperability boundary

Codex App Server, A2A and MCP configuration must keep credential values out of
JSON and SQLite. Store only environment-variable names. Non-loopback remote
endpoints require HTTPS and examples must use generic domains.

`invoke_enabled: true` is an execution gate, not consent to disclose arbitrary
repository contents. Obtain explicit user authorization for the exact live
endpoint and context before a pilot.

Interoperability sessions, Agent Cards, event payloads, MCP arguments and
approval records are local runtime state. Never commit the runtime database or
copy those records into a public report. MCP tool calls require a persisted
single-use approval even when the server itself is already configured.

## Local worktree evidence boundary

Worktree leases may contain absolute repository/worktree paths, user-defined
Agent identities, private filenames, source diffs, test commands and bounded
test output. Treat all of it as private local runtime data:

- create linked worktrees only below the configured ignored runtime root;
- never copy a worktree, runtime SQLite row, diff or test excerpt into this
  public repository or a public board report;
- use opaque generated Git branch names rather than Agent/user labels;
- retain only bounded diff/test excerpts and full-stream hashes;
- reject inline credential flags in persisted test command arrays;
- confirm `runtime/` and `runtime-*` remain ignored before public push;
- run the full-history scanner even though runtime data should never be staged.

If runtime evidence is accidentally committed or pushed, stop the active board,
remove it from the current tree and all reachable history, rotate any exposed
credential, assess whether private project content reached another party, and
verify the repaired public refs independently before continuing.

## Repair-loop evidence boundary

Repair goals, reviewer feedback, changed-file inventories, failure diagnostics
and review bundles are private downstream-project context. Keep them in ignored
runtime SQLite and local terminal output only.

Board 10 does not send review bundles through an Adapter or network transport.
Its automatic driver accepts injected local callbacks only. Connecting a real
writer or reviewer in a later board requires a new exact outbound-context
inventory and explicit authorization for the selected files, diff, test output,
goal and feedback. Worktree permission, `invoke_enabled`, an accepted repair
session or a prior synthetic pilot does not authorize that disclosure.

## Objective-evaluation evidence boundary

Board 11 evaluation manifests and results remain ignored local runtime data.
The tracked example freezes only public synthetic text, the public endpoint and
model identifiers, byte/count limits and the credential environment-variable
name.

- The candidate receives zero files and zero Artifacts.
- Prompt plus transport metadata is limited to 4,096 UTF-8 bytes.
- The HTTP response body is limited to 16,384 bytes before JSON parsing.
- Non-loopback endpoints require HTTPS and HTTP redirects are rejected.
- Evaluation tables store output SHA-256 and byte count, not response text.
- The exact prompt is displayed only through an explicit local CLI option.
- A real request requires `invoke_enabled: true` and one approved, unused
  manifest whose prompt and transport digest still match.

Never copy local manifests, provider responses, usage payloads or evaluation
database rows into a public report. Any future repository-derived evaluation
requires a new policy, new exact manifest and separate user authorization.
