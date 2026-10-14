# Board 25 Report: Foundation Audit and Recomputed Trust Surface

Date: 2026-10-14

Status: complete for the local offline audit-and-remediation slice

## Contribution to `PROJECT_GOAL`

`docs/PROJECT_GOAL.md` requires that the user can inspect a real Agent+Model
team, authorize exactly one run, and receive an auditable result without any
silent expansion of data, file, network or permission scope. The canonical
property is that the user keeps control over what leaves this machine.

The owner restated the underlying requirement on 2026-10-14: information about
this machine must not become recoverable by another party, because personal
privacy in the hands of a malicious party is hard to recover. That statement
wider than "do not publish". Board 25 recomputes the trust surface against it
and fixes the two deterministic causes it found. It adds no execution authority.

## Business objective

The twenty-four preceding boards were planned, implemented and accepted by one
process. A second development owner cannot inherit those acceptance claims as
facts. Before any new capability is built, the existing foundation must be
independently checked, and every check must be reproducible by a command.

## Scope

- audit the documentation, report evidence chain, production entry points,
  privacy gate and the thirty-three unpublished commits;
- repair the deterministic causes found during the audit;
- extend the privacy gate so that ignored local runtime state is inspected;
- remove machine-identifying values from newly written persistent Artifact
  records;
- record the threat model that the new controls serve.

## Exclusions

No external model, Provider, App Server, A2A, MCP or network invocation; no
process start; no Git push, tag or Release; no third-party dependency; no SQLite
schema change; no deletion of existing runtime data; no change to Board 24's
frozen scope; no Board 24 execution authority.

## Audit results

| Layer | Check | Result |
| --- | --- | --- |
| Documentation | 71 report files, 70 referenced paths | all referenced paths exist; 5 reports are only self-referenced; the suite total was stale at "150", measured 151 |
| Evidence chain | sampled report claims against implementation | the sampled claims, including Board 9's and Board 10's explicit scope statements, hold |
| Production entry points | `RepairService.run_local_until_terminal`, `WorkspaceService.invoke_cli` | both are documented as deliberate local-only test paths; not missing wiring |
| Privacy gate | `scripts/privacy_scan.py` coverage | the scanner never inspected ignored runtime state (PRIV-032) |
| Unpublished commits | 33 commits ahead of `origin/main` | 63 `.md`, 25 `.py`, 5 `.json`; no binary, database or image; all commit authors use the GitHub noreply identity; no machine-identifying value found |

## Delivered changes

| Change | File | Purpose |
| --- | --- | --- |
| Local runtime state inspection | `scripts/privacy_scan.py` (`--local-state`) | makes recoverable machine identity visible; previously the only privacy tool skipped every ignored path |
| OS build fingerprint detection | `scripts/privacy_scan.py` (`os_build_fingerprint`) | catches OS version-and-build strings the earlier pattern set did not cover |
| Machine-independent Artifact paths | `model_council/artifacts.py` | removes the real user name and project directory from newly persisted records |
| Legacy compatibility | `model_council/artifacts.py`, `model_council/backup.py` | previously written absolute values keep resolving |
| Dead exemption removed | `scripts/privacy_scan.py` | the `runtime-board14/` history skip never matched an object and could only ever hide a future one |
| Stale test count corrected | `docs/START_HERE_NEXT_SESSION.md` | the recorded total was 150 against a measured 151 |
| Register additions | `docs/PRIVACY_ISSUES.md` | PRIV-029 through PRIV-032, plus the widened triage policy |

## Verification

```text
python -m unittest discover -s tests                    -> Ran 153 tests ... OK
python -m compileall -q model_council tests scripts      -> exit 0
python scripts/privacy_scan.py                           -> passed
python scripts/privacy_scan.py --history                 -> passed
python scripts/privacy_scan.py --history --local-state   -> reports 4 recoverable values
```

End-to-end confirmation of the Artifact change: a fresh runtime database
persisted `36/365a305d….md` instead of an absolute path, the value resolved and
read back correctly, and the database byte stream contained no `C:\Users`
sequence.

## Residual risk

Local runtime data written before this board still holds absolute paths. It is
ignored by Git and was never published, but it is readable from this host or any
copy of it. It is not rewritten automatically, because rewriting the owner's
local run history is a destructive change that needs explicit authorization. The
operator control is: remove `runtime/`, `runtime-board14/` and
`runtime-board8-pilot/` before archiving, copying or migrating the working tree.
`python scripts/privacy_scan.py --local-state` reports what remains.

## Evidence retained

Tracked output contains no prompts, responses, credentials, runtime rows,
absolute personal paths or Provider records. The audit read local runtime state
but copied none of it into tracked files.

## Why the next board is necessary

Board 25 changes no external-execution boundary and grants no new call. The
canonical user lifecycle still stops short of one real Agent qualification. That
remains separately scoped and separately authorized.
