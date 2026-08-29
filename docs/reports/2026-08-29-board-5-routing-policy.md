# Board 5 Report: Routing Policy

Date: 2026-08-29

Status: accepted

Commit: `f386ecea1dda471921e331dd0cb0f354f926ba3a`
(`feat: add deterministic routing policy`)

## Objective

Resolve every manager, worker and reviewer role through deterministic
control-plane policy before invoking an Adapter. Selection must consume the
durable contracts created by Boards 1 through 4 and must remain auditable.

## Delivered

### Manual, automatic and hybrid routing

`RoutingService` now resolves persisted role assignments:

- `manual` uses the required Agent and fails without silent replacement;
- `auto` ranks only candidates that satisfy every hard constraint;
- `hybrid` preserves the preferred Agent and falls back deterministically only
  when the assignment is unlocked;
- older configurations without explicit worker roles retain implicit manual
  compatibility.

The manager proposes a role and may express an Agent preference. The final
identity is selected by deterministic code and written back into the accepted
task plan before execution.

### Persisted evidence

Candidate evaluation consumes:

- enabled Provider, Model and Agent registry state;
- configured runnable Adapter presence;
- Agent and Model capabilities;
- separated executable, authentication, permission and connectivity
  observations;
- historical average cost and latency from `usage_events`;
- active hard-budget state;
- prior routing decisions needed by separation constraints.

Unknown cost and latency remain unknown. A hard maximum rejects missing evidence
unless the user explicitly permits it. Clearly failed discovery or exhausted
hard-budget evidence rejects a candidate.

### Locks and separation

A locked assignment requires an explicit Agent and disables hybrid fallback.
Constraints support explicit Agent, Model and Provider exclusions plus
role-relative separation on any combination of:

- Agent identity;
- Model identity;
- Provider identity.

Manager and reviewer identities are reserved from automatic worker selection.

### Durable explanations

The additive `routing_decisions` table records:

- run, task and role;
- assignment mode and requested identity;
- selected Agent, Provider and Model;
- success or failure and a stable reason code;
- the applied constraints;
- selected capability, availability, cost and latency evidence;
- rejected candidates and their reason codes.

`status` includes routing evidence. It can also be inspected directly:

```powershell
python -m model_council routing decisions --run <RUN_ID> `
  --config config.example.json
```

### Configuration and privacy hardening

Role constraints are validated during config loading and user assignment.
`settings assign` accepts a JSON `--constraints` object.

Credential redaction continues to suppress access, bearer and refresh-token
fields while preserving non-secret token counts and measurement-source fields.
The repository now includes `docs/PRIVACY.md` and the offline
`scripts/privacy_scan.py` release gate.

## Verification

Automated verification:

```text
41 tests passed
```

Coverage includes:

- manual success and no-fallback failure;
- automatic capability and availability filtering;
- hybrid preference, fallback and lock behavior;
- historical cost and latency limits;
- unknown cost not being treated as zero;
- hard-budget routing rejection;
- Provider separation between roles;
- immutable routing explanations;
- additive migration of an existing SQLite database;
- end-to-end routing in the mock collaboration workflow;
- privacy scanner detection and safe non-disclosure output;
- credential redaction without destroying usage metrics.

The final offline demo run
`0179d65d-91c2-4cd6-b6fe-448fe178cad6` completed with:

- four completed tasks;
- ten structured messages;
- five Artifacts;
- five resolved routing decisions;
- six completed usage events;
- 2,282 estimated tokens;
- estimated USD cost of zero;
- no budget alert.

`doctor` resolved the configured local `codex.cmd` without invoking it.
Discovery scanned local commands without running a connectivity probe. No real
Codex model, paid Provider, balance endpoint or external model service was
called.

## Privacy verification

The board added a repeatable public-repository privacy gate. The final release
check covers tracked and non-ignored text, changed files, staged content,
tracked filenames, ignore rules and commit-author metadata. The scanner reports
only file, line and finding type and never echoes a possible secret value.

No runtime database, generated Artifact, `.env`, credential, personal home
path, private repository content or real local username is intended to enter
the public commit.

The complete reachable Git history was rewritten to replace an older README
home-directory example with a generic placeholder. The cleaned public `main`
was independently verified at the Board 5 commit above, and the full local
history scan passed afterward.

GitHub's low-level object API continued to return the now-unreferenced old blobs
immediately after the force-push. They are no longer referenced by public
branches or normal repository history, but complete physical removal depends on
GitHub garbage collection or a private GitHub Support purge request. The old
object IDs are deliberately not recorded in public project documentation.

## Scope boundaries

This board does not implement:

- the Board 6 local Web or Electron interface;
- Codex App Server or persistent real-model sessions;
- A2A, MCP or remote Agent interoperability;
- worktree creation, merge or deployment;
- a universal price catalog or currency conversion;
- broad real-model startup.

The real Codex pilot remains separately paused pending explicit authorization
before repository content or derived details are sent to an external model
service.

## Next board

Board 6 will build the local settings interface over the stable registry,
discovery, provenance, ledger, budget and routing contracts. It must keep state
local by default and must not begin Board 7 interoperability.
