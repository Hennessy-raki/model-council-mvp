# Board 14.4 Plan: Fail-Closed App Server Usage Compatibility Repair

Date: 2026-08-31

Status: frozen before implementation

## Trigger

The first separately authorized one-turn Board 14.3 pilot consumed its start
approval and failed without retry because the controlled executor did not
observe a usage shape it could verify. The response body was deliberately not
retained, so this repair does not attempt to reconstruct or inspect it.

## Goal

Extend the local executor's usage parser to accept only bounded,
non-negative provider-reported token counts from these protocol-equivalent
locations:

- `thread/tokenUsage/updated.params.tokenUsage.last`;
- `thread/tokenUsage/updated.params.tokenUsage.total`; and
- `turn/completed.params.turn.usage`.

If no complete, verifiable usage is present, the executor must continue to
fail closed before success evidence is stored.

## Offline-only verification

- use repository-controlled fake App Server fixtures only;
- test accepted `total` notification usage;
- test accepted completion-turn usage;
- preserve failure on absent or incomplete usage;
- retain one process, one turn and zero retries in fixture tests;
- store only hashes, byte counts and bounded usage in evidence.

## Excluded

- any retry of the consumed Board 14.3 start approval;
- real App Server startup, PackyAPI access or model call;
- relaxed token limits or unverified usage acceptance;
- raw response, prompt, protocol transcript or credential storage;
- GitHub push, tag or Release.

## Next real-pilot boundary

If this repair passes offline verification, create a fresh strict candidate,
then repeat the complete sequence: experiment approval, arm approval, pending
start approval, start approval, and one separate exact execution authorization.
