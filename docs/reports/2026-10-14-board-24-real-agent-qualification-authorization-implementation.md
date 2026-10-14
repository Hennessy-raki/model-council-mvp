# Board 24 Implementation Report: Real-Agent Qualification Authorization Package

Date: 2026-10-14

Status: complete for the offline preparation scope frozen on 2026-09-09

Board numbering note: Board 24's scope was frozen on 2026-09-09 with no
implementation and no new board number was assigned to it. Board 25 was later
assigned to the foundation audit. This report implements the frozen Board 24
scope under its original number, which is why the dates differ from the plan.

## Contribution to `PROJECT_GOAL`

`docs/PROJECT_GOAL.md` requires that "all members ready" is not the same as "the
task may start", and that the user can inspect what a real Agent+Model
qualification would send before anything leaves this machine. The frozen scope
states the missing handoff: local qualification metadata exists, but the user
has no single reviewable object that separates what was declared, what was
observed, and what the user must still confirm.

This board supplies that object. It performs no qualification and authorizes no
execution. Its contribution is that one future real-Agent request becomes
exact, privacy-safe and independently reviewable before any process, Provider,
model or private context can be involved.

## Business objective

An operator must be able to answer, from one deterministic document:

1. which Agent, Model and Provider are being proposed, and whether those values
   came from the registry or from an observation;
2. whether the permissions, tools, context and limits are the frozen minimum;
3. which facts are still missing, so that consent is asked about real unknowns
   rather than assumed;
4. whether a previously approved package is still the same package.

## Scope

- add `model_council/authorization.py` with a pure local package builder;
- define the package schema, the fact classification and the digest;
- reference the working directory by category and environment-variable name
  instead of by value;
- expose the same service projection through CLI commands;
- add regression tests for determinism, drift, rejection and privacy.

## Exclusions

No Agent start, connect or attach; no process start; no login or actual-Model
query; no Provider, model, App Server, A2A, MCP or network call; no repository
context; no writing permission; no worktree; no Git operation; no Artifact
retention or purge; no remote authentication or signing; no change to the
Supervisor snapshot, project-run approval or single-use semantics.

## Delivered changes

| Change | File | Purpose |
| --- | --- | --- |
| `AuthorizationPackageService` | `model_council/authorization.py` | builds one deterministic, privacy-safe package and verifies it against its digest |
| `authorization build` / `authorization verify` | `model_council/cli.py` | read-only entry points; `build` is pure validation and persists nothing |
| Rejection of any absolute path | `model_council/qualification.py` | the Board 21 preflight rejected a user-home path but accepted any other absolute path; a non-home absolute path still names real directories on this host |
| 12 focused tests | `tests/test_authorization.py` | determinism, drift, authority rejection, privacy |

## Design decisions worth recording

**The working directory is never stored as a value.** It appears as a category
(`synthetic_workspace`, `system_temp`, `dedicated_operator_directory`) plus an
environment-variable name such as `MODEL_COUNCIL_SYNTHETIC_CWD`. That is what
satisfies "require an explicit, resolved working directory at authorization
time without storing or displaying a personal absolute path in tracked files",
and it reuses the convention already established for Board 8's `cwd_env`.

**Missing evidence produces `user_confirmation_required` by construction.** The
seven canonical lifecycle facts default to `unknown`. A package cannot reach
`eligible_for_separate_review` by omitting evidence; it reaches it only when
observed values are supplied. The default outcome is therefore a question to
the operator, not an assumption.

**Fact state is bound into the package digest.** The first implementation left
the facts outside the digest, so a package approved while the actual Model was
unknown kept validating after a later observation contradicted it. The package
now carries `fact_digest`, `declared_fact_names` and `observed_fact_names`, so
any change to the facts changes `package_sha256` and makes a prior approval
stale. A regression test asserts exactly that.

## Verification

```text
python -m unittest discover -s tests        -> Ran 165 tests ... OK
python -m compileall -q model_council ...   -> exit 0
python scripts/privacy_scan.py --history    -> passed
python scripts/privacy_scan.py --local-state -> no machine-identifying values
```

End-to-end CLI verification:

| Step | Result |
| --- | --- |
| `build` with no observations | `status = user_confirmation_required`, all seven facts missing, `execution_authorized = false` |
| `build` with observations | `status = eligible_for_separate_review`, no missing facts, digest changes |
| `verify` against the stored digest | `verified = true`, `execution_authorized = false` |
| `verify` after tampering with a permission | `verified = false`, exit code 2 |

The added tests raise the suite from 153 to 165.

## Known flaky test, unrelated to this board

One full-suite run reported
`ConnectionAbortedError: [WinError 10053]` in
`tests/test_evaluation.py::test_redirect_is_rejected_before_a_second_request`.
The same test passed 8 consecutive isolated runs and the full suite passed twice
afterwards. This is the Windows loopback interruption recorded as Board 16,
which stays deferred unless a reproducible failure is captured. Board 24 does
not depend on it and does not change it.

## Evidence retained

Tracked output contains no prompts, responses, credentials, runtime rows,
absolute personal paths, Provider records or machine identity. The package holds
identifiers, categories, bounded status codes, limits, ladder names and digests.

## Why the next board is necessary

Board 24 produces a reviewable request; it does not qualify an Agent. The
canonical lifecycle still stops short of one real observation. Reaching it
requires a new frozen scope and an exact user authorization for the displayed
package, and a separate record when that consent exists.
