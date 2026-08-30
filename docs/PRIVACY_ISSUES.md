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
