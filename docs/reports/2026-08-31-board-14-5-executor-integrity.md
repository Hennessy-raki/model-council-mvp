# Board 14.5 Report: Start-Approval Executor Integrity Binding

Date: 2026-08-31

Status: accepted offline verification; Board 14 remains in progress

## Delivered

Every newly requested Board 14 start approval now includes SHA-256 integrity
records for:

- `model_council/experiments.py`, the controlled executor; and
- `model_council/interoperability.py`, the JSON-lines transport helper.

Immediately before consuming an approved start approval, the executor
recomputes both hashes. If either differs, the start approval becomes `stale`
and no process is created. The existing experiment, team snapshot, Agent/Model
identity, strict policy, prompt, transport, permission and limit revalidation
continues unchanged.

## Verification

The new regression test alters the integrity result in memory and proves:

- a fresh start approval displays both integrity records;
- integrity drift marks that approval stale;
- the failure happens before fixture process startup.

Final offline verification:

```text
119 offline tests passed
Python compilation passed for model_council, tests and scripts
Current-tree privacy scan passed
Reachable-history privacy scan passed
git diff --check passed
```

No real App Server startup, PackyAPI request, model call, retry, workspace
write, Git action, push, tag or Release occurred during Board 14.5.

## Next boundary

The first real pilot remains failed and its start approval remains consumed.
Neither can be retried. A future candidate must be newly prepared after this
commit, then separately approved, armed, given a fresh start approval that
displays the integrity records, approved again, and explicitly authorized for
one turn.
