# Board 27 Report: Version Preference Engine and Configuration-Driven Discovery

Date: 2026-10-14

Status: complete for the local offline slice

## Contribution to `PROJECT_GOAL`

Boards 24 and 26 could build and bind an authorization package, but the Agent
catalogue they describe was empty, so both could only be exercised with example
values. Filling the catalogue ran into a question the real machine makes
concrete: several Agents exist in more than one version at the same time, and
the discovery mechanism could only see four vendor names hardcoded in the
module. `PROJECT_GOAL` rule 9 forbids exactly that binding to a single vendor,
and rule 4 forbids treating a registered item as a runnable one.

This board answers both: it ranks installed versions under a rule the operator
states, and it moves the discovery catalogue into configuration so that a
desktop application can be recorded without being mistaken for something the
control plane can invoke.

## Business objective

The operator must be able to see what Agent versions are installed on this
machine, be told which one the stated rule prefers, and still choose a different
one. A recommendation that cannot be overridden, or that silently replaces a
binding, would take the decision away from the operator.

## Scope

- compare version strings deterministically, covering the shapes this machine
  actually produces;
- apply the operator's stated preference at the level of comparing two versions
  and at the level of ranking candidates;
- let an explicit user preference override the recommendation;
- report `undecidable` when versions have no comparable form;
- move the discovery catalogue into configuration;
- probe each installed form with an argument-array, shell-free, time-limited
  command;
- record a GUI-only application without claiming it is invocable.

## Exclusions

No Agent invocation, no model call, no Provider, App Server, A2A, MCP or network
call; no project context in any probe; no change to a binding; no start
approval; no Artifact action; no publication.

The only process this board starts is a version query. It sends no project
context and asks the tool to identify itself.

## Delivered changes

| Change | File | Purpose |
| --- | --- | --- |
| `parse_version`, `compare_versions`, `version_kind`, `plan_upgrade`, `version_from_output` | `model_council/versions.py` | deterministic comparison and a stated preference |
| `LocalAgentTarget.version_arguments`, `.extra_path_patterns`, `.interface_kind` | `model_council/discovery.py` | a tool is described by data, not by code |
| `target_from_config`, `targets_from_config`, `gui_targets_from_config` | `model_council/discovery.py` | validated catalogue from configuration |
| `version_candidates`, `_probe_version`, `_scan_gui_target` | `model_council/discovery.py` | probe and rank installed forms; record a GUI-only Agent |
| `discovery_targets`, `gui_only_targets` | `model_council/config.py` | the two catalogues, validated at load time |

## The rule, and where it applies

The operator chose two things, and they act at different levels.

| Level | Rule |
| --- | --- |
| Comparing two versions | A stable release outranks a pre-release of the *same* number: `1.35.0` above `1.35.0-rc.1` |
| Ranking candidates | Any stable release is preferred over any pre-release, so `1.34.9` is recommended over `1.35.0-rc.1` |

Ranking by number alone, with the stability rule off, remains available through
`stable_absolute_priority=False`, because the setting is a decision rather than
a fixed property of the code.

An explicit `preferred_version` always wins and is reported as
`user_preference`, with the versions it displaced listed under `alternatives`.
No result ever carries `auto_switch: true`.

## Verified against this machine

| Agent | Path | Version detected |
| --- | --- | --- |
| codex | `codex.cmd` on PATH | 0.154.0 |
| reasonix | `reasonix.cmd` on PATH | 1.7.0-rc.1 |
| reasonix | desktop installation CLI | 1.35.0 |

With both reasonix installs present, the recommendation is **1.35.0** with
reason `stable_release_preferred_over_prerelease`, because a stable release is
preferred over any pre-release even though `1.7.0-rc.1` is on PATH. An explicit
preference of `1.7.0-rc.1` overrides it and is reported as
`explicit_user_preference`.

An end-to-end run with a configuration declaring four GUI-only applications
recorded all four as `gui_only_application` with `agent_id` null and
`capabilities.invocable` false, created no team binding, and left the CLI
targets in the same run registered normally. The machine-specific paths stay in
the operator's local configuration, outside this public repository.

## Defects found and fixed while building this

All five were found by running the code against the real machine or by a test,
not by inspection.

1. **Trailing-zero normalisation made padded comparison necessary.** `1.35`
   and `1.35.0` normalise to different tuples, so the comparator must compare
   the padded values rather than the stored ones.
2. **The pre-release flag was read as an ascending value**, which inverted the
   answer: `1.35.0-rc.1` compared above `1.35.0`. The comparison is now written
   through an explicit three-way helper so the direction cannot be misread.
3. **`Path().glob` rejects an absolute pattern**, so an operator-supplied
   absolute path failed at scan time. Replaced with `glob.glob`.
4. **An empty `adapters` mapping was treated as "not supplied"**, because an
   empty dict is falsy, and the call then failed on a missing config. Now
   distinguished with an explicit `is None` check.
5. **The reason string named the version kinds present rather than the rule
   that decided**, so switching stable priority off still reported the
   stable-priority reason. A recorded reason that does not match the decision
   would have misled every later review.

A sixth issue was found by inspection while writing the docs: an earlier version
of this report referred to report files that did not exist, which is why the
file you are reading exists.

## Verification

```text
python -m unittest discover -s tests        -> Ran 234 tests ... OK
python -m compileall -q model_council ...   -> exit 0
python scripts/privacy_scan.py --history    -> passed
python scripts/privacy_scan.py --local-state -> no machine-identifying values
git diff --check                            -> clean
```

The suite grew from 181 to 234 across Board 27: 24 cases for the version engine
and 29 for discovery.

## Evidence retained

Tracked output contains no prompts, responses, credentials, runtime rows,
absolute personal paths, Provider records or machine identity. The tracked
catalogue holds vendor keys and command names; the machine-specific paths live in
the operator's local configuration.

## Why the next board is necessary

The entry documents were last updated at Board 26 and several now describe a
state that has moved: the recorded test count, the Agent catalogue, the
available CLI commands and the Codex version. A new session that reads them
first would be misled, which is the failure this project has hit before.
