# Board 14.10 Report: Explicit Cost Feasibility Gate

Date: 2026-09-01

Status: accepted offline verification; Board 14 remains in progress

## Trigger

After Board 14.9 made a future Provider-input budget explicit, a local review
found that a high-input scope could still bind a numeric cost cap without a
bound price schedule. That would not prove its permitted token envelope fits
the cost budget.

## Delivered

Any Board 14 scope that sets input/output component caps must now also include:

- both `max_input_tokens` and `max_output_tokens`;
- `max_total_tokens` and `max_total_cost`;
- a `cost_estimate` containing input-per-million, output-per-million,
  per-request, and matching currency values.

Preparation uses decimal arithmetic to calculate the maximum declared cost from
the two token caps and per-request fee. It rejects missing, malformed,
non-positive per-token prices, currency mismatch, component-limit mismatch, or
a maximum envelope above `max_total_cost`.

The normalized declared schedule is part of the existing experiment and
start-approval SHA-256 scope. It is an operator-declared estimate, not a claim
of Provider-reported or current billing.

## Offline verification

The Board 14 fixture tests cover:

- explicit component input/output/total budgets;
- missing cost schedule rejection;
- worst-case envelope rejection above the cost cap;
- existing strict approval, integrity, usage, output-contract, and
  zero-retry behavior.

No test starts `codex.cmd`, contacts a Provider, accesses credentials, sends
network traffic, or invokes a model.

## Verification

```text
Focused Board 14 experiments: 26 tests passed
Full offline suite: 127 tests passed
Python compilation passed for model_council, tests and scripts
Tracked JSON validation passed (12 files)
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

## Next authorization boundary

All five prior Board 14 real synthetic attempts and consumed approvals remain
terminal. Board 14.10 creates no candidate and grants no execution authority.

A new candidate may be prepared only after the user separately authorizes a
local pending scope that displays its exact input/output/total limits, declared
price schedule, worst-case cost and all existing privacy boundaries.
