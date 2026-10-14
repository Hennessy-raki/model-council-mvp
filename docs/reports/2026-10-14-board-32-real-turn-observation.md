# Board 32 Report: A Real Turn Establishes What a Version Query Cannot

Date: 2026-10-14

Status: complete for the real-observation slice

## Contribution to `PROJECT_GOAL`

Board 31 made only a probe-produced record able to qualify a real Agent, and the
probe could establish two of seven facts. The other five were declared
unobservable without attempting them. This board attempts them, under the
operator's authorization to make real calls, and reports exactly what a real
turn establishes and what it does not.

The result is more useful than a success would have been. Four facts are
observable on this machine. Two are not, for reasons that are now measured
rather than assumed, and the system records them as unknown instead of filling
them in.

## Business objective

The canonical lifecycle needs each member's real state, and the project forbids
substituting a configured value for an observed one. Establishing which facts a
real turn can actually supply is therefore a precondition for any honest
qualification, and it had never been done.

## Scope

- add `ObservationTurnService`, which runs one bounded, read-only, ephemeral,
  synthetic turn and derives facts from the captured event stream;
- build the turn's argument list inside the service, so the prompt and the
  safety flags cannot be supplied or relaxed by the caller;
- keep the response text out of the record: only hashes, byte counts, token
  counts and the one synthetic token the task asked for;
- add `combine_probe_records`, so a version probe and a turn probe can produce
  one record covering the union of what they establish;
- run one real turn against the installed Codex CLI and record what it yielded.

## Exclusions

No new Provider, A2A or MCP call; no writing Agent; no repository, worktree or
Artifact context; no change to the qualification preflight, the authorization
package or the start-approval ladder; no publication.

The turn sets `--sandbox read-only`, `--ephemeral`, `--skip-git-repo-check` and
disables the optional subsystems that made unauthenticated catalog requests
during the first live pilot.

## What the real turn established

```text
observed : process(exit_code=0)  version(0.154.0)
           protocol(jsonl_events=3)  connectivity(synthetic_token_returned)
unknown  : actual_model   permission
n/a      : login
prompt_tokens: 16046     output_tokens: 12
```

Combined with a version probe, four of seven facts are observable on this
machine, two are not, and one does not apply.

## The two facts that stay unknown, and why

**`actual_model` cannot be observed from either side on this machine.** The
Codex event stream carries no model field, which the 2026-10-14 observation
already showed. This board tested the other side: a direct request to the
configured relay endpoint returns HTTP 403 with `error code: 1010`, a
Cloudflare interstitial, so the service's own report is unreachable too. The
fact is therefore unobservable here, and the record says so. Filling it in from
the configured value would be the precise substitution the project forbids.

**`permission` cannot be observed from a silent tool.** The turn requests
read-only, and the tool did not echo the sandbox it used. The requested value is
not the observed value, so recording it as observed would be an assertion about
the tool rather than a measurement of it. It stays unknown.

This is the honest ceiling for this machine, and it is now documented rather
than discovered again next time.

## Delivered changes

| Change | File | Purpose |
| --- | --- | --- |
| `TURN_PROMPT`, `TURN_EXPECTED_TOKEN`, `TURN_PROVIDES`, `TURN_CANNOT_ESTABLISH` | `model_council/observation.py` | a fixed synthetic task and what it can establish |
| `run_turn_command` | `model_council/observation.py` | builds the argument list, runs one bounded turn, captures the event stream |
| `ObservationTurnService.turn` | `model_council/observation.py` | derives facts from the captured events |
| `combine_probe_records` | `model_council/observation.py` | merges receipts into one record |
| 22 new tests | `tests/test_observation.py` | turn derivation, refusal cases, merging |

## Design decisions worth recording

**The prompt belongs to the module.** A caller cannot supply it, so it cannot be
swapped for something carrying project content, and the record is comparable
across runs because what was sent is fixed. The provenance stores the prompt's
hash and byte count.

**Connectivity requires the right answer, not just a process exit.** A turn that
returns a different token, or nothing, leaves connectivity unknown. Exiting
cleanly proves the process ran, which is a different fact.

**Merging is restricted to receipts.** A version probe and a turn probe may be
merged; a caller-supplied claim may not, because mixing a receipt with an
assertion destroys the value of the receipt. Every input's digest is verified
and every input's identity must match.

**A merged record is as fresh as its oldest input.** An earlier measurement
cannot be made current by a later probe, so the combined measurement time is the
minimum across the contributing records.

## Defects found and fixed while building this

1. **The sensitive-key filter rejected a token count.** `prompt_token_sources`
   contains the word "token", so the substring check treated it as a credential
   and blocked every merged record with `sensitive_field_forbidden`. Token
   counts are now named explicitly in the allow-list that bypasses the substring
   check.
2. **`output_bytes` and `prompt_token_sources` were not accepted evidence
   fields**, so the services rejected their own output until the allow-list was
   extended.

## Verification

```text
python -m unittest discover -s tests        -> Ran 306 tests ... OK
python -m compileall -q model_council ...   -> exit 0
python scripts/privacy_scan.py --history    -> passed
python scripts/privacy_scan.py --local-state -> no machine-identifying values
git diff --check                            -> clean
```

The suite grew from 288 to 306.

One real turn was performed under the operator's authorization. No session file
was written (`--ephemeral`), the response text was never persisted, and the
record retains a byte count and two token counts rather than any content.

## Evidence retained

Tracked output contains no prompts, responses, credentials, runtime rows,
absolute personal paths or machine identity. A turn record holds classifications,
one parsed version, two token counts, an exit code, digests, timestamps and the
synthetic token the task asked for.

## Why the next board is necessary

Four facts are observable and two are structurally unobservable on this machine.
A qualification gate that requires all seven would hold a team at not_ready
forever, and one that ignores the difference would accept a claim in place of a
measurement. The next problem is therefore the policy: which facts a scope must
require, and how to record a deliberate, reviewable exception for a fact that
cannot be observed here.
