# Model Council MVP

Model Council 是一个本地优先的多模型协作雏形。它不要求模型彼此建立网络连接，而是由一个管理员模型通过统一消息、共享任务库和 Artifact 文件，把不同模型的成果传递给彼此。

跨会话继续开发时，请先阅读：

- [`AGENTS.md`](AGENTS.md)
- [`docs/PROJECT_HANDOFF.md`](docs/PROJECT_HANDOFF.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/DEVELOPMENT_BOARDS.md`](docs/DEVELOPMENT_BOARDS.md)
- [`docs/START_HERE_NEXT_SESSION.md`](docs/START_HERE_NEXT_SESSION.md)

当前版本已经具备：

- 管理员模型生成结构化任务计划；
- 多个工作模型并行执行；
- 任务依赖和分波调度；
- 独立审查模型复核所有成果；
- 管理员模型综合最终答案；
- SQLite 持久化运行、任务和消息；
- SHA-256 内容寻址的 Artifact 文件库；
- `mock`、任意 `cli` 和 OpenAI-compatible HTTP 三类适配器；
- Codex `--json` JSONL 事件解析和最终消息提取；
- CLI 线程、usage、事件、耗时、退出码和 stderr 诊断；
- 不调用模型的 Adapter `doctor` 检查；
- Provider、Model、Agent和角色设置注册中心；
- `manual`、`auto`、`hybrid`三种角色分配模式；
- 配置同步、用户覆盖保护和敏感字段脱敏；
- 模型能力和边界声明；
- 超时、失败记录和确定性调度；
- 不依赖第三方 Python 包的可运行演示。

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
python -m model_council run "分析并设计一个个人知识库应用" --config config.example.json
```

查看最近运行：

```powershell
python -m model_council runs --config config.example.json
```

查看指定运行：

```powershell
python -m model_council status <RUN_ID> --config config.example.json
```

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

`status` 会同时显示运行、任务、结构化消息和 Artifact 元数据。

运行测试：

```powershell
python -m unittest discover -s tests -v
python scripts/privacy_scan.py --history
```

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
- 当前版本不会未经持久化权限修改用户主检出，也不会未经单次精确审批合并或丢弃 Git worktree；
- 真实 agent 的系统权限仍由对应 CLI、沙箱和操作系统控制。

## 目前刻意未做

- A2A 网络服务器；
- MCP 工具代理；
- Codex App Server 持久会话；
- 第二个真实 Agent 家族的客观评估；
- 审批中心、运行比较、备份和发布准备；
- Web/Electron 图形界面；
- 自动价格目录刷新、货币换算和按时间窗口预算；
- 人工审批页面；
- 多轮争论和动态重新规划。

这些属于下一阶段。当前目标是先验证最关键闭环：管理员分工、多个模型交换成果、独立复核、最终整合。
