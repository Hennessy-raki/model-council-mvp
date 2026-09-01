# Privacy Issue Register

Last updated: 2026-08-31

Every privacy-related observation must be recorded here, even when it does not
block development. Remediation effort is proportional to whether personal,
machine-specific, credential, private-project or public-repository data is at
risk.

## Triage policy

| Priority | Meaning | Required action |
| --- | --- | --- |
| critical | Credential, private key, private repository content or directly exploitable access material may be exposed | Stop affected work; revoke/rotate access; remove public data and reachable history; investigate recipient retention before continuing |
| high | Personal identity, home path, machine-identifying data, private project metadata or runtime state may reach GitHub or another party | Record and fix the deterministic cause before the board closes; verify the block or redaction locally; run the full-history public scan |
| medium | Correlatable or operational metadata may leave the machine but does not directly identify a person, machine or private project | Record; fix when inexpensive or when it compounds another risk; may be scheduled without blocking unrelated work |
| low | Privacy-adjacent behavior carries no personal, machine-specific, credential or private-project data | Record; defer or accept with rationale; do not delay the active board solely for this item |

A live revalidation is required only when the privacy control depends on
external-service behavior. A deterministic local control that blocks the
transport before process or network startup may close with automated local
evidence.

## Register

### PRIV-001: Historical personal-path examples in public Git history

- Date found: 2026-08-29
- Channel: public GitHub reachable history
- Priority: high
- Data class: personal home-directory path
- Status: resolved
- Resolution: replaced the examples throughout reachable history, force-updated
  public `main`, and added full-history scanning as a board-completion gate.
- Evidence: `python scripts/privacy_scan.py --history` passes.
- Residual risk: hosting infrastructure may retain unreachable objects until
  garbage collection; no reachable public reference remains.
- Blocks development: no

### PRIV-002: App Server working directory omitted from first approval manifest

- Date found: 2026-08-30
- Channel: local Codex App Server and potentially its configured upstream model
  provider
- Priority: high
- Data class: absolute working-directory path containing machine/user context
- Status: resolved
- Resolution:
  - approval now binds prompt, resolved `cwd`, model, sandbox and approval
    policy into one scope digest;
  - Windows and POSIX personal home paths are rejected before App Server
    process startup;
  - Codex App Server configuration requires explicit `cwd` or `cwd_env`;
  - public pilot configuration uses `MODEL_COUNCIL_SYNTHETIC_CWD`.
- Evidence: automated tests cover changed transport context, missing/duplicate
  working-directory configuration and personal-path rejection; all 55 tests
  pass.
- Residual risk: the first functional live run may have disclosed its absolute
  synthetic working path. It sent no file, Artifact, credential or repository
  content. The path had no access capability.
- Blocks development: no; the deterministic pre-start control is fixed and
  locally verified.

### PRIV-003: App Server attempted a featured-plugin catalog request

- Date found: 2026-08-30
- Channel: Codex host auxiliary network request
- Priority: low
- Data class: no observed personal, machine-specific, credential or project
  content
- Status: mitigated and deferred
- Resolution: public pilot commands disable `plugins`, `remote_plugin` and
  `apps`.
- Evidence: the installed CLI accepts the feature flags; no additional live
  model call was made solely to retest a low-priority item.
- Residual risk: the host may add other auxiliary requests in future versions.
- Blocks development: no

### PRIV-004: Token-usage metrics were over-redacted

- Date found: 2026-08-30
- Channel: ignored local runtime audit data
- Priority: low
- Data class: non-sensitive numeric usage metrics
- Status: resolved
- Resolution: preserve an explicit metric allowlist while continuing to redact
  access, refresh, bearer and plural credential-token fields.
- Evidence: fake App Server and registry redaction tests pass.
- Residual risk: new protocol field names require future allowlist review.
- Blocks development: no

### PRIV-005: Worktree audit state contains machine and private-project context

- Date found: 2026-08-30
- Channel: ignored local runtime SQLite and linked worktree directories
- Priority: medium
- Data class: absolute paths, filenames, diffs, test commands and bounded test
  output
- Status: mitigated and accepted
- Resolution:
  - every linked worktree is created below the configured runtime root;
  - an in-repository runtime root must already be ignored before creation;
  - stdout/stderr and diff retention is bounded while complete hashes are
    stored;
  - public reports contain only synthetic aggregate evidence, never runtime
    rows or downstream content;
  - full-history privacy scanning and staged-diff review remain release gates.
- Evidence: synthetic tests create all worktrees in temporary repositories;
  repository `.gitignore` covers `runtime/` and `runtime-*`.
- Residual risk: a user can deliberately copy ignored runtime evidence into a
  tracked path; the board-completion review must detect that before push.
- Blocks development: no

### PRIV-006: Agent labels in generated Git branch names

- Date found: 2026-08-30
- Channel: Git refs that could be pushed accidentally
- Priority: medium
- Data class: user-defined Agent label that could contain correlatable or
  personal naming
- Status: resolved before public commit
- Resolution: generated branches use only
  `model-council/worktree-<opaque lease prefix>` and never include Agent IDs,
  usernames or repository names.
- Evidence: automated tests assert that the synthetic Agent label is absent
  from the generated branch.
- Residual risk: users can manually rename a local branch outside Model
  Council; merge scope validation rejects a worktree whose assigned branch
  changed.
- Blocks development: no

### PRIV-007: Synthetic test fixture used a generic non-noreply email

- Date found: 2026-08-30
- Channel: public test source
- Priority: low
- Data class: synthetic, non-personal email-shaped placeholder
- Status: resolved before public commit
- Resolution: replaced the generic `.invalid` fixture address with the fixed
  project GitHub-noreply identity already used for isolated checkpoints.
- Evidence: the full-history privacy scanner no longer reports the test file.
- Residual risk: none; no personal or machine-specific value was present.
- Blocks development: no

### PRIV-008: Runtime ignore check covered only the target repository

- Date found: 2026-08-30
- Channel: a public Git repository containing a custom `state_dir`
- Priority: high
- Data class: linked private-project worktree files, absolute paths and local
  runtime evidence
- Status: resolved before public commit
- Resolution: before creating a worktree, Model Council now discovers any Git
  repository that contains the configured runtime root and requires the
  generated path to be ignored there. The target repository is checked
  separately when applicable.
- Evidence: a synthetic cross-repository test rejects an unignored control
  repository, then succeeds only after its runtime root is ignored.
- Residual risk: a user can later remove an ignore rule or deliberately force
  add runtime content; staged-diff and full-history scans remain mandatory.
- Blocks development: no; the deterministic pre-creation gate is fixed.

### PRIV-009: Repair token-limit policy was over-redacted

- Date found: 2026-08-30
- Channel: ignored local repair policy state
- Priority: low
- Data class: non-sensitive numeric token limit
- Status: resolved before public commit
- Resolution: validated repair policy values and validated test command arrays
  use direct JSON serialization; untrusted Agent metadata and audit events
  continue through sensitive-value sanitization.
- Evidence: all Board 10 policy and budget tests pass.
- Residual risk: new numeric policy field names require explicit validation
  before bypassing generic sanitization.
- Blocks development: no

### PRIV-010: Repair sessions retain private project context

- Date found: 2026-08-30
- Channel: ignored local runtime SQLite and local CLI output
- Priority: medium
- Data class: repair goal, Agent identities, reviewer feedback, changed
  filenames, errors and bounded test/diff excerpts
- Status: mitigated and accepted
- Resolution:
  - repair state is stored only in the existing ignored runtime database;
  - feedback, diff, test and event payloads have explicit byte limits;
  - writer output is stored only as byte count, SHA-256 and sanitized metadata;
  - public reports contain synthetic aggregate evidence only.
- Evidence: synthetic tests use temporary repositories; staged and full-history
  privacy scans are release gates.
- Residual risk: local operators can display private evidence in their own
  terminal or deliberately copy it into a tracked file.
- Blocks development: no

### PRIV-011: Review bundles contain repository-derived evidence

- Date found: 2026-08-30
- Channel: potential future external Reviewer
- Priority: high
- Data class: changed filenames, source diff and test output from a downstream
  repository
- Status: mitigated for Board 10
- Resolution:
  - Board 10 does not construct or invoke an Adapter and has no network path;
  - `run_local_until_terminal` accepts only injected local callbacks and is
    explicitly named/documented as local;
  - CLI review bundle display is local inspection only;
  - a future real Reviewer must use a new exact outbound-context inventory and
    explicit user authorization rather than inheriting Board 10 permission.
- Evidence: all Board 10 tests use local Python callbacks and synthetic
  repositories; no real endpoint was invoked.
- Residual risk: application code outside Model Council can deliberately pass a
  callback that transmits data; that is outside the Board 10 built-in path and
  remains prohibited without explicit authorization.
- Blocks development: no; no built-in disclosure path exists.

### PRIV-012: Evaluation prompts and responses are external-service evidence

- Date found: 2026-08-30
- Channel: ignored local evaluation SQLite, local CLI and an explicitly
  approved external Responses endpoint
- Priority: medium for the fixed synthetic case; high for any future
  repository-derived case
- Data class: exact outbound prompt, endpoint/model metadata, response text,
  usage and objective result
- Status: mitigated and accepted
- Resolution:
  - Board 11 freezes one public synthetic token task with zero files and zero
    Artifacts;
  - prompt plus transport metadata is limited to 4,096 UTF-8 bytes and bound to
    one exact, single-use approval;
  - response JSON is limited to 16,384 bytes before parsing;
  - non-loopback HTTP endpoints and HTTP redirects are rejected before a
    credential-bearing follow-up request can occur;
  - evaluation tables retain output hashes, byte counts, assertions and ledger
    references rather than response text;
  - tracked configuration stores only
    `MODEL_COUNCIL_DEEPSEEK_API_KEY`, never its value.
- Evidence: local loopback tests cover exact payload, approval consumption,
  objective pass/fail, missing invocation permission, plaintext credential
  rejection, redirect rejection and response-size failure without retry. One
  explicitly authorized live call consumed a 937-byte synthetic-only scope
  with zero files and zero Artifacts; response text was not published or copied
  into evaluation tables.
- Residual risk: a user can explicitly display the local prompt or inspect
  ignored runtime/provider response state. A future non-synthetic task could
  contain private data and therefore needs a separately frozen policy and
  authorization.
- Blocks development: no; the fixed live scope was explicitly authorized and
  consumed once.

### PRIV-013: Local backups contain private runtime state

- Date found: 2026-08-31
- Channel: ignored `state_dir/backups/`
- Priority: medium
- Data class: SQLite prompts, Agent identities, absolute paths, local approval
  records, bounded workspace/repair evidence and optional registered Artifacts
- Status: mitigated and accepted
- Resolution:
  - backup destinations are generated only below the ignored state directory;
  - database-only is the default and Artifact inclusion is explicit;
  - only registered, hash-verified Artifact files below the Artifact store may
    be copied;
  - credentials, `.env`, repositories and worktrees are excluded;
  - manifests use relative names, byte counts and SHA-256 values;
  - restore requires an exact approval and creates a pre-restore safety backup.
- Evidence: synthetic tests verify exclusions, Artifact recovery, stale-state
  rejection, manifest/database tamper detection and safety-backup creation.
- Residual risk: anyone with access to the local operating-system account may
  read ignored backup contents. Host filesystem protection and retention remain
  operator responsibilities.
- Blocks development: no

### PRIV-014: Approval center displays private evidence locally

- Date found: 2026-08-31
- Channel: loopback Web UI and local JSON API
- Priority: medium
- Data class: exact external prompts, workspace paths and bounded evidence,
  repair goals/feedback, evaluation hashes and restore scopes
- Status: mitigated and accepted
- Resolution:
  - the server binds only to `127.0.0.1` or `localhost`;
  - trusted Host, same-origin writes, a per-process token, CSP, no-store and
    browser capability restrictions remain enforced;
  - page refresh is read-only;
  - prompt display is deliberate so outbound approval covers the real text;
  - approval delegates to existing deterministic service methods and remains
    separate from invocation, merge, discard, MCP execution or restore.
- Evidence: Web tests cover local binding/security headers, cross-origin and
  missing-token rejection, exact outbound/workspace/restore approval, read-only
  comparison and product-page sections.
- Residual risk: local malware, an unlocked browser session or deliberate
  screenshots can expose displayed evidence.
- Blocks development: no

### PRIV-015: Release-verifier diagnostics may contain local failure details

- Date found: 2026-08-31
- Channel: local terminal output
- Priority: low
- Data class: bounded command names and the last 4,000 characters of test,
  compilation or privacy-scan diagnostics
- Status: mitigated and accepted
- Resolution: the verifier is local-only, uses argument arrays with
  `shell=False`, bounds retained output and reports only the repository folder
  name rather than its absolute path.
- Evidence: release tests verify version and tracked-file policy; the final
  release command is run only from the reviewed checkout.
- Residual risk: a failing third-party test can print private content to the
  local terminal. Do not paste failed verifier output into public reports
  without review.
- Blocks development: no

### PRIV-016: Supervisor readiness and fake Manager events retain local setup evidence

- Date found: 2026-08-31
- Channel: ignored local runtime SQLite and local CLI output
- Priority: medium
- Data class: Agent labels, selected Model identifiers, local version and
  readiness diagnostics, confirmation notes, snapshot and approval hashes
- Status: mitigated and accepted
- Resolution:
  - Supervisor state is stored only in the existing ignored runtime database;
  - check details pass through the existing sensitive-value sanitizer;
  - confirmation notes are bounded;
  - tracked reports describe only generic synthetic behavior, never runtime
    records or machine-specific endpoints;
  - the first-stage inspector cannot create an Adapter, process or network
    connection.
- Evidence: Supervisor tests use temporary SQLite state and fake observation
  profiles; current-tree and reachable-history privacy scans remain required.
- Residual risk: a local operator can intentionally enter identifying Agent
  labels or copy a local runtime report into a tracked file.
- Blocks development: no

### PRIV-017: Controlled experiment manifests retain exact local invocation scope

- Date found: 2026-08-31
- Channel: ignored local runtime SQLite and deliberate local CLI preview
- Priority: medium
- Data class: synthetic prompt, Agent/Model identities, command, working
  directory, version/configuration hashes, budgets, approval and evidence
- Status: mitigated and exercised under one explicit Board 14 authorization
- Resolution:
  - experiment state remains below the ignored runtime directory;
  - public examples contain only generic synthetic identifiers and paths;
  - personal home paths and credential-shaped text are rejected;
  - the initial policy requires zero files, zero Artifacts, read-only, no
    tools, no workspace writes and no Git;
  - fake evidence stores hashes, byte counts and assertions instead of output;
  - the controlled executor remains unavailable unless an exact experiment and
    integrity-bound, single-use start approval are separately authorized.
- Evidence: focused tests cover private-context rejection, disabled public
  configuration, zero-call simulation, stale approval after identity/team
  drift and executor-integrity drift. One separately authorized local-private
  synthetic turn completed without copying runtime content into tracked files.
- Residual risk: any future exact local manifest and Provider response may
  contain operational or account-correlatable details. They must remain local,
  require a new privacy review, and need a distinct approval ladder.
- Blocks development: no; the completed scope is terminal and grants no new
  execution authority.

### PRIV-018: Failed usage gates lacked a privacy-safe failure classification

- Date found: 2026-08-31
- Channel: ignored local Board 14 runtime SQLite evidence
- Priority: medium
- Data class: provider-reported numeric token counts and protocol-shape
  metadata; raw protocol records could also contain prompts or response text
- Status: resolved before public commit
- Resolution:
  - retain only fixed source labels, semantic field-presence booleans and,
    only for complete over-limit usage, normalized non-negative numeric counts
    plus the configured hard limit;
  - never retain raw JSONL, prompt, response, task plan, stderr, stdout,
    transcript, credentials or private paths;
  - keep the fail-closed usage gate and zero-retry behavior unchanged.
- Evidence: the second separately authorized real Board 14 attempt completed
  the Manager plan validation and then failed at the usage gate, but its
  pre-14.6 runtime state could not distinguish unavailable from incomplete or
  over-limit usage.
- Residual risk: local numeric usage and source-shape metadata remain
  operational data inside ignored runtime SQLite. Host account protection and
  runtime retention remain operator responsibilities.
- Blocks development: no; no real retry is authorized.

### PRIV-019: Failed Manager output contract lacked privacy-safe classification

- Date found: 2026-08-31
- Channel: ignored local Board 14 runtime SQLite evidence
- Priority: medium
- Data class: Provider output structure, output hash and byte count; raw output
  could contain prompt-derived or operational content
- Status: resolved before public commit
- Resolution:
  - validate the exact two-Worker plan contract locally;
  - retain only a failure class, schema label, SHA-256 and byte count;
  - do not retain raw JSONL, output text, prompt, task content, stderr,
    stdout, transcript, credentials, paths, files or Artifacts.
- Evidence: the third separately authorized real Board 14 attempt reached the
  Manager output contract and failed because it did not contain exactly two
  tasks. Its response body was deliberately not retained.
- Residual risk: output hash and byte count remain operational local runtime
  metadata. Host account protection and runtime retention remain operator
  responsibilities.
- Blocks development: no; the terminal experiment and consumed approval cannot
  be retried.

### PRIV-020: Synthetic Manager prompt underspecified the enforced output contract

- Date found: 2026-08-31
- Channel: a separately approved synthetic external prompt and ignored local
  Board 14 runtime diagnostic
- Priority: medium
- Data class: public synthetic task-format instructions and bounded Provider
  output structure; a raw response could contain prompt-derived content
- Status: resolved before public commit
- Resolution:
  - the fourth output-contract failure was retained only as a failure class,
    SHA-256 and byte count; its response text was not reconstructed or stored;
  - Board 14.8 generates the exact v2 JSON contract prompt from the bound mock
    Worker IDs and rejects generic or edited prompts at local preparation;
  - the scope binds the expected top-level/task fields, Worker set and exact
    empty-dependency rule;
  - failure diagnostics remain hash/count/class only and do not store output,
    prompt, JSONL, transcript, credentials, paths, files or Artifacts.
- Evidence: offline fake-App-Server tests assert the exact prompt, valid v2
  output, generic-prompt rejection and fail-closed extra-field diagnostics.
- Residual risk: a future Provider may still disregard the contract. The
  executor then fails closed without retry and records only bounded local
  diagnostic metadata.
- Blocks development: no; any future candidate remains separately gated.

### PRIV-021: Provider input usage may include unreviewed host context

- Date found: 2026-09-01
- Channel: one separately approved synthetic Board 14 App Server execution and
  ignored local runtime usage diagnostic
- Priority: medium
- Data class: complete Provider-reported token counts and protocol source
  shape; raw host context or response would be private operational data
- Status: resolved before public commit
- Resolution:
  - the fifth experiment failed closed at the frozen total-token limit and its
    approval was consumed without retry;
  - runtime retained only normalized input/output/total counts, source-shape
    metadata, the limit, and `response_text_stored: false`;
  - Board 14.9 requires any future Provider-input headroom to be explicit,
    SHA-256-bound, separately capped, and human-approved rather than inferred
    from the small synthetic prompt.
- Evidence: the completed usage shape was present at approved App Server
  locations; the current-tree and reachable-history privacy scans passed after
  the run.
- Post-closeout: one later separately authorized synthetic turn completed
  within its explicit component and total limits. Exact usage and protocol
  records remain only in ignored local runtime state.
- Residual risk: a Provider may continue to include host or service context in
  billed input usage. A future scope must set an explicit budget that covers
  that risk or fail closed; Model Council must not recover or retain raw
  context to diagnose it.
- Blocks development: no; no new candidate or retry is authorized.

### PRIV-022: Cost cap lacked a bound price schedule for high-input scopes

- Date found: 2026-09-01
- Channel: local Board 14 scope review
- Priority: medium
- Data class: operator-declared price schedule and token/cost limits; actual
  Provider billing records remain private runtime data
- Status: resolved before public commit
- Resolution: Board 14.10 requires an explicit, bounded price schedule
  whenever a candidate sets Provider input/output component caps, and reject a
  worst-case envelope above the approved cost cap before any process starts.
- Residual risk: declared prices can become stale or differ from Provider
  billing. A future scope must be approved as an estimate and still retain
  strict token caps; Model Council must not represent the estimate as actual
  cost.
- Blocks development: no; the completed scope is terminal, and no repeat or
  additional candidate is authorized.
