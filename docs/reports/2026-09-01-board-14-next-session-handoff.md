# Board 14 Next-Session Handoff

Date: 2026-09-01

Status: superseded by Board 14.11 closeout; retained as the pre-execution
handoff record

## Purpose

Resume local-private Model Council development in the existing checkout. Do not
copy the repository, create a worktree, push, tag, create a Release, or infer
authorization for a model call from this handoff.

The companion runtime appendix is deliberately ignored by Git and contains
local experiment identifiers needed for safe continuation. Read it only from
the local checkout; never copy it into a tracked document, issue, commit, or
external prompt.

Board 14.11 subsequently completed one separately authorized synthetic Manager
turn and closed Board 14 for local-private incubation. Read
`docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md` for the
current terminal boundary. This historical handoff does not authorize a repeat.

## Verified code checkpoint

The local `main` checkpoint is:

```text
526f16a Gate high-input experiments on cost feasibility
```

It is intentionally ahead of `origin/main` by eleven local commits. No push,
tag, or GitHub Release was created.

Boards 1 through 12 remain the prepared public `0.2.0rc1` release candidate.
Board 13 and Board 14 are local-private incubation work.

The final Board 14 code sequence is:

- Board 14.6: privacy-safe unavailable/incomplete/total-over-limit usage
  diagnostics;
- Board 14.7: privacy-safe Manager output-contract diagnostics;
- Board 14.8: identity-bound v2 synthetic Manager prompt;
- Board 14.9: separate input, output, and total token hard limits;
- Board 14.10: declared price schedule and worst-case cost-feasibility gate
  for any component-token scope.

## Real-execution state

Five separately authorized synthetic Manager attempts have reached terminal
failure and their approvals are consumed. None may be retried, re-armed,
re-approved, replayed, or used as a template for a new approval.

Their failure categories were:

1. usage unavailable;
2. usage unavailable or over the total-token cap;
3. invalid two-task output contract;
4. invalid task key under the v1 contract;
5. complete Provider input usage above the total-token cap.

No raw Provider response, JSONL stream, prompt instance, transcript, stderr,
stdout, credential, path, file, Artifact, or private project context may enter
Git. Runtime evidence retains only hashes, byte counts, normalized usage where
permitted, and privacy-safe failure classifications.

One older v1 runtime experiment is still marked `approved` but is a legacy
record. It predates strict approval handling and the v2 output/cost controls.
Do not arm, approve further, request a start approval for, or otherwise use it.

## Current product behavior

The next compliant high-input candidate must bind all of the following into its
experiment and start-approval SHA-256 scopes:

- exact v2 synthetic prompt and the two frozen mock Worker identities;
- read-only transport, no tools, zero files, zero Artifacts, no Git, one call,
  zero retries, sequential operation, timeout and response-byte limits;
- `max_input_tokens`, `max_output_tokens`, and `max_total_tokens`;
- `max_total_cost`, `cost_currency`, and a declared `cost_estimate` with:
  `input_per_million`, `output_per_million`, `per_request`, and `currency`.

The component token caps must both be present, each must not exceed the total,
their sum must not exceed the total, the estimate currency must match the cost
currency, and the decimal worst-case token envelope must not exceed the cost
cap. The price schedule is an operator-declared estimate, not an assertion of
Provider billing or current market pricing.

## Required first actions in a new session

1. Work only in the existing checkout named by the user; verify `cwd`, `git
   status --short --branch`, and `git log -1 --oneline`.
2. Read `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`,
   `docs/PROJECT_HANDOFF.md`, `docs/ROADMAP.md`,
   `docs/DEVELOPMENT_BOARDS.md`, `docs/START_HERE_NEXT_SESSION.md`,
   `docs/PRIVACY.md`, `docs/PRIVACY_ISSUES.md`, this handoff, and the Board
   14.8, 14.9, and 14.10 reports.
3. Run the baseline before changes:

   ```powershell
   python -m unittest discover -s tests -v
   python -m compileall -q model_council tests scripts
   python scripts/privacy_scan.py --history
   ```

4. Treat ignored `runtime-board14/` data as local-private. Read its private
   appendix only when the user has placed that local state in scope.
5. Do not prepare a candidate until the user provides exact business values for
   the token caps, cost cap, currency, and declared price schedule, then grants
   a separate authorization limited to creating one local `pending`
   experiment.

## Required authorization ladder

Each scope is single-use and must be authorized separately:

```text
exact budget and price decision
  -> authorize only pending experiment preparation
  -> approve exact experiment SHA-256
  -> authorize only arm after revalidation
  -> authorize only pending start-approval creation
  -> approve exact start-approval SHA-256 and integrity records
  -> authorize exactly one execute-start
```

If readiness, identity, prompt, transport, source-integrity, usage,
output-contract, permission, token, cost, timeout, or response-byte controls
fail, stop with zero retries. Perform only a read-only postmortem and the
current-tree plus reachable-history privacy scans. Do not replay consumed
approvals.

## Verification checkpoint

The most recent Board 14.10 acceptance evidence is:

```text
Focused Board 14 experiments: 26 tests passed
Full offline suite: 127 tests passed
Python compilation passed
Tracked JSON validation passed (12 files)
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

## Documents

- Board 14.8: `docs/reports/2026-08-31-board-14-8-contract-bound-synthetic-prompt.md`
- Board 14.9: `docs/reports/2026-09-01-board-14-9-provider-input-budget.md`
- Board 14.10: `docs/reports/2026-09-01-board-14-10-cost-feasibility.md`
- Board 14.11: `docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md`
- local-only supplement:
  `runtime-board14/2026-09-01-next-session-private-handoff.md`
