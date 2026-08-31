# Board 14.2 Plan: Offline Codex App Server Execution Verification

Date: 2026-08-31

Status: scope frozen and accepted after local fixture verification

## Goal

Verify the already-present Codex App Server protocol client against a
repository-controlled local fake App Server, then add the missing Board 14
stop-rule enforcement for any server-side approval request.

This is an offline protocol verification step. It is not authorization to
start `codex app-server`, invoke Codex, send a prompt to PackyAPI, or call any
other Provider.

## Scope

- one repository-controlled Python JSON-lines fixture;
- one synthetic request with no files or Artifacts;
- read-only sandbox and `approval_policy: "never"`;
- disabled plugins, remote plugins and apps in the Board 14 public candidate;
- one local process per test, no network listener or HTTP request;
- deterministic inspection of initialize, thread/start, turn/start, rejected
  approval-request and turn-completion protocol messages;
- local temporary SQLite only, with raw test output excluded from Git.

## Required change

The generic App Server Adapter currently declines server-side command or file
approval requests, then may continue reading the turn. Board 14 needs a
stricter policy: if its Manager receives any approval request, it must decline
the request, stop the local transport immediately, record bounded failure
metadata, and produce no Manager answer.

The stricter behavior must be opt-in and represented by a boolean
`strict_no_approvals` Agent setting. Existing interoperability behavior remains
unchanged unless that setting is enabled.

## Offline acceptance criteria

1. `strict_no_approvals` is type-validated and defaults to false.
2. The public Board 14 Codex candidate enables the strict policy while keeping
   `invoke_enabled: false`.
3. The existing fake App Server test still proves normal persistent-session
   protocol behavior and local rejection of a command request.
4. A strict-policy test proves that the same request ends the invocation
   without accepting a command, returning a Manager answer, or retrying.
5. Tests use only the repository fixture and synthetic text; they do not start
   the configured `codex.cmd app-server` candidate.
6. Full offline tests, compilation, JSON validation, current-tree privacy
   scan, reachable-history privacy scan and `git diff --check` pass.

## Deferred real-pilot gates

No existing Board 14.1 approval authorizes a live call. After the offline
verification is accepted, a new exact real-pilot manifest must bind the final
executor behavior, current team snapshot, exact prompt, command, working
directory, model, limits and stop rules.

The user must separately approve:

1. revalidation and arming, without starting App Server; and
2. one-time startup plus one exact `turn/start` request, including the new
   manifest SHA-256.

Any configuration, identity, prompt, transport or executor-policy change
invalidates that candidate and requires a new displayed scope.

## Excluded

- real Codex App Server startup;
- PackyAPI, OpenAI, Reasonix, ZCode, MCP, A2A or HTTP calls;
- real model output;
- repository, user workspace, credentials, files or Artifacts in context;
- workspace writes, Git operations, concurrent Agents, pushes, tags or
  releases.
