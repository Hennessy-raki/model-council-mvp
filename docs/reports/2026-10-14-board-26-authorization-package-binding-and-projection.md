# Board 26 Report: Authorization Package Binding and Read-Only Projection

Date: 2026-10-14

Status: complete for the local offline binding slice

## Contribution to `PROJECT_GOAL`

Board 24 produced a reviewable authorization package but only as a command's
output. The canonical lifecycle requires the user to be able to *see* the state
of a proposed team member and to know whether an earlier review still stands.
Without a persisted record, a package could only be reviewed once, in the
terminal that produced it, and nothing could detect that an approved package had
since gone stale.

This board makes the package inspectable after the fact: bound to one role,
captured against the current team snapshot, projected read-only through the CLI
and the loopback product surface, and re-validated on every read. It adds no
execution authority.

## Business objective

While implementing this board, one defect in the Board 24 digest was found and
fixed. Board 24 bound `fact_digest` into the package, but `build` computed it
over the raw fact buckets while the read path would have completed them
differently. Reading a freshly built package back would therefore have reported
it stale immediately. `AuthorizationPackageService.normalize_facts` now
completes the buckets in one place, and two regression tests assert both
directions: a freshly stored package must not look stale, and drifted facts must
not reproduce the approved digest.

## Scope

- persist one bound authorization package per role, with its facts, digests,
  identity and captured team snapshot;
- re-derive the digest and the registry identity on every read;
- report `current`, `stale` or `invalid` with a bounded reason code;
- report whether the captured team snapshot is still the latest one;
- project the result through `supervisor authorization-show`,
  `supervisor show` and the loopback Web view;
- refuse to bind a package that carries execution authority, a mismatched
  identity, or facts that do not reproduce its digest.

## Exclusions

No Agent start, connect or attach; no process start; no login or actual-Model
query; no Provider, model, App Server, A2A, MCP or network call; no repository
context; no worktree; no Git operation; no Artifact retention or purge; no start
approval. Binding creates no approval, starts nothing and grants nothing.

## Delivered changes

| Change | File | Purpose |
| --- | --- | --- |
| `normalize_facts` and `recompute_package` | `model_council/authorization.py` | one canonical fact shape, so the digest is reproducible across build and read |
| `supervisor_authorization_packages` | `model_council/store.py` | durable binding record, plus an index on role and update time |
| `bind_authorization_package`, `authorization_package(s)`, `latest_snapshot` | `model_council/supervisor.py` | bind, read back, and re-derive status |
| `_registry_identity_integrity` | `model_council/supervisor.py` | shared with the qualification preflight so both fail closed on the same registry drift |
| `supervisor authorization-bind`, `supervisor authorization-show` | `model_council/cli.py` | the two new read/write entry points |
| Authorization package panel | `model_council/web.py` | loopback read-only projection |
| 16 focused tests | `tests/test_authorization_binding.py` | binding, drift, tampering, identity mismatch, projection |

## Design decisions worth recording

**Binding captures the team snapshot, and a later snapshot supersedes it.** The
frozen scope requires provenance binding to the current team. The record stores
`captured_team_snapshot_id`, and every read compares it with the latest snapshot,
reporting `superseded` when a newer one exists. A snapshot therefore cannot be
silently reused for a review that described a different team.

**Reading re-derives rather than trusts.** The stored package is verified against
its digest, and its facts are replayed through the digest derivation. Nothing is
taken from the row at face value: a tampered package reports `invalid`, and a
package whose bound facts changed reports `stale`. Failure to reproduce fails
closed to `invalid` rather than defaulting to acceptable.

**`status` and `package_status` are separate.** The row carries a record
lifecycle in `status`; the package's own build status is reported in
`package_status`. Collapsing them would have hidden the package's state behind
the word `current`.

**Binding refuses a package that claims authority.** `execution_authorized` must
be exactly `false`, and the bind path rejects a result whose facts do not
reproduce the digest, so a caller cannot hand in a plausible-looking shell.

## Verification

```text
python -m unittest discover -s tests        -> Ran 181 tests ... OK
python -m compileall -q model_council ...   -> exit 0
python scripts/privacy_scan.py --history    -> passed
python scripts/privacy_scan.py --local-state -> no machine-identifying values
```

Covered behaviour, by test:

| Behaviour | Assertion |
| --- | --- |
| No team snapshot | binding raises |
| Normal bind | digest matches, snapshot captured, `integrity_status = current`, no approval created |
| Incomplete evidence | `package_status = user_confirmation_required`, all seven facts reported missing |
| Drifted bound facts | `integrity_status = stale`, code `bound_facts_drifted` |
| Tampered package | `integrity_status = invalid`, code `package_digest_mismatch` |
| Mismatched identity | binding raises |
| Forged authority flag | binding raises |
| Facts that do not reproduce the digest | binding raises |
| New snapshot after binding | `snapshot_status = superseded` |
| CLI projection | empty before binding; the bound entry afterwards through both `authorization-show` and `show` |

The added tests raise the suite from 165 to 181.

## Evidence retained

Tracked output contains no prompts, responses, credentials, runtime rows,
absolute personal paths, Provider records or machine identity. The stored and
projected values are identifiers, categories, bounded status codes, limits,
ladder names and digests.

## Why the next board is necessary

The control plane can now describe one exact real-Agent request and show whether
an earlier review still stands. It still cannot observe a real Agent. Reaching
that requires a new frozen scope and an exact authorization for a displayed
package, and that board must be authorized separately.
