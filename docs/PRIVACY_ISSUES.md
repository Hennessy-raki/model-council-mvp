# Privacy Issue Register

Last updated: 2026-08-30

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
