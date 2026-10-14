# Board 29 Report: Gaps Exposed by the First Real Observation

Date: 2026-10-14

Status: complete for the local offline slice

## Contribution to `PROJECT_GOAL`

The project has asserted since its first milestone that a configured model must
never be treated as proof that the same model actually served a request. Until
2026-10-14 that assertion had never been tested against a real call, because
every prior board ran against mock adapters or repository fake servers.

One real observation was performed under explicit operator authorization. It
succeeded and it exposed three gaps that no amount of offline work would have
surfaced. This board closes them. It adds no execution authority of its own.

## The observation that produced this board

Authorized scope: one read-only `codex exec` call, one synthetic ASCII-token
task, zero files, zero Artifacts, no tools, no repository content, one attempt
with no retry, `--ephemeral`, run in a system temporary directory.

Result: exit code 0, the exact expected token returned, and a complete
`thread.started → turn.started → item.completed → turn.completed` event stream.

| Qualification fact | Outcome |
| --- | --- |
| process | passed |
| version | 0.154.0 |
| permission | read-only honoured |
| protocol | passed |
| connectivity | passed, with provider-reported usage |
| actual_model | **not obtainable** — the JSONL stream carries no model field |
| login | not applicable — API-key mode |

### The finding worth recording

The prompt was 78 bytes. The service billed **16,078 input tokens**, of which
15,232 were cached. The difference is the host tool's own system prompt and tool
definitions, which are injected per call and are independent of task size.

This reframes a constraint the project had already hit. Board 14.9 added
`max_input_tokens` after a real attempt failed on "complete Provider input usage
above the frozen total cap". That failure was not an anomaly; it was this
overhead. Any future scope sized from prompt length alone will fail closed.

## Gaps closed

**1. The adapter did not record the model the service reported.**
`OpenAICompatibleAdapter` wrote `{"model": <configured>}` and nothing else, so
the one fact the project most needs to verify was structurally unobservable. It
now records `configured_model`, `observed_model`, `observed_model_source` and,
when the two disagree, `model_identity_mismatch`. An absent report is recorded as
`unavailable` rather than filled in from the configured value.

**2. The login check had no notion of authentication mode.**
An API-key Agent has no interactive login state, so reporting `unknown` for it
looks like a missing fact and holds a team at `not_ready` permanently. The
Supervisor now classifies the Agent's authentication mode from its persisted
configuration and records the login check as `not_applicable` with code
`login_not_applicable_for_api_key`. An interactive-login Agent is unaffected:
its unknown login state remains a real fact to resolve.

**3. The connectivity probe reported a false failure.**
It used `/models`, which the observed provider rejects with 403 while serving
completions normally. A provider can now declare
`models_endpoint_available: false`, and the probe confirms reachability through
the completion endpoint instead. That path costs one bounded request, so it is
declared explicitly rather than assumed, and it doubles as an identity
observation.

## Scope

- record the service-reported model identity separately from the configured one;
- classify authentication mode and record a non-meaningful login check as
  not applicable;
- let a provider declare that `/models` is unavailable and probe the completion
  endpoint instead;
- record the prompt-token count on every call;
- document the input-token overhead and its consequences for future budgets.

## Exclusions

No new external call is made by this board. The code changes are verified
against stubs and against the repository's existing local test doubles. The one
real call belongs to the observation described above and was separately
authorized.

## Verification

```text
python -m unittest discover -s tests        -> Ran 253 tests ... OK
python -m compileall -q model_council ...   -> exit 0
python scripts/privacy_scan.py --history    -> passed
python scripts/privacy_scan.py --local-state -> no machine-identifying values
git diff --check                            -> clean
```

19 new cases across two areas: model identity, prompt-token recording and
connectivity mode in `tests/test_model_identity.py`, plus the authentication-mode
classification and its effect on the login check. The suite grew from 234 to
253.

The observation itself left no residue: `--ephemeral` produced no session file,
no credential appears in any script, no user-level environment variable was
written, and the raw JSONL was never persisted.

## Evidence retained

Tracked output contains no prompts, responses, credentials, runtime rows,
absolute personal paths or machine identity. The recorded observation values are
token counts, byte counts, status classifications and the exact synthetic token
that the task asked for.

## Residual risk

`actual_model` remains unverifiable for a CLI-hosted Agent whose output stream
carries no model field. The adapter-level fix covers HTTP providers that report
one; a tool that does not report its model still cannot be verified from its own
output. That limitation is now recorded rather than papered over, and it is the
honest answer to the rule that a configured model is not proof.

The credential used for the observation is stored in plaintext in the host
tool's own configuration file and has additionally been pasted into a chat
transcript. It should be rotated; that is an operator action, recorded here so
it is not forgotten.

## Why the next board is necessary

The control plane can now describe, bind, project and partially observe a real
Agent. What remains is the operator-facing path that turns an observation into a
qualification record the supervisor accepts, which is currently the last
unimplemented step of the canonical lifecycle.
