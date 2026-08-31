# Board 14.8 Plan: Contract-Bound Synthetic Manager Prompt

Date: 2026-08-31

Status: frozen before implementation

## Trigger

The fourth separately authorized Board 14 one-turn synthetic Manager attempt
consumed its approval and failed closed with the privacy-safe
`task_key_invalid` classification. The retained SHA-256 and byte count cannot
and must not be used to reconstruct its response body.

The local failure classification established that the response reached the JSON
task path, while the frozen prompt asked only for two synthetic tasks. It did
not state the locally enforced non-empty `key`, exact Worker identity,
independence, top-level, or control-field requirements. The product therefore
asked the Manager for a weaker contract than the executor required.

## Goal

Make the future Board 14 synthetic prompt a canonical, identity-bound copy of
the local Manager plan contract, and version the strengthened contract as
`manager_two_worker_plan_v2`.

## Scope

- create one tested canonical prompt builder bound to the two frozen mock
  Worker Agent IDs;
- require that exact generated prompt during local experiment preparation;
- bind the v2 schema, allowed top-level fields, allowed task fields, Worker
  IDs, and exact empty dependency rule into the experiment scope;
- require a JSON object whose only top-level field is `tasks`;
- require exactly two task objects, each with exactly `key`, `agent`, and
  `depends_on`, with a non-empty unique key, each bound Worker used once, and
  `depends_on: []`;
- keep rejection of permission, tool, workspace, file, Artifact, Git, and
  command fields, with privacy-safe output diagnostics only;
- update the repository fake App Server fixture to assert exact prompt
  delivery and valid v2 output;
- add regression coverage for generic-prompt rejection and unexpected
  top-level/task fields.

## Excluded

- a real App Server startup, Provider request, model call, retry, replay, or
  preparation of a new live candidate;
- speculative App Server structured-output request fields;
- raw output, prompt, JSONL, stderr, stdout, transcript, credential, path,
  file, Artifact, workspace, Git, push, tag, Release, or deployment changes;
- relaxation of zero files, zero Artifacts, read-only, no tools, one call,
  zero retry, usage, cost, timeout, approval, or integrity requirements.

## Acceptance criteria

1. A generic or hand-written prompt cannot prepare a Board 14 experiment.
2. The canonical prompt names both frozen Worker IDs and the complete v2 JSON
   shape.
3. A valid local fixture plan succeeds, while top-level or task-field
   expansion fails closed with a privacy-safe diagnostic.
4. Exact empty dependencies are required; `null` is not accepted.
5. Focused and full offline tests, compilation, tracked JSON validation,
   current-tree and reachable-history privacy scans, and `git diff --check`
   pass.
6. One local-only commit is created without push, tag, Release, or real call.

## Next real-pilot boundary

This board grants no execution authority. A possible future attempt must use a
new candidate prepared after this board, then repeat the separate experiment
approval, arming, start-approval creation, start-approval approval, and exact
one-turn execution authorization sequence.
