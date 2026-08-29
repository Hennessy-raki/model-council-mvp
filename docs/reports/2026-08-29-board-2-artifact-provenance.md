# Board 2 Report: Artifact Provenance

Date: 2026-08-29

Status: accepted

Commit: `feat: add artifact provenance`

## Objective

Make every work product attributable to the actual local Agent host, Provider
and Model that produced it, while preserving the distinction between internal
audit data and what a user chooses to see in a delivery view.

## Delivered

### Immutable producer snapshots

New Artifacts capture their producing Agent, Provider and Model IDs at creation
time. The snapshot is stored directly on the `artifacts` record, rather than
being reconstructed from mutable current settings.

### Participation attribution

The new `artifact_attributions` table records role-specific identity snapshots:

- `producer`;
- `contributor`;
- `reviewer`;
- `final_integrator`.

Worker Artifacts include upstream contributors. Review Artifacts identify both
the reviewing Agent and the reviewed work lineage. The final report identifies
the manager as final integrator and includes the worker and review lineage as
contributors.

### Internal audit versus presentation

`artifact_provenance_display` is a persisted application setting with three
validated values:

- `compact`: producer identity, contributor count and review/integration flags;
- `detailed`: full participant identity lists;
- `hidden`: no provenance field in the CLI `status` Artifact projection.

The default seed setting is `compact`. `hidden` is deliberately presentation
only: all producer and attribution records continue to be written, and the
internal store can still retrieve the full audit trail. As with other settings,
a user-owned display override survives later JSON seed synchronization.

### Safe SQLite migration

Store initialization is additive and idempotent. It creates the attribution
table and checks the existing `artifacts` columns before adding the three
nullable producer snapshot columns. A pre-Board-2 database retains all existing
Artifact rows; legacy Artifacts simply have no historical producer identity.

## Verification

Automated verification:

```text
13 tests passed
```

New coverage verifies:

- producer Provider, Model and Agent persistence;
- contributor de-duplication;
- reviewer and final-integrator attribution in a full mock workflow;
- `compact`, `detailed` and `hidden` projections;
- retrieval of internal provenance after `hidden` projection;
- user display-mode override protection and invalid-mode rejection;
- migration of an existing SQLite Artifact record without data loss.

The offline demo was rerun after the change and completed successfully with a
final Artifact.

## Scope boundaries

This board does not implement:

- automatic role routing;
- startup Agent or model discovery;
- usage, cost or billing calculations;
- a Web or Electron interface;
- a real Codex invocation.

The real Codex pilot remains paused pending explicit user authorization before
any private repository content or derived details are sent to an external model
service.

## Next board

Board 3 will add startup discovery and setup checks. It must treat the registry
as durable local state and must not replace the captured Artifact provenance
snapshot with mutable live configuration.
