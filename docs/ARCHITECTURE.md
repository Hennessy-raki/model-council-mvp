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

## 下一阶段边界

优先级顺序：

1. Board 6 本地设置与控制界面；
2. 经单独授权后的 Codex `exec` 单模型只读试点；
3. Board 7 Codex App Server、A2A、MCP 和远程互操作；
4. Git worktree 隔离与人工审批。

Board 6 must consume the stable registry, discovery, provenance, ledger and
routing contracts. It must not replace deterministic control-plane decisions
with browser-side or model-generated authorization.
