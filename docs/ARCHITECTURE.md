# Architecture

## 控制平面与认知平面

Model Council 把系统分为两部分：

1. 认知平面：管理员模型和专业模型负责推理、提出计划与生成成果。
2. 控制平面：确定性 Python 程序负责身份、权限、依赖、消息、超时和持久化。

这意味着管理员模型可以请求任务分派，但只有编排器能够真正调用某个 agent。

## 一次运行的生命周期

```text
run.created
  -> manager.plan.requested
  -> tasks.created
  -> task.assigned
  -> task.completed / task.failed
  -> reviewer.assigned
  -> review.completed
  -> manager.synthesis.requested
  -> run.completed / run.failed
```

每一步都会记录到 SQLite。文本成果同时写入内容寻址 Artifact 仓库。

## 模型通信

模型通信不是模型之间建立 socket，而是：

1. 发送者把结果提交给编排器；
2. 编排器保存结果并生成 Artifact；
3. 编排器写入结构化消息；
4. 接收者获得经过筛选的上下文和 Artifact 引用。

因此可以替换任意模型，而不改变上层工作流。

## Startup discovery and setup

Discovery observes and records local model hosts; it does not select project
roles. Every target keeps separate executable, authentication, permission,
connectivity and model status.

`discovery scan` inspects configuration and known local commands without a
model call. Model enumeration is delegated only to Adapters that declare the
capability. `discovery probe` is explicit and a CLI probe runs a fixed prompt
from an empty temporary directory without project goals, Agent descriptions,
conversation context or Artifact references.

GUI-only Agents can be registered manually. Their registry and discovery
records are user-owned and cannot be overwritten by later config sync or local
command scanning.

## Usage, cost and balance ledger

Every Adapter invocation creates one immutable `usage_events` record. Locally
observed request counts and duration are `actual`; values returned by a model
host are `provider_reported`; heuristic tokens and configured-price
calculations are `estimated`; missing values remain `unavailable`.

Project, run and role totals are computed from these records. Budget policies
are deterministic control-plane rules. Warning thresholds create audit alerts.
Hard limits block later calls once reached. If a hard limit depends on values
that are unavailable, the control plane blocks conservatively instead of
treating unknown consumption as zero.

Provider balance is never inferred from model prices or usage. It is queried
only through an Adapter that explicitly declares a supported balance API, and
the resulting snapshot records its source and currency.

## Adapter

每个模型承载工具都实现同一个接口：

```python
class AgentAdapter:
    def invoke(self, request: AgentRequest) -> AgentResponse:
        ...
```

当前实现：

- `MockAdapter`：离线演示与测试；
- `CliAdapter`：Codex、Claude、Gemini、OpenCode 等 CLI；
- `OpenAICompatibleAdapter`：Responses 或 Chat Completions 风格 HTTP API。

下一阶段可增加：

- `CodexAppServerAdapter`；
- `A2AAdapter`；
- `MCPToolBroker`；
- 各厂商原生 SDK Adapter。

## 任务图

管理员返回任务键和依赖：

```json
{
  "tasks": [
    {
      "key": "architecture",
      "title": "设计架构",
      "instruction": "定义模块与数据流",
      "agent": "architect",
      "depends_on": []
    },
    {
      "key": "implementation",
      "title": "制定实现方案",
      "instruction": "根据架构给出实现步骤",
      "agent": "implementer",
      "depends_on": ["architecture"]
    }
  ]
}
```

编排器校验 agent 名称和依赖，按依赖分波执行。同一波任务可以并行。

## Artifact

Artifact 路径由内容哈希决定：

```text
runtime/artifacts/ab/abcdef...md
```

SQLite 保存逻辑名称、媒体类型、任务、哈希和相对路径。相同内容可以复用同一个物理文件。

## 设置与注册中心

SQLite同时保存Provider、Model、Agent、角色分配和应用设置。

```text
Provider
  -> Model
  -> Agent profile
  -> Role assignment
```

JSON配置是种子数据，不是设置界面的唯一事实来源。配置同步不会覆盖来源为
`user`的记录，也不会删除配置文件中缺失的手动或自动发现记录。

角色分配支持：

- `manual`
- `auto`
- `hybrid`

自动选择逻辑将在发现、能力和费用数据可用后实现。当前版本只持久化选择模式、
用户锁定和结构化约束。

## Deterministic routing policy

The `RoutingService` resolves every persisted project role before its Adapter is
invoked. It consumes the existing role registry, Agent and Model capabilities,
discovery observations, usage and cost history, hard-budget state and prior
routing decisions.

Manual assignments fail rather than silently replacing an unusable identity.
Automatic assignments consider only eligible configured Adapters. Hybrid
assignments preserve the preferred Agent and use deterministic fallback only
when unlocked. Missing cost or latency remains unknown and cannot satisfy a
hard maximum unless the assignment explicitly permits unknown evidence.

Every success or failure creates an immutable `routing_decisions` row containing
the requested and selected identities, constraints, bounded evidence, rejected
candidates and reason codes. Manager suggestions are preferences only; they
cannot override locks, budgets, separation constraints or permission evidence.

## Persistent and remote interoperability

Board 7 keeps protocol cognition behind Adapters and durable control evidence
in SQLite:

```text
configured remote identity
  -> explicit invoke_enabled gate
  -> protocol Adapter or MCP broker
  -> interoperability session
  -> immutable inbound/outbound events
  -> local message, Artifact and usage contracts
```

`CodexAppServerAdapter` initializes a local app-server process for each call,
resumes the durable remote Thread ID when present, starts one Turn and persists
the protocol exchange. Server approval requests are recorded and declined by
default; the Adapter never grants itself command or file-change permission.

Board 8 places a local outbound-context approval gate before App Server
startup. The Adapter renders a prompt without local run IDs or Artifact paths
and combines it with the exact App Server transport context: resolved `cwd`,
model, sandbox and approval policy. The ignored local manifest records prompt
and scope SHA-256 values, byte counts, section digests, policy limits and
status. Personal Windows/POSIX home paths are rejected. The App Server receives
nothing until a human has reviewed the whole scope and approved its matching
digest; approval is consumed atomically before transport startup.
Protocol-event audit records use the manifest ID, digest and byte count instead
of copying prompt text.

`A2AAdapter` validates HTTPS for non-loopback endpoints, persists Agent Card
observations, submits a JSON-RPC Message and polls returned Tasks to a terminal
state. Authentication values are read only from named environment variables.

`MCPToolBroker` supports stdio and Streamable HTTP. Listing tools is explicit.
Calling a tool requires a persisted approval that is approved and consumed
exactly once before the transport request. Stdio commands remain argument
arrays with `shell=False`.

The local settings interface projects endpoints, remote identity observations,
sessions, protocol events and approval controls. Browser approval cannot bypass
the same persisted single-use check enforced by the broker.

## Isolated Git workspaces

Board 9 adds a separate `WorkspaceService` control plane. It does not let the
manager model create permissions. A local operator creates one lease for one
writing Agent, and the lease begins with only `read=true`.

```text
clean target checkout
  -> ignored runtime/worktrees/<opaque lease id>
  -> explicit read/write/test/merge permissions
  -> Agent checkpoint on isolated branch
  -> bounded test and diff evidence
  -> exact pending merge or discard approval
  -> SHA-256 confirmation and single consumption
  -> fast-forward merge or destructive cleanup
```

SQLite stores the lease, repository/worktree paths, permissions, bounded
stdout/stderr excerpts, full-stream hashes, evidence metadata and approval
state. This data is local runtime state because paths, diffs and test output may
identify a workstation or contain private downstream-project material.

Worktree paths are generated below the configured runtime root and must be
ignored when that root is inside the target repository. Git refs use an opaque
lease identifier rather than an Agent name. Every subprocess uses an argument
array and `shell=False`. Test output retains at most 64,000 bytes per stream;
diff output retains at most 128,000 bytes; complete output hashes remain
available for evidence comparison.

Merge permission depends on read, write and test permission. A merge approval
can be requested only when the target and Agent worktree are clean, the target
has not moved, the Agent branch is a fast-forward, and current diff plus
passing-test evidence match the exact source SHA. Dirty discard approvals hash
tracked changes and up to 1,000 untracked files / 64 MiB of untracked content.
Any state drift makes the approval stale. Board 9 does not add automatic
reviewer-writer retries, rebases, conflict repair or deployment.

## Bounded repair state machine

Board 10 adds `RepairService` above `WorkspaceService`:

```text
waiting_writer
  -> writer_running
  -> checkpoint + test + diff + inventory
  -> waiting_review
  -> reviewer_running
  -> repair_requested | accepted | limit_reached
```

SQLite stores sessions, iterations and bounded events. The session policy caps
iteration count, elapsed time, changed files, diff bytes, feedback bytes and
optional token/cost totals. Unknown usage remains unknown and blocks a further
call when a corresponding hard budget exists.

The reviewer cannot override test evidence: `accept` is rejected unless the
bound test record passed. A repair decision stores bounded feedback for the
next writer attempt. Acceptance stores the exact clean Git head and can only
request the existing Board 9 merge approval while that head remains unchanged.

`recovery_required` is explicit. A writer may retry only when it changed no Git
state; dirty or committed interrupted work must be explicitly captured or the
session explicitly failed. Captured reviewer evidence can be retried without
running the writer again. Cancellation and failure never delete the worktree.

Repair goals, feedback, filenames and evidence excerpts remain private local
runtime data. Board 10's automatic driver accepts injected local callbacks and
has no Adapter/network path.

## Objective Agent evaluation

Board 11 adds `EvaluationService` for one DeepSeek Responses candidate and one
fixed `synthetic_evaluator` case:

```text
fixed local oracle
  -> exact prompt plus HTTP transport manifest
  -> explicit one-time scope approval
  -> invoke_enabled gate
  -> one bounded Responses request
  -> hash/byte/duration/usage assertions
  -> passed or failed, with no retry or fallback
```

The prompt contains no repository, worktree, repair, file or Artifact context.
The manifest binds endpoint, request URL, model, API style, payload fields,
static header shape, credential environment-variable name and byte limits.
The credential value is never included. The candidate response is limited
before JSON parsing; evaluation tables retain only hashes, byte counts,
assertions, failure class and ledger references.

The evaluation is separate from manager planning, reviewer acceptance and
routing. It cannot grant worktree permissions, request a merge, submit repair
feedback or reuse a prior Board 8-10 approval. Loopback fake servers may
exercise the same path with temporary test configuration.

## 下一阶段边界

优先级顺序：

1. preserve Board 8 external-context approval and Board 9 merge authority;
2. finish the one DeepSeek Board 11 evaluation only after exact context
   authorization;
3. complete and publish Board 11 before starting Board 12 product UI and
   release work;
4. keep repair evidence local unless the user approves its exact disclosure.

The Board 6 interface is a loopback-only presentation and local mutation layer
over SQLite. It does not move state into a remote service and cannot replace
deterministic control-plane routing with browser-side or model-generated
authorization.
