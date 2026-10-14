# Model Council MVP

Model Council 是一个本地优先的多模型协作雏形。它不要求模型彼此建立网络连接，而是由一个管理员模型通过统一消息、共享任务库和 Artifact 文件，把不同模型的成果传递给彼此。

跨会话继续开发时，请先阅读：

- [`AGENTS.md`](AGENTS.md)
- [`docs/PROJECT_HANDOFF.md`](docs/PROJECT_HANDOFF.md)
- [`docs/PROJECT_GOAL.md`](docs/PROJECT_GOAL.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/DEVELOPMENT_BOARDS.md`](docs/DEVELOPMENT_BOARDS.md)
- [`docs/START_HERE_NEXT_SESSION.md`](docs/START_HERE_NEXT_SESSION.md)
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)

当前版本已经具备：

**协作闭环**

- 管理员模型生成结构化任务计划；
- 多个工作模型并行执行；
- 任务依赖和分波调度；
- 独立审查模型复核所有成果；
- 管理员模型综合最终答案；
- SQLite 持久化运行、任务、消息和 Artifact 元数据；
- SHA-256 内容寻址的 Artifact 文件库（持久化路径相对根目录，不含本机绝对路径）。

**模型接入**

- `mock`、任意 `cli`、OpenAI-compatible HTTP、Codex App Server 和 A2A 五类适配器；
- Codex `--json` JSONL 事件解析、最终消息提取、线程与 usage 诊断；
- 不调用模型的 Adapter `doctor` 检查。

**控制平面**

- Provider、Model、Agent 和角色设置注册中心；
- `manual`、`auto`、`hybrid` 三种角色分配模式；
- 启动发现：可执行、认证、权限、连通性与**版本**分项记录；
- 配置驱动的发现目录，可登记 GUI-only 应用并明确标注不可调用；
- 版本比较与推荐：正式版优先，推荐可被用户偏好覆盖，且永不自动替换绑定；
- 用量、费用与余额台账，区分实际、Provider 上报、估算与不可用；
- 聊天记录以外的确定性路由、能力与预算约束、不可变的路由决策证据。

**审批与隔离**

- 仅回环地址的本地产品界面与统一审批中心；
- Codex App Server 的精确出站上下文（prompt + cwd + 模型 + 沙箱）单次审批；
- 隔离 Git worktree、显式读写测试合并权限、有界修复与恢复；
- 真实 Agent 资质授权包：可由用户审查、可绑定角色、事实漂移即失效。

**门禁**

- 本地隐私扫描：当前树、可达历史、以及被忽略的本地运行数据三个口径；
- 发布候选校验；
- 隐私安全的本地备份与精确恢复；
- 不依赖第三方 Python 包的可运行演示（零依赖，只需 Python 3.11+）。

截至 2026-10-14 实测：**234 项离线测试全部通过**，46 张 SQLite 表，33 条已登记的
隐私条目。这些数字每块板都会变，请以实测为准。

## 架构

```text
用户目标
   |
管理员模型 -- 生成 JSON 任务计划
   |
确定性编排器 -- 校验身份、依赖、并发和边界
   |
   +-- 架构模型 ----+
   +-- 实现模型 ----+--> Artifact 仓库 + SQLite 消息黑板
   +-- 研究模型 ----+
   |
审查模型
   |
管理员模型 -- 最终综合
```

管理员模型负责提出计划，Python 编排器负责执行规则。模型无法绕过编排器直接扩大权限。

## 立即运行

项目只要求 Python 3.11 或更新版本。

```powershell
cd C:\path\to\model-council-mvp
python -m model_council demo "设计一个支持多模型协作的本地项目管理工具"
```

输出会写入：

```text
runtime/
├─ council.db
└─ artifacts/
```

查看 agent 清单：

```powershell
python -m model_council agents --config config.example.json
```

在不调用任何模型的情况下检查 Adapter：

```powershell
python -m model_council doctor --config config.codex.example.json
```

启动发现不会调用模型：

```powershell
python -m model_council discovery scan --config config.codex.example.json
python -m model_council discovery show --config config.codex.example.json
```

显式发现某个 Adapter 可见的模型：

```powershell
python -m model_council discovery models manager --config config.example.json
```

连接测试必须由用户显式选择。CLI Adapter 会在空临时目录中使用固定探针，
不传递项目目标、上下文、Agent 描述或 Artifact：

```powershell
python -m model_council discovery probe manager --config config.example.json
```

手动注册无法通过命令行发现的 GUI Agent：

```powershell
python -m model_council discovery register-gui desktop-reviewer `
  --name "Desktop Reviewer" --provider mock-local --model mock-general `
  --capability review --boundary "manual handoff" `
  --config config.example.json
```

发现记录会把 executable、authentication、permission、connectivity 和 models
分别保存。可执行文件存在不等于认证成功，配置了凭据也不等于远端验证通过。

查看项目、运行和角色用量：

```powershell
python -m model_council ledger summary --config config.example.json
python -m model_council ledger events --run <RUN_ID> --config config.example.json
python -m model_council ledger alerts --run <RUN_ID> --config config.example.json
```

设置用户拥有的预算：

```powershell
python -m model_council ledger set-budget project-cost `
  --scope project --metric cost --warning 5 --hard 10 --currency USD `
  --config config.example.json
```

Provider 余额只能显式查询，而且只有 Adapter 声明支持余额 API 时才会访问：

```powershell
python -m model_council ledger balance <PROVIDER_ID> --config config.example.json
```

账本分别标记 `actual`、`provider_reported`、`estimated` 和 `unavailable`。
未知值不会被当成零；存在 hard budget 而历史消费不可度量时，下一次调用会被保守阻断。

初始化并查看设置注册中心：

```powershell
python -m model_council settings sync --config config.example.json
python -m model_council settings show --config config.example.json
```

修改角色分配：

```powershell
python -m model_council settings assign detail_executor `
  --mode hybrid --agent implementer --model mock-general `
  --constraints '{"required_capabilities":["implementation"]}' `
  --config config.example.json
```

设置注册中心当前是未来本地设置界面的数据基础。JSON配置只负责提供初始值，
用户通过CLI或未来UI保存的值不会被后续同步覆盖。

运行自定义目标：

```powershell
python -m model_council run "分析并设计一个个人知识库应用" `
  --start-approval <PROJECT_RUN_APPROVAL_ID> --config <LOCAL_CONFIG>
```

`run` is the user-facing project entry point and requires a one-time
Supervisor project-run approval bound to the current ready team and exact goal.
The approval is consumed before any Adapter invocation. Use the local
Supervisor flow to create and approve it.

查看最近运行：

```powershell
python -m model_council runs --config config.example.json
```

查看指定运行：

```powershell
python -m model_council status <RUN_ID> --config config.example.json
```

## Release candidate status

Productization Boards 1 through 12 are complete. The prepared release
candidate is `0.2.0rc1`; it has not been tagged or published as a GitHub
Release. Run `python scripts/release_verify.py` from a clean synchronized
`main` checkout before creating any release artifact.

## Deterministic routing

Board 5 resolves persisted roles before any Adapter invocation. Inspect the
selected identity, evidence and rejected candidates with:

```powershell
python -m model_council routing decisions --run <RUN_ID> `
  --config config.example.json
```

`manual` never silently falls back. `auto` selects only eligible candidates.
`hybrid` preserves the preferred Agent and falls back only when the assignment
is unlocked. Unknown cost and latency remain unknown rather than becoming zero.

## Local settings interface

Board 6 adds a dependency-free local Web control surface. It binds to loopback
by default, reads and writes the same SQLite registry used by the CLI, and
never invokes a model, discovery probe, Provider balance API or external
service.

```powershell
python -m model_council web --config config.example.json
```

Open the printed local URL. The interface can edit user-owned Provider, Model,
Agent, role, application-setting and budget records. It also displays persisted
discovery observations, Artifact provenance, usage and cost evidence, budget
alerts, balance snapshots, configured Adapter capabilities and deterministic
routing explanations. Edit buttons prefill the local forms. Writes require a
per-process session token plus trusted Host and same-origin checks. Provider and
Agent configuration values continue to be redacted before SQLite storage.

## Persistent and remote interoperability

Board 7 adds persistent, audited protocol clients without enabling any real
endpoint by default:

- Codex App Server initialization, Thread start/resume, Turn execution and
  streaming Agent-message collection;
- A2A v1.0 Agent Card discovery, JSON-RPC message submission and Task polling;
- MCP 2025-11-25 stdio and Streamable HTTP clients;
- SQLite endpoint identities, sessions, protocol events and approvals;
- single-use human approval before every MCP tool call;
- HTTPS enforcement for non-loopback endpoints and environment-only
  credential references.

Start from `config.interop.example.json`. Every real endpoint requires
`invoke_enabled: true`; this is separate from enabling the registry record.

Inspect local interoperability state:

```powershell
python -m model_council interop show --config config.interop.example.json
python -m model_council interop sessions --config config.interop.example.json
python -m model_council interop approvals --config config.interop.example.json
```

MCP tool execution is deliberately two-step:

```powershell
python -m model_council interop request-tool local-tools echo `
  --arguments '{"text":"local request"}' `
  --config config.interop.example.json
python -m model_council interop approve <APPROVAL_ID> `
  --config config.interop.example.json
python -m model_council interop call-tool <APPROVAL_ID> `
  --config config.interop.example.json
```

Approval is consumed once before transport execution. The local settings page
also shows endpoints, sessions, events and pending approval controls.

## Controlled Codex pilot

Board 8 adds a prompt-level gate in front of the existing App Server
`invoke_enabled` gate. Start from `config.pilot.example.json`, copied to an
untracked local file. It deliberately contains one read-only Codex architect,
with the manager and reviewer kept on `mock`.

Set `MODEL_COUNCIL_SYNTHETIC_CWD` to an existing generic synthetic directory
outside any personal home path, for example `C:\model-council-synthetic`.
The exact approval scope includes this resolved working directory, model,
sandbox and approval policy in addition to the prompt.

When an enabled synthetic run reaches the architect, Model Council records a
local pending manifest and stops before App Server startup. Inspect the exact
prompt locally, obtain explicit user authorization for that exact scope, then
approve the displayed digest once:

```powershell
python -m model_council interop contexts --config <LOCAL_CONFIG>
python -m model_council interop context <MANIFEST_ID> --show-prompt `
  --config <LOCAL_CONFIG>
python -m model_council interop context <MANIFEST_ID> `
  --approve-sha256 <DISPLAYED_APPROVAL_SHA256> --config <LOCAL_CONFIG>
python -m model_council run "<SAME_SYNTHETIC_GOAL>" `
  --outbound-manifest <MANIFEST_ID> --config <LOCAL_CONFIG>
```

The initial policy allows synthetic text only: zero files, zero Artifacts and
at most 8,192 UTF-8 bytes across prompt and transport metadata. It rejects
repository context, credential/path patterns, personal home-directory paths
and any changed or replayed scope.

One live synthetic Codex App Server run completed functionally, but its first
manifest covered only the Turn prompt and not the `thread/start` working
directory. That run may therefore have disclosed its absolute synthetic
directory path through Codex environment context. The strengthened combined
scope gate is deterministic, runs before process startup and is covered by
automated tests. Under the privacy triage policy, a second live validation is
optional and does not block Board 9. No repository-content, A2A or MCP live
verification is claimed.

## Isolated Git workspaces

Board 9 adds a local control plane for writing Agents without granting direct
access to the user's primary checkout. Each lease creates one linked Git
worktree under ignored runtime state and starts with read permission only.
Write, test and merge permissions are enabled separately and persisted in
SQLite.

A typical local workflow is:

```powershell
python -m model_council workspace prepare C:\path\to\synthetic-repo writer `
  --config <LOCAL_CONFIG>
python -m model_council workspace permission <LEASE_ID> write allow `
  --config <LOCAL_CONFIG>
python -m model_council workspace permission <LEASE_ID> test allow `
  --config <LOCAL_CONFIG>
python -m model_council workspace checkpoint <LEASE_ID> `
  --message "Apply reviewed Agent change" --config <LOCAL_CONFIG>
python -m model_council workspace test <LEASE_ID> `
  --command-json '["python","-m","unittest","discover","-s","tests","-v"]' `
  --config <LOCAL_CONFIG>
python -m model_council workspace diff <LEASE_ID> --config <LOCAL_CONFIG>
python -m model_council workspace permission <LEASE_ID> merge allow `
  --config <LOCAL_CONFIG>
python -m model_council workspace request-merge <LEASE_ID> `
  --config <LOCAL_CONFIG>
```

The pending merge displays a `scope_sha256` bound to the clean target SHA,
Agent branch SHA, bounded diff evidence and a passing test captured at that
exact branch state. Approve and consume it once:

```powershell
python -m model_council workspace approve <APPROVAL_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council workspace merge <APPROVAL_ID> `
  --config <LOCAL_CONFIG>
```

Merge is fast-forward only and fails if the target branch, target SHA, Agent
branch, worktree cleanliness or evidence changes. Destructive discard uses the
same two-step approval pattern. Git and test subprocesses are argument arrays
with `shell=False`; stdout/stderr retention is bounded while hashes cover the
complete streams.

## Bounded repair and recovery

Board 10 layers a persistent reviewer-writer state machine over one active
Board 9 lease. A session starts only after read, write and test permissions are
present. Every iteration begins at a clean head, captures a checkpoint, runs
the configured test, collects diff evidence and records `accept` or `repair`.

Start and inspect a local manual session:

```powershell
python -m model_council repair start <LEASE_ID> `
  "Fix the bounded synthetic task" --reviewer reviewer `
  --test-command-json '["python","-m","unittest"]' `
  --max-iterations 3 --max-changed-files 50 `
  --config <LOCAL_CONFIG>
python -m model_council repair begin <SESSION_ID> --config <LOCAL_CONFIG>
python -m model_council repair capture <SESSION_ID> --config <LOCAL_CONFIG>
python -m model_council repair bundle <SESSION_ID> --config <LOCAL_CONFIG>
python -m model_council repair review <SESSION_ID> `
  --decision repair --feedback "Address the failing evidence." `
  --config <LOCAL_CONFIG>
```

Limits cover iterations, elapsed time, changed files, diff bytes, feedback
bytes and optional token/cost budgets. Unknown usage blocks conservatively
when its hard budget is enabled. A reviewer cannot accept failing tests.
Interrupted writer/reviewer stages require explicit `repair recover` actions;
no recovery path automatically deletes, rebases, merges or deploys.

After acceptance, `repair request-merge` only creates the existing Board 9
pending approval. The user must still inspect and approve its exact digest.

Board 10 is local-only: it does not invoke an Adapter or send a review bundle
to a model. Real writer/reviewer integration requires a later exact
outbound-context approval.

## Objective second-family evaluation

Board 11 adds one DeepSeek Responses candidate in the sole
`synthetic_evaluator` role. `config.evaluation.example.json` keeps
`invoke_enabled` false and references only
`MODEL_COUNCIL_DEEPSEEK_API_KEY`.

The fixed evaluation asks for exactly `MC-EVAL-ORBIT-42`. It sends no files or
Artifacts, allows at most 4,096 bytes of prompt plus transport metadata and
rejects an HTTP response larger than 16,384 bytes. SQLite records the expected
and observed hashes, byte counts, objective assertions, failure class and
usage-ledger reference without copying response text into evaluation tables.
Non-loopback endpoints require HTTPS, and HTTP redirects are rejected.

Prepare and inspect the exact local scope:

```powershell
python -m model_council evaluation prepare deepseek_evaluator `
  --config config.evaluation.example.json
python -m model_council evaluation context <EVALUATION_ID> --show-prompt `
  --config config.evaluation.example.json
```

Running requires a local untracked configuration with
`invoke_enabled: true`, the credential environment variable, and an explicit
one-time approval of the displayed scope digest:

```powershell
python -m model_council evaluation context <EVALUATION_ID> `
  --approve-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council evaluation run <EVALUATION_ID> `
  --outbound-manifest <MANIFEST_ID> --config <LOCAL_CONFIG>
```

A prepared manifest, credential presence, Board 8 pilot approval, Board 9
workspace permission or Board 10 repair acceptance does not authorize this
call. Local fake-server tests exercise the complete flow without contacting an
external service.

One explicitly authorized live synthetic evaluation consumed its manifest
once. DeepSeek returned a valid Responses result in 1,009 ms with 236
provider-reported tokens, but the 131-byte response did not equal the required
16-byte token. The objective evaluation therefore failed without retry or
fallback. This outcome is retained as evidence rather than weakened into a
pass.

## Product interface and approval center

Board 12 expands the loopback Web interface into the local product surface:

```powershell
python -m model_council web --config config.example.json
```

It displays the unified approval center, workspace permissions and bounded
evidence, repair sessions and iterations, objective evaluations, pairwise run
comparison and local backup/restore. Refresh remains read-only.

Approving never consumes an action. External invocation, MCP execution,
workspace merge/discard and restore still require their separate CLI or UI
consumption step and the same service-level revalidation.

## Local backup and restore

Create the privacy-safe database-only default:

```powershell
python -m model_council backup create --config config.example.json
```

Include registered Artifacts explicitly:

```powershell
python -m model_council backup create --include-artifacts `
  --config config.example.json
```

Restore is deliberately three-step:

```powershell
python -m model_council backup request-restore <BACKUP_ID> `
  --config config.example.json
python -m model_council backup approve <APPROVAL_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config config.example.json
python -m model_council backup restore <APPROVAL_ID> `
  --config config.example.json
```

Backups stay below ignored runtime state. They never include credentials,
environment files, repositories or worktrees. Restore creates a safety backup,
rechecks the exact state and only adds missing hash-verified Artifacts.

Compare two local runs:

```powershell
python -m model_council compare runs <LEFT_RUN_ID> <RIGHT_RUN_ID> `
  --config config.example.json
```

Unknown cost remains unknown instead of becoming zero.

## Local team Supervisor

Board 13 adds a local-only Supervisor that binds one Manager, Worker and
Reviewer Agent+Model team. The wizard imports a local JSON file containing
only synthetic readiness checks; it does not invoke an Adapter or contact a
service.

```powershell
python -m model_council supervisor wizard `
  --team-file config.supervisor.team.example.json `
  --config config.example.json
python -m model_council supervisor check --config <LOCAL_CONFIG>
python -m model_council supervisor snapshot --config <LOCAL_CONFIG>
python -m model_council supervisor request-run <SNAPSHOT_ID> `
  "分析并设计一个个人知识库应用" --config <LOCAL_CONFIG>
python -m model_council supervisor approve <APPROVAL_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council run "分析并设计一个个人知识库应用" `
  --start-approval <APPROVAL_ID> --config <LOCAL_CONFIG>
```

The older `supervisor request-start` / `supervisor start` commands remain
separate local synthetic Manager-platform controls. They do not authorize a
project run.

Before considering any real Agent qualification, validate a local declaration
with the pure offline preflight. It does not load project configuration,
initialize runtime state, start a process or contact any endpoint:

```powershell
python -m model_council supervisor qualification-preflight `
  --candidate-file <LOCAL_QUALIFICATION_JSON>
```

The command requires explicit lifecycle checks, read-only permissions, private
context exclusions, bounded token/cost/time limits, a single-attempt stop rule,
the separate approval ladder and runtime-only evidence policy. It always
returns `execution_authorized: false`; a successful preflight is not a real
Agent qualification or execution approval.

For a configured non-mock role, bind the eligible preflight to the Supervisor
role before creating a team snapshot:

```powershell
python -m model_council supervisor qualification-bind manager `
  --candidate-file <LOCAL_QUALIFICATION_JSON> --config <LOCAL_CONFIG>
```

The binding stores only sanitized scope metadata and its digest in local
ignored runtime state. Role or scope drift invalidates downstream approvals.

```powershell
python -m model_council supervisor request-start <SNAPSHOT_ID> `
  --config <LOCAL_CONFIG>
python -m model_council supervisor approve <APPROVAL_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council supervisor start <APPROVAL_ID> --config <LOCAL_CONFIG>
```

Readiness covers process, login, Model, permission, version and connection.
Unavailable machine evidence is `user_confirmation_required`, never ready by
assumption. A snapshot requires all three roles ready. Configuration or
readiness evidence drift makes the SHA-256-bound start approval stale. In this
first local phase, `start` writes only a synthetic local Manager-platform audit
event; it does not start a real task, process, network connection or model.
The tracked example deliberately requires an explicit reviewer-connection
confirmation; copy it to an untracked local file before replacing synthetic
checks with future local experiments.

## Controlled local experiments

Board 14.0 adds an offline experiment harness. Board 14.1 prepares a disabled
Codex Manager plus two fake Worker candidate and stops before invocation.

Start with local copies of:

```text
config.board14.example.json
config.board14.team.example.json
config.experiment.board14-fake.example.json
config.experiment.board14-codex.example.json
```

After creating and confirming a current Supervisor team snapshot, replace the
placeholder snapshot ID in an untracked experiment spec:

```powershell
python -m model_council experiment prepare `
  --spec-file <LOCAL_EXPERIMENT_JSON> --config <LOCAL_CONFIG>
python -m model_council experiment show <EXPERIMENT_ID> `
  --show-prompt --config <LOCAL_CONFIG>
```

Board 14.0 can be exactly approved, armed and simulated locally:

```powershell
python -m model_council experiment approve <EXPERIMENT_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council experiment arm <EXPERIMENT_ID> `
  --config <LOCAL_CONFIG>
python -m model_council experiment simulate <EXPERIMENT_ID> `
  --config <LOCAL_CONFIG>
```

For `real_codex`, `arm` only revalidates the exact scope. A controlled
executor may start one turn only after a separately approved, SHA-256-bound
start approval; it revalidates the team, identities, scope and source
integrity before process creation. The fake simulator still rejects that mode.
Each real turn remains single-use and requires its own explicit local
authorization.

Board 14 is complete only for one local-private synthetic Manager execution.
It does not enable the public candidate, authorize a repeat, or change the
published `0.2.0rc1` release candidate. See
`docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md`.

`status` 会同时显示运行、任务、结构化消息和 Artifact 元数据。

运行测试：

```powershell
python -m unittest discover -s tests -v
python scripts/privacy_scan.py --history
python scripts/privacy_scan.py --local-state
python scripts/release_verify.py
```

`--local-state` 会检查被 `.gitignore` 排除的 `runtime/` 与 `runtime-*`。默认的
`--history` 只看 Git 跟踪与非忽略路径，因此那些目录对它完全不可见；两者是不同
的口径，发布门禁用前者，搬迁工作目录前用后者。

## Real-Agent qualification authorization package

这是"到真实调用之间"的最后一个离线环节：把一次未来真实 Agent 资质的请求做成
**可审查、可摘要、可失效**的对象。它不启动任何东西。

```powershell
python -m model_council authorization build --candidate-file <声明.json>
python -m model_council authorization verify --package-file <包.json>
python -m model_council supervisor authorization-bind manager --package-file <包.json>
python -m model_council supervisor authorization-show [--role manager]
```

`build` 是纯校验，不落盘。`bind` 才会写一条本地记录，并捕获当前团队快照。

三个必须知道的行为：

- **工作目录只以"类别 + 环境变量名"出现**，例如
  `{"category": "synthetic_workspace", "env_var": "MODEL_COUNCIL_SYNTHETIC_CWD"}`，
  所以跟踪文件里永远不会出现本机绝对路径；
- **缺证据时状态是 `user_confirmation_required`**，这是构造性的：七个生命周期
  事实默认 `unknown`，没有提供观测值就不会变成可审查，
  也就是说默认产出的是**一个问你的问题**，不是放行；
- **事实状态绑进了包摘要**，任何观测值变化都会改变 `package_sha256`。
  重新读取时会重新推导，所以被篡改的包报 `invalid`、事实漂移的报 `stale`、
  团队快照过期的报 `superseded`。

绑定**不创建启动审批、不启动进程、不授予任何权限**。

## Agent 版本与发现目录

发现目录是**配置数据**，不是代码。加一个工具不需要改模块：

```json
"discovery_targets": [
  {"key": "myagent", "display_name": "My Agent",
   "command_candidates": ["myagent.cmd", "myagent"],
   "version_arguments": ["--version"],
   "extra_path_patterns": ["C:/Programs/MyAgent/*.exe"]}
],
"gui_only_targets": [
  {"key": "some-desktop-app", "display_name": "Some Desktop App",
   "command_candidates": [], "version_arguments": [],
   "interface_kind": "gui_only"}
]
```

`interface_kind` 只有两个取值：`cli`（控制面可以自己调用）与 `gui_only`
（不可以，只登记可见性与手工移交）。声明成 `cli` 却没有任何命令会在**配置加载时
直接报错**，不会静默通过。

同一 Agent 存在多个安装时，会各自探测版本并按规则推荐：

| 层级 | 规则 |
| --- | --- |
| 比较两个版本 | 正式版只胜过**同号**的候选版：`1.35.0` > `1.35.0-rc.1` |
| 排序候选集 | 只要存在正式版，就不推荐任何候选版：`1.34.9` 胜过 `1.35.0-rc.1` |

排序规则可关闭（退化为纯数字比较）。**推荐永远不是替换**：任何结果都带
`auto_switch: false`，且显式指定的 `preferred_version` 一定优先于推荐，
会记为 `user_preference` 并把被压过的版本列进 `alternatives`。

无法比较的版本（例如 `latest` 与 `1.35.0` 混在一起）返回 `undecidable`，
**不给推荐、不猜**。

版本探测是参数数组、`shell=False`、有超时，只问工具自己的版本，不发送任何项目上下文。

## 接入 Codex

复制 `config.codex.example.json` 后修改。Windows 示例通过 stdin 把完整任务交给
`codex exec -`，并使用 JSONL 事件流：

```json
{
  "type": "cli",
  "command": [
    "codex.cmd",
    "exec",
    "--ephemeral",
    "--skip-git-repo-check",
    "--sandbox",
    "read-only",
    "--color",
    "never",
    "--json",
    "-"
  ],
  "output_format": "codex_jsonl"
}
```

第一轮建议只让一个角色使用真实 Codex，其他角色继续使用 mock。确认运行、权限和输出都稳定后，再逐个替换。

`codex_jsonl` 模式不会把推理事件当作最终答案，只读取最后一个完成的
`agent_message`。线程 ID、事件类型统计和 usage 会作为任务消息元数据保存。

Codex 默认应保持只读。需要让执行 agent 修改项目时，应给它独立 Git worktree，并在人工确认后才启用工作区写权限。

如果在 Codex Desktop 自身的受限任务环境中调用打包的 `codex.exe` 出现
Windows“拒绝访问”，请在普通用户 PowerShell 中运行本项目，或改用后续的
App Server/API Adapter。这是宿主进程权限边界，不代表 CLI Adapter 的参数协议失败。

## 接入 OpenAI-compatible API

不要把密钥写进 JSON。配置环境变量：

```powershell
$env:MODEL_COUNCIL_API_KEY = "..."
```

然后使用：

```json
{
  "type": "openai_compatible",
  "base_url": "https://example.com/v1",
  "api_key_env": "MODEL_COUNCIL_API_KEY",
  "model": "your-model-id",
  "api_style": "responses",
  "max_response_bytes": 16384,
  "outbound_context": {
    "source": "synthetic",
    "allowed_sources": ["synthetic"],
    "max_files": 0,
    "max_total_bytes": 4096,
    "max_artifacts": 0,
    "max_artifact_bytes": 0
  },
  "invoke_enabled": false
}
```

可选的 `api_style`：

- `responses`
- `chat_completions`

并非所有声称兼容 OpenAI API 的服务都完整支持这两种接口，需要按提供商实际行为验证。

## 安全边界

- 公开发布前必须执行 [`docs/PRIVACY.md`](docs/PRIVACY.md) 的全仓检查；
- 不得提交真实本机路径、用户名、个人邮箱、凭据或私有项目内容；
- CLI 调用始终使用参数数组和 `shell=False`；
- 不从配置执行拼接后的 shell 字符串；
- API 密钥只读取环境变量；
- 每个任务都有明确的目标 agent；
- Artifact 通过哈希定位，消息只传引用；
- 本地持久化的 Artifact 路径是**相对于 Artifact 根目录**的，不写本机绝对路径；
- 当前版本不会未经持久化权限修改用户主检出，也不会未经单次精确审批合并或丢弃 Git worktree；
- 真实 agent 的系统权限仍由对应 CLI、沙箱和操作系统控制。

隐私有两个不同口径，不要混用：

| 命令 | 作用范围 | 用途 |
| --- | --- | --- |
| `privacy_scan.py` | Git 已跟踪 + 未忽略的未跟踪文件 | 每次板块完成的公开门禁 |
| `privacy_scan.py --history` | 加上可达的全部历史 blob 与提交者域名 | 公开推送前的门禁 |
| `privacy_scan.py --local-state` | 加上被忽略的 `runtime/`、`runtime-*` | 搬迁、归档或迁移工作目录之前 |

第三个口径是被忽略的本地运行数据。它不进 Git，但**仍可从这台机器或它的任何副本读出**，
所以在本机隐私要求下也是一个需要检查的面。

## 目前刻意未做

判断"未做"时请注意区分三种状态，混为一谈会误判项目进度。

**尚未实现**

- 自动价格目录刷新、货币换算和按时间窗口预算；价格表目前是操作者声明的；
- 多轮争论与动态重新规划：管理者只做一次规划、一次综合，worker 失败后不重规划；
- worker 之间的交互式问答：目前只能通过已存结果和最终上下文传递；
- 通用上下文摘要，需要先有经审查的留存与披露政策；
- 远程节点认证与签名；
- Artifact 保留与清除策略（需要独立的冻结板块与单独授权）；
- Electron 打包与更广的操作台工作流。

**已实现但只对本地假服务器验证过**

- A2A 与 MCP 的真实第三方端点：协议客户端与审批都已实现，但没有验证过任何真实远端；
- Codex App Server：已对仓库内的假服务器完整验证，并有过一次真实只读合成运行。

**已实现但没有生产入口**

- `RepairService.run_local_until_terminal()` 与 `WorkspaceService.invoke_cli()`：
  两条路径目前只被测试使用，是明确标注的本地回调与假 CLI 演练，
  不是遗漏的接线。

**已决定不启动**

- Board 16 的本地传输可靠性加固：只观察到一次不可复现的 Windows 回环中断，
  除非先拿到可复现的失败测试，否则不启动。

当前阶段的目标仍是那个最关键闭环：管理员分工、多个模型交换成果、独立复核、最终整合。
真正没有验证过的不是这些机制，而是**它们面对真实 Agent 时的行为**。
