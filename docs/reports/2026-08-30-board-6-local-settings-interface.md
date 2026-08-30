# Board 6 Report: Local Settings Interface

Date: 2026-08-30

Status: accepted

## Objective

Provide a local control surface over the durable registry, discovery,
provenance, ledger, budget and deterministic-routing contracts from Boards 1
through 5. SQLite must remain authoritative, user-owned settings must survive
seed synchronization, and the interface must not create a model or remote
interoperability path.

## Delivered

### Local-only Web server

`python -m model_council web --config config.example.json` starts a
dependency-free HTTP interface using only the Python standard library. It binds
to `127.0.0.1` by default and rejects non-loopback hosts. The server provides
only a static local page and same-origin JSON endpoints; it has no CORS,
third-party asset, discovery, balance-query or model-invocation endpoint.
Every process creates an ephemeral write token embedded in its same-origin
page. Mutations also require a trusted loopback Host and, when present, a
matching Origin. Inline style and script execution is limited by a per-process
CSP nonce.

The page explicitly reports that it is reading local SQLite state and that
refresh does not re-scan, probe, query balances or call a model.

### Registry and policy editing

The interface can add or edit user-owned records for:

- Providers, with credential-like configuration keys redacted before storage;
- Models, validated against an existing Provider;
- Agent profiles, validated against existing Provider and Model links;
- role assignments, with the existing routing-constraint validation;
- application settings, including the existing provenance-display constraint;
- budget policies, with the existing warning, hard-limit and currency rules.

The new registry methods store the same normalized SQLite rows used by the CLI.
Updates are marked `user`, so a later JSON seed synchronization preserves the
user's choices under the established ownership rules.

### Inspectable evidence

The interface reads and displays persisted:

- Provider, Model, Agent, role and application-setting registry records;
- executable, authentication, permission and connectivity observations;
- Artifact provenance;
- usage, cost, budget-policy, alert and balance-snapshot evidence;
- declared discovery and billing capabilities for configured Adapters, without
  invoking those capabilities;
- immutable routing decisions, including rejected-candidate evidence;
- recent runs.

The browser is presentation and mutation only. It cannot bypass the
`RoutingService`, change a resolved decision or turn manager preferences into
authorization.

## Verification

```text
45 tests passed
```

The four Board 6 tests cover:

- user-owned Provider, Model, Agent, role and setting updates;
- sensitive configuration redaction before persistence;
- budget editing and local-observation state;
- loopback HTTP rendering, session-token JSON updates and restrictive headers;
- rejection of missing-token and cross-origin writes;
- validation that capability arrays contain non-empty strings.

The complete test suite remained offline. No real Codex model, paid Provider,
balance endpoint, discovery probe or external model service was called.

## Privacy and execution boundaries

- The Web server binds only to loopback.
- Configuration values are passed through the existing storage redaction before
  they reach SQLite.
- The page loads no remote assets and sends no repository contents externally.
- The interface does not expose GitHub Support communication or historical
  privacy-remediation identifiers.
- The public-push privacy scanner remains required after this board.

## Scope boundaries

Board 6 does not implement:

- Codex App Server or persistent real-model sessions;
- A2A, MCP or remote Agent interoperability;
- automatic worktree creation, merge or deployment;
- new billing claims, automatic price refresh or remote balance polling;
- browser-side or model-generated routing authorization.

Board 7 remains unstarted and requires separate authorization.

## Next session

Run the standard offline and privacy checks before further work. The local
interface can be inspected with:

```powershell
python -m model_council web --config config.example.json
```

Do not start Board 7 or a real Codex pilot without explicit user authorization.
