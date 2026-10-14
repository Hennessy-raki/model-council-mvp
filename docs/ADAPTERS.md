# Adapter 接入指南

本文说明如何把一个真实 Agent 或 API 接到 Model Council 上。根 `README.md` 只保留要点，
配置细节在这里。

通用原则，任何 Adapter 都适用：

- **第一轮只让一个角色使用真实模型**，其余角色继续用 mock。确认运行、权限和输出都稳定后，
  再逐个替换；
- **不要把密钥写进 JSON**。配置只用环境变量名，值从环境变量读；
- **真实调用默认关闭**。`invoke_enabled` 默认 `false`，启用它是与「注册表里有这条记录」
  完全分离的一步；
- **真实编码 Agent 默认只读**。需要它修改项目时，给它独立的 Git worktree，
  并在人工确认后才启用工作区写权限。

---

## 接入 Codex（CLI Adapter）

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

`codex_jsonl` 模式**不会把推理事件当作最终答案**，只读取最后一个完成的 `agent_message`。
线程 ID、事件类型统计和 usage 会作为任务消息元数据保存。

Windows 的一个已知边界：如果在 Codex Desktop 自身的受限任务环境里调用打包的 `codex.exe`，
可能得到"拒绝访问"。解决办法是在**普通用户 PowerShell** 中运行本项目，或改用 App Server／API
Adapter。**这是宿主进程的权限边界，不代表 CLI Adapter 的参数协议失败。**

### 观测：这个 CLI 不报告模型身份

实测（2026-10-14，codex 0.154.0）：`codex exec --json` 的事件流里**没有任何模型字段**。
一次真实回合只报告四类事件：

```json
{"type": "thread.started", "thread_id": "..."}
{"type": "turn.started"}
{"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": "..."}}
{"type": "turn.completed", "usage": {"input_tokens": 16078, "cached_input_tokens": 15232, "output_tokens": 12}}
```

所以「配置的模型」与「实际服务的模型」**在这一侧无法对齐**。系统把这个事实记为
`unknown`，而不是用配置值顶替。详见根 README 的「本机观测现状」。

## 接入 OpenAI-compatible API

不要写密钥进 JSON。配置环境变量：

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

`api_style` 可选：`responses` 或 `chat_completions`。

**并非所有声称兼容 OpenAI API 的服务都完整支持这两种接口**，需要按提供商实际行为验证。

### `/models` 端点不可用的 Provider

有些服务对 `/models` 直接返回拒绝（实测遇到过 403 + Cloudflare 1010），
但完成请求完全正常。这种情况把 `models_endpoint_available` 设为 `false`，
连通性检查就会改用补全端点，而不是报一个**假的失败**：

```json
{
  "base_url": "https://provider.example/v1",
  "model": "model-name",
  "api_key_env": "PROVIDER_API_KEY",
  "api_style": "responses",
  "models_endpoint_available": false
}
```

这个模式下的探针**会发一次有界的真实补全请求**，所以它是显式声明而非默认行为。
好处是它顺带回答"实际服务的是哪个模型"——响应里的 `model` 字段会被记为
`observed_model`，与 `configured_model` **分开保存**。

## 模型身份：两个字段，不要混用

`OpenAICompatibleAdapter` 把两件事分开记：

| 字段 | 含义 |
| --- | --- |
| `configured_model` | 你在配置里要求的模型 |
| `observed_model` | 服务端回报的、实际服务了这个请求的模型 |
| `observed_model_source` | 前者来源：`provider_response` / `provider_usage` / `unavailable` |
| `model_identity_mismatch` | 两者不一致时为 `true` |

**服务端没回报时 `observed_model` 记为 `unavailable`，绝不用配置值顶替。**
因为"配置的模型"不是"它服务了请求"的证据。

## 接入 Codex App Server

`codex_app_server` 类型走持久会话：`initialize` → `thread/start`（或 `thread/resume`）
→ `turn/start` → 读取内容与 usage。

它的默认行为是**拒绝**：没有通过出站上下文审批（清单必须与 prompt 完全一致）时，
它会抛出 `OutboundContextApprovalRequired`，**根本不会发起调用**。这是设计意图，不是 bug。

审批流程见 [`CLI.md`](CLI.md) 第 7 节。约束：

- `sandbox` 只能是 `read-only` 或 `workspace-write`（默认 `read-only`）；
- `approval_policy` 只能是 `never` 或 `on-request`（默认 `never`）；
- 支持 `cwd_env` 以避免把机器路径写进配置。

## 接入 A2A 与 MCP

- **A2A**：协议客户端与审批链已实现，但**没有验证过任何真实第三方端点**，
  只对仓库内的假服务器跑通过；
- **MCP**：工具代理同样，执行**刻意分两步**（请求 → 批准 → 调用）。

两者都属于「已实现但只对本地假服务器验证过」，详见根 README 的缺陷清单。

## 与 Claude / Gemini / OpenCode 等的关系

这些名字只是**内置发现目录里的默认条目**，不是硬编码的接入口。发现目录本身是
**配置数据**：

```json
"discovery_targets": [
  {"key": "any-tool", "display_name": "Any Tool",
   "command_candidates": ["any-tool.cmd", "any-tool"],
   "version_arguments": ["--version"],
   "extra_path_patterns": []}
]
```

项目**不得把任何特定厂商、模型、CLI 或桌面工具写死为唯一实现**——这是总体目标里的
一条不可偏离原则。加一个工具不需要改代码。
