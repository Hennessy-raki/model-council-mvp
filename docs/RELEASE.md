# Model Council 0.2.0rc1

Date: 2026-08-31

Model Council remains a local-first control plane. Release candidate
`0.2.0rc1` includes the complete productization sequence through Board 12:

- persistent Provider, Model, Agent, role and application settings;
- Artifact provenance and content-addressed storage;
- startup discovery and project-neutral probes;
- normalized usage, cost, budget and balance evidence;
- deterministic routing explanations;
- loopback-only product interface;
- Codex App Server, A2A and MCP interoperability contracts;
- exact outbound-context approval;
- isolated Git workspaces and exact merge/discard approval;
- bounded reviewer-writer repair and recovery;
- one objective DeepSeek synthetic evaluation;
- unified local approval/evidence views, run comparison and backup/restore.

## Safety posture

- SQLite remains authoritative.
- Credentials are environment-variable references only.
- External context, MCP tools, workspace merge/discard and restore retain
  separate exact approvals.
- Worktrees, runtime databases, backups, prompts, responses, diffs, repair
  feedback and private project evidence remain ignored local state.
- A UI action cannot grant itself permission or bypass deterministic service
  checks.

## Verification

Run from a clean published `main` checkout:

```powershell
python scripts/release_verify.py
```

The command verifies local refs, clean state, version consistency, required
documentation, tracked-file privacy, all offline tests, Python compilation,
all tracked JSON parsing and full-history privacy scanning.

Independently verify the public ref after push:

```powershell
git ls-remote origin refs/heads/main
```

No Git tag or GitHub Release is created automatically.
