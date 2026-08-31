# Board 14.4 Report: Fail-Closed App Server Usage Compatibility Repair

Date: 2026-08-31

Status: accepted offline verification; no real retry performed

## Trigger

The first separately authorized Board 14.3 one-turn pilot on August 31, 2026
started the approved App Server command and stopped safely because no
verifiable provider usage was observed. Its start approval was consumed once;
this board does not retry it.

## Delivered

The controlled executor now accepts complete, non-negative token usage from:

- `thread/tokenUsage/updated.params.tokenUsage.last`;
- `thread/tokenUsage/updated.params.tokenUsage.total`; or
- `turn/completed.params.turn.usage`.

It still fails closed when usage is absent or incomplete, before success
evidence is stored. Limits, one-call semantics, zero retries and response
privacy are unchanged.

## Offline verification

Repository fake App Server fixtures covered:

- accepted `last` usage;
- accepted `total` usage;
- accepted completion-turn usage;
- absent usage failure;
- token-limit failure;
- strict approval-request termination;
- exact prompt, one process, one turn, zero retry and response hashing.

Final verification:

```text
118 offline tests passed
Python compilation passed for model_council, tests and scripts
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

No real Codex process, PackyAPI call, model retry, external network request,
new credential use or workspace write occurred during Board 14.4.

## Next authorization boundary

The failed Board 14.3 experiment and consumed start approval are terminal and
must not be reused. A new strict candidate must be prepared and displayed,
then separately approved, armed, given a new start approval, and explicitly
authorized for one execution. The first real retry must remain one Manager
turn with two mock Worker identities.
