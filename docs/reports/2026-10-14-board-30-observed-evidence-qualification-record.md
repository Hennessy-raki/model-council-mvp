# Board 30 Report: Observed Evidence Becomes a Qualification Record

Date: 2026-10-14

Status: complete for the local offline slice

## Contribution to `PROJECT_GOAL`

After the first real observation, the control plane could produce an
authorization package, bind it, project it and measure a real Agent, and none of
that measurement reached the system's own judgement. The canonical lifecycle
therefore still had a hole: the supervisor would accept a declared scope as if it
described reality, because there was nothing else to consult.

This board closes that hole. A measurement becomes a first-class record that the
supervisor requires, ages, and refuses when it no longer describes the present.
It adds no execution authority and makes no external call.

## Business objective

A declaration says what would be observed. Only a measurement says what was. The
project's own rules forbid treating the first as the second, so readiness must
be able to tell them apart and must refuse a team whose evidence is missing or
old rather than accepting the declaration in its place.

## Scope

- define a deterministic, privacy-safe observation record and its digest;
- require an explicit measurement time and refuse one that is not a real moment;
- record how each observed fact was obtained, distinguishing a tool's
  self-report from a service's report about the request it served;
- treat a fact that does not apply, such as login for a key-based Agent, as
  `not_applicable` rather than as a missing one;
- age every record against an explicit lifetime and report `stale` with a reason
  code rather than silently accepting it;
- require a current record before a non-mock role can be marked ready;
- bind the record into the team snapshot so a later measurement change makes the
  snapshot stale;
- project the result read-only through the CLI and the Supervisor show command.

## Exclusions

No Agent invocation, no model call, no Provider, App Server, A2A, MCP or network
call; no process start beyond the repository's existing local fixtures; no change
to the authorization package or the qualification preflight; no start-approval
semantics change; no publication.

## Delivered changes

| Change | File | Purpose |
| --- | --- | --- |
| `ObservationService` | `model_council/observation.py` | builds, verifies and ages one measurement record |
| `supervisor_observation_records` | `model_council/store.py` | durable record keyed by role |
| `bind_observation_record`, `observation_record(s)` | `model_council/supervisor.py` | bind, read back, re-derive status |
| Readiness gate | `model_council/supervisor.py` | a non-mock role additionally needs a current record |
| Snapshot binding | `model_council/supervisor.py` | the record digest and measurement time enter the snapshot payload |
| `supervisor observation-bind`, `observation-show` | `model_council/cli.py` | the two entry points |
| 31 focused tests | `tests/test_observation.py` | record building, ageing, binding, projections |

## Design decisions worth recording

**A value without a measurement time is not evidence about the present.** The
record requires `measured_at` and an explicit `max_age_seconds`, and a record
that cannot be aged is refused rather than assumed fresh. This is the difference
between "the model was X" and "the model was X when we last looked".

**Where a value came from is part of the value.** Each observed fact carries a
source: `tool_output`, `service_response`, `local_process` or
`operator_confirmed`. A tool reporting its own version is a weaker claim than a
service reporting which model served a request, and they must not be recorded
under the same label. An observed fact that omits its source is refused.

**Reading re-derives rather than trusts.** As with the authorization package, the
stored record is verified against its digest and re-aged on every read. A
tampered record is `invalid` with `record_digest_mismatch`; an expired one is
`stale` with `measurement_expired`. Failure to reproduce fails closed.

**The record is bound into the snapshot.** A measurement change after a snapshot
makes the snapshot stale rather than leaving an approval attached to a team whose
evidence has moved.

**Binding a measurement does not require a snapshot.** The first ordering
attempt required one and deadlocked, because a non-mock role cannot be
snapshotted before it has been observed and could not be observed before being
snapshotted. The record precedes the snapshot that later binds it.

## Behaviour this tightens

Two existing supervisor tests failed when this board was first run, and that is
the intended effect: a non-mock role that previously became ready with only a
declared preflight now also needs a measurement. The tests were updated to bind
one, which reflects the new requirement rather than relaxing it.

The qualification preflight is unchanged and still required. Scope is not
retired by measurement; the two answer different questions.

## Defects found and fixed while building this

1. **A shape-valid but impossible timestamp was accepted.** `2026-13-45T99:99:99Z`
   matched the outline and is not a moment in time, so a shape check alone let it
   through and the error would have surfaced only when ageing. The value is now
   parsed at submission, with its own blocker code.
2. **The timestamp regex rejected what the project itself emits.** The first
   version demanded fractional seconds with a `Z` suffix, while `utc_now()` emits
   a numeric offset, so the checker and the producer disagreed. The accepted
   formats were widened to the ISO-8601 forms real tooling uses.
3. **The readiness pass was recorded before the prerequisite existed.** A report
   captured before a preflight was bound kept saying
   `qualification_preflight_required`, because a stored report is deliberately
   not recomputed behind the caller's back. The ordering is now explicit.

## Verification

```text
python -m unittest discover -s tests        -> Ran 284 tests ... OK
python -m compileall -q model_council ...   -> exit 0
python scripts/privacy_scan.py --history    -> passed
python scripts/privacy_scan.py --local-state -> no machine-identifying values
git diff --check                            -> clean
```

The suite grew from 253 to 284. Coverage includes determinism, the measurement
time requirement, an impossible moment, the source requirement for an observed
fact, unknown fact names, sensitive-material rejection, prompt-token survival
through the sensitive-key filter, five distinct staleness reasons, identity
mismatch, digest tampering, a blocked result, the readiness gate, snapshot
staleness after a changed measurement, and the CLI projections.

## Evidence retained

Tracked output contains no prompts, responses, credentials, runtime rows,
absolute personal paths or machine identity. A record holds classifications,
bounded values, timestamps, digests and the token counts the provider reported.

## Why the next board is necessary

The supervisor can now require and age a measurement, but nothing produces the
record from a real observation automatically: an operator builds it by hand and
binds it. The canonical lifecycle's next step is the path that turns a completed
observation into the record, which is the last manual join in the chain.
