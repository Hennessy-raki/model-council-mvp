# Board 31 Report: Only a Probe Can Produce a Qualification Record

Date: 2026-10-14

Status: complete for the local offline slice

## Contribution to `PROJECT_GOAL`

Board 30 made a measured observation a qualification record, and the record
alone did not settle whether anything had been measured. A test written while
auditing the project showed the gap: a hand-written record claiming every fact
observed, with `actual_model` filled in from configuration, was accepted with
`integrity_status = current` and bound without complaint.

That is the failure the project's own first rule names. Its contribution is
therefore narrow and important: the system can now tell a receipt from a claim,
and it refuses the claim when a real Agent is at stake.

## Business objective

A record that says "observed" must mean a process produced that observation. An
operator who can type the word `observed` into a JSON file has not measured
anything, and a qualification gate that cannot distinguish the two gives false
confidence about exactly the fact that is hardest to verify.

## Scope

- mark every record with its provenance, `probe_run` or `operator_authored`;
- add `ObservationProbeService`, which runs one bounded probe and derives the
  facts from the captured output rather than from its arguments;
- let the probe capture its own start and finish times so the measurement time
  is not caller-chosen;
- record the command digest and the output hash in the record;
- refuse a caller-supplied record at binding unless the caller says explicitly
  that an unverified claim is intended;
- require a probe-produced record before a non-mock role can be marked ready;
- expose the probe through the CLI.

## Exclusions

No model call, no Provider, App Server, A2A, MCP or network call; no project
context in any probe; no change to the authorization package, the qualification
preflight or the start-approval ladder; no publication.

The probe starts one process: the tool it is asked to ask. It sends that tool no
project context.

## Delivered changes

| Change | File | Purpose |
| --- | --- | --- |
| `PROVENANCE_*`, `PROBE_PROVIDES`, `PROBE_CANNOT_ESTABLISH` | `model_council/observation.py` | provenance labels and what a probe may claim |
| `ObservationProbeService.probe` | `model_council/observation.py` | runs a probe, derives facts from captured output |
| `run_probe_command` | `model_council/observation.py` | argument-array, shell-free, time-limited capture with digests |
| Provenance check in `bind_observation_record` | `model_council/supervisor.py` | refuses a claim by default |
| Probe requirement in readiness | `model_council/supervisor.py` | a non-mock role needs a receipt |
| `supervisor observation-probe` | `model_council/cli.py` | the entry point |
| 4 new tests plus updated fixtures | `tests/test_observation.py`, `tests/test_supervisor.py` | provenance, refusal, explicit override, probe-produced status |

## Design decisions worth recording

**The probe derives facts; it does not accept them.** The caller supplies the
identity and the command. Every fact value comes from the captured output,
parsed by this class. A caller therefore cannot assert that a fact was observed;
it can only run something and accept what came back.

**The probe reports only what it can establish.** A version probe yields
`process` and `version`. `actual_model`, `permission`, `protocol` and
`connectivity` stay `unknown`, because establishing them needs a real turn, and
`login` is not applicable to a key-based Agent. The first real probe against the
installed Codex CLI produced exactly that: two observed, five unknown. Filling
`actual_model` from configuration would have been the precise error the project
forbids.

**The measurement time is the probe's own.** `measured_at` is the captured
`finished_at`, so an operator cannot age a record into freshness or backdate one
into staleness.

**A caller-supplied record is not deleted, it is labelled.** It remains bindable
with an explicit `allow_operator_authored=True`, and the stored provenance shows
which kind it is. The refusal is a default, not a prohibition, because there are
honest uses for recording an unverified claim as long as it is recorded as such.

## The honest limit of this board

This does not prevent forgery, and claiming otherwise would be false. A local
operator owns the process, the disk and the tool, so a determined operator can
always manufacture evidence; nothing running on this machine can stop that.

What changed is the trust boundary. The record no longer rests on free-form
caller JSON that happens to use the word `observed`, and an inconsistency in the
captured provenance is reportable. That is a real reduction in the space for
accidental false confidence, and it is not a guarantee against deliberate
misrepresentation. The README records this limit next to the mechanism.

## Behaviour this tightens

Nine observation tests and two supervisor tests failed when the provenance check
was added, which is the intended effect: fixtures that built records by hand no
longer qualify a real Agent. They were converted to use a probe runner that
mimics a captured run, so the tests exercise the path production uses rather
than the path the board removed.

## Defects found and fixed while building this

1. **The probe rejected its own evidence field.** `_evidence` did not list
   `output_bytes`, which the probe adds, so every probe result came back
   `blocked` with `unsupported_evidence_field`. Found by running the probe
   rather than by reading it.
2. **A module-level constant import created a cycle.** Reading the provenance
   labels into the supervisor at import time failed, because the observation
   module imports the supervisor. The check now compares plain strings.

## Verification

```text
python -m unittest discover -s tests        -> Ran 288 tests ... OK
python -m compileall -q model_council ...   -> exit 0
python scripts/privacy_scan.py --history    -> passed
python scripts/privacy_scan.py --local-state -> no machine-identifying values
git diff --check                            -> clean
```

The suite grew from 284 to 288.

A real probe was run against the installed Codex CLI through the new CLI
command. It recorded `process = exit_code=0` and `version = 0.154.0`, left the
other five facts unknown, and carried a `probe_run` provenance with a command
digest, an output hash, and its own start and finish times. The record retains
the output byte count, not the output.

## Evidence retained

Tracked output contains no prompts, responses, credentials, runtime rows,
absolute personal paths or machine identity. A probe record holds classifications,
a parsed version, digests, timestamps, an exit code and a byte count. The
executable path is used by the probe and deliberately not written into the
record.

## Why the next board is necessary

The record is trustworthy and narrow. What remains is coverage: the probe
establishes two of the seven facts, and the rest need a real turn. Producing
them honestly is the next problem, and it is the one that finally requires the
real model call the operator has already authorized in principle.
