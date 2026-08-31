# Board 14.5 Plan: Start-Approval Executor Integrity Binding

Date: 2026-08-31

Status: frozen before implementation

## Trigger

Board 14.4 repaired the controlled executor after the first real pilot failed
closed. A future second start approval must bind the execution-control code
that interprets that approval; otherwise code could change after review while
the displayed start scope remained unchanged.

## Goal

Add SHA-256 integrity records for the controlled executor module and its
JSON-lines transport helper to every newly requested start approval. Before
consumption, recompute both digests. Any mismatch marks the start approval
stale and prevents process creation.

## Scope

- hash only tracked, public source modules:
  `model_council/experiments.py` and `model_council/interoperability.py`;
- include module labels and SHA-256 values in the start-approval scope;
- revalidate integrity immediately before one-time consumption;
- retain all existing experiment, identity, prompt, transport, permission,
  usage and limit checks;
- prove source-integrity drift blocks consumption without starting a fixture.

## Excluded

- real App Server startup or model call;
- a retry of the failed, consumed first pilot;
- runtime prompt/response persistence;
- code-signing, external attestations, package publishing, push, tag or
  Release.

## Next boundary

After offline acceptance, create a fresh strict candidate and repeat every
approval gate. The final start-approval display must include the executor
integrity records before any second one-turn pilot can be considered.
