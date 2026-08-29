# Board 1 Report: Settings and Registry Foundation

Date: 2026-08-29

Status: accepted

Commit: `feat: add settings and registry foundation`

## Objective

Create the persistent foundation required by the future settings interface,
automatic model selection, Artifact attribution, startup discovery and billing
features.

The board deliberately does not build a graphical interface. A UI created before
the underlying data contract would duplicate configuration logic and make later
model discovery and routing changes difficult to control.

## Delivered

### Persistent registry

SQLite now stores:

- Providers;
- Models;
- Agent profiles;
- role assignments;
- application settings.

Provider, Model and Agent are separate identities. This allows one Agent host to
expose different models and allows the same model family to be accessed through
different hosts or providers.

### Role assignment modes

Every project role can use:

- `manual`: a specific Agent is required;
- `auto`: the future router will select an Agent and Model;
- `hybrid`: the user supplies preferences while the router may choose within
  constraints.

Assignments also support:

- optional Model selection;
- a lock flag;
- arbitrary structured constraints;
- a source field distinguishing config values from user choices.

### Seed configuration and user ownership

JSON configuration is treated as seed data. It can create and update
configuration-owned registry records, but it does not overwrite records whose
source is `user`.

This establishes the behavior needed by a future settings UI:

```text
JSON seed -> initial registry
user/UI change -> user-owned override
later JSON sync -> user override remains intact
```

Synchronization is additive and non-destructive. Records absent from the JSON
file are not deleted.

### Secret redaction

Nested configuration keys that appear to contain API keys, authorization data,
passwords, secrets or tokens are replaced with `[REDACTED]` before being stored
in the registry.

This is defense in depth. Future credential handling must still use operating
system credential storage or environment references rather than registry JSON.

### CLI control surface

The following commands are available:

```powershell
python -m model_council settings sync --config config.example.json
python -m model_council settings show --config config.example.json
python -m model_council settings assign detail_executor `
  --mode hybrid --agent implementer --model mock-general --locked `
  --config config.example.json
python -m model_council settings set locale '"zh-CN"' `
  --config config.example.json
```

The orchestrator synchronizes the registry at startup, so normal runs also keep
configuration-owned records current.

## Data contract

```text
providers
  -> models
  -> agent_profiles
  -> role_assignments

app_settings
```

An Agent may reference a Provider and Model. A role may reference an Agent and
Model. Foreign keys prevent assignments to unknown registered identities.

## Verification

Automated test result:

```text
10 tests passed
```

New coverage verifies:

- complete registry synchronization;
- automatic manager and reviewer role creation;
- nested secret redaction;
- user role overrides surviving later config synchronization;
- user setting overrides surviving later config synchronization;
- rejection of assignments to unknown Agents.

Manual smoke verification produced:

```text
Providers: 1
Models: 1
Agents: 5
Role assignments: 3
Application settings: 2
```

Both example JSON configurations parsed successfully.

## Scope boundaries

This board does not yet:

- change runtime routing based on persisted roles;
- discover installed Agents or models;
- provide a graphical settings page;
- record Artifact producer identity;
- calculate usage or costs;
- store credentials.

Those behaviors depend on this registry and are assigned to later boards.

## Risks and decisions

### Config versus database authority

Decision: user-owned database values take precedence over future config sync.

Reason: otherwise every application restart could silently undo settings changed
through the UI.

### Automatic mode

Decision: store `auto` and `hybrid` now, but do not implement selection logic in
this board.

Reason: routing requires reliable discovery, capability observations and budget
data. Choosing automatically before those inputs exist would create misleading
behavior.

### Record deletion

Decision: configuration sync does not delete missing records.

Reason: later discovery and manual setup may create records that are not
represented in the original JSON seed.

## Next board

Board 2 will add Artifact provenance:

- producing Agent;
- Provider and Model identity;
- contributors;
- reviewer;
- final integrator;
- internal provenance retention;
- user-configurable display mode.

This is the next dependency because discovery, cost reporting and quality
evaluation all require work products to be connected to their actual producer.
