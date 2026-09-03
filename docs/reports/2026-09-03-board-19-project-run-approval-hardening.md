# Board 19 Report: Project-Run Approval Hardening

Date: 2026-09-03

Status: accepted for local private development

## Contribution to PROJECT_GOAL

Board 19 closes the remaining normal-library authorization gap in the
canonical lifecycle. Production project runs now require an exact,
single-use Supervisor approval just like the CLI path.

## Delivered

- `Orchestrator.run()` now fails closed when `start_approval_id` is absent.
- Exact goal, ready-team snapshot, lifecycle evidence and single-use
  consumption continue to be revalidated by `SupervisorService`.
- Added regression coverage for the Python API boundary.
- Existing offline pipeline tests use an explicit private
  `_offline_test_mode`; CLI and Web never enable it.

## Safety and privacy

This board narrows authority only. It adds no Provider, model, App Server,
A2A, MCP, network, repository, worktree, Git or Artifact behavior. Approval
scopes and goals remain local ignored runtime state.

## Verification

```text
Full offline suite: 139 tests passed
Python compilation: passed
Tracked JSON validation: 12 files passed
Current-tree privacy scan: passed
Reachable-history privacy scan: passed with protected `runtime-board14/`
  history paths excluded before blob reads
git diff --check: passed
```

## Remaining gap

The private offline test mode remains until all lower-level pipeline tests can
construct a complete synthetic Supervisor approval without weakening test
isolation. It is not a user-facing project entry point and is not enabled by
default.
