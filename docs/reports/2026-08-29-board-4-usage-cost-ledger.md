# Board 4 Report: Usage, Cost and Balance Ledger

Date: 2026-08-29

Status: accepted

Commit: `feat: add usage cost and balance ledger`

## Objective

Create an auditable control-plane ledger for every model-host call without
presenting estimates, configured prices or missing values as actual provider
billing.

GitHub Issue #4 was not present when this board started. Acceptance therefore
followed `docs/DEVELOPMENT_BOARDS.md`, `AGENTS.md`, the project handoff and the
completed Board 1 through Board 3 contracts.

## Delivered

### Immutable per-call records

Every Adapter invocation made by the orchestrator now creates one
`usage_events` row. This includes manager planning and synthesis, worker calls,
independent review and failed calls.

Each record captures:

- run, task, project, Agent and role;
- producing Provider and Model snapshots;
- phase and completion status;
- request count and local duration;
- normalized input, output and total tokens;
- cost amount and currency;
- bounded raw usage metadata;
- a source label for every measurement family.

### Measurement source contract

The ledger uses four explicit source labels:

- `actual`: locally observed request counts and duration, or explicitly
  identified actual billing data;
- `provider_reported`: usage or cost returned by the model host;
- `estimated`: heuristic token counts or configured-price calculations;
- `unavailable`: no defensible value exists.

Unknown values remain null. Summary totals expose source counts so a displayed
zero cannot conceal unavailable consumption.

### Normalization and estimation

The normalizer accepts common provider token fields including:

- `input_tokens` / `output_tokens`;
- `prompt_tokens` / `completion_tokens`;
- `total_tokens`.

When `usage_estimation_enabled` is true and the Provider reports no usage,
tokens are estimated from prompt and response character counts. Cost estimates
are calculated only when the selected Model has an explicit pricing object.
Configured prices never become `actual`.

OpenAI-compatible responses now preserve returned usage and optional cost
objects in Adapter metadata. Codex JSONL usage remains provider-reported.

### Project, run and role totals

The CLI can aggregate:

- total calls and duration;
- input, output and total tokens;
- costs by currency;
- token and cost source distributions;
- completed and failed call counts;
- per-role totals.

Run status output now includes the run ledger and its budget alerts.

### Budget policies

`budget_policies` supports project, run and role scopes for token or cost
metrics. Configuration-owned policies are synchronized additively. CLI-created
policies are user-owned and survive later config synchronization.

Warnings create persistent `budget_alerts`. Hard policies are checked before a
call. Once a hard threshold is reached, later calls are blocked. If a hard
policy depends on prior unavailable values, the next call is conservatively
blocked rather than assuming unknown consumption is zero.

Calls covered by hard policies are serialized around check, invocation and
recording so parallel workers cannot all pass the same stale pre-call check.
Workloads without hard policies keep normal parallel execution.

### Provider balance

Provider balance is never inferred from usage or model pricing. The CLI asks an
Adapter only when it declares `provider_balance`. Unsupported Providers return
`unavailable` without a network request.

The OpenAI-compatible Adapter supports an optional, provider-specific balance
endpoint and field mapping. Successful results become immutable
`provider_balance_snapshots` with currency and source.

### CLI control surface

```powershell
python -m model_council ledger summary --config config.example.json
python -m model_council ledger events --run <RUN_ID> --config config.example.json
python -m model_council ledger budgets --config config.example.json
python -m model_council ledger set-budget project-cost `
  --scope project --metric cost --warning 5 --hard 10 --currency USD `
  --config config.example.json
python -m model_council ledger alerts --run <RUN_ID> --config config.example.json
python -m model_council ledger balance <PROVIDER_ID> --config config.example.json
python -m model_council ledger balance-history --config config.example.json
```

## Verification

Automated verification:

```text
29 tests passed
```

New coverage verifies:

- provider-reported token normalization;
- explicitly actual reported cost;
- estimated tokens and configured-price cost;
- unavailable token and cost preservation;
- project, run and role totals in a full workflow;
- CLI ledger summaries;
- warning and hard-limit alerts;
- conservative hard blocking after unavailable values;
- user budget overrides surviving config sync;
- unsupported balance APIs making no request;
- supported balance snapshots;
- OpenAI-compatible balance capability and field mapping;
- additive migration of all ledger tables.

Offline smoke verification produced:

- six normalized calls for one complete mock run;
- 2,092 estimated tokens;
- estimated USD cost of zero for the explicitly zero-priced mock model;
- five role totals;
- no budget warning at the configured threshold;
- `unavailable` balance for the mock Provider without a balance API.

No real Codex model or paid Provider balance endpoint was invoked.

## Scope boundaries

This board does not:

- choose Agents or implement routing;
- fetch a universal price catalog;
- convert currencies;
- invent Provider balances;
- implement time-based budget policies;
- build a Web interface;
- send repository content to an external model.

The real Codex pilot remains separately paused.

## Next board

Board 5 will implement routing policy using persisted capability, discovery,
availability and ledger evidence. It must preserve manual locks and required
model separation and must persist explanations for every automatic or hybrid
selection.
