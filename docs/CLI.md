# CLI 与配置参考

本文是 Model Council 的完整命令面。根 `README.md` 只保留最小上手路径，细节在这里。

约定：

- 需要真实外部调用的命令一律需要**单次、精确、可失效**的授权，命令里会体现为
  `--start-approval`、`--scope-sha256`、`--approve-sha256` 之类参数；
- `<LOCAL_CONFIG>` 指你本地未跟踪的配置，`<...>` 是占位符；
- 示例里的 `config.example.json` 是仓库内的离线基线，**全部角色都是 mock**，
  不会产生任何外部调用。

---

## 1. 最小上手

项目只要求 Python 3.11 或更新版本，无第三方依赖。

```powershell
cd <REPO>
python -m model_council demo "设计一个支持多模型协作的本地项目管理工具"
```

输出写入：

```text
runtime/
├─ council.db
└─ artifacts/
```

```powershell
python -m model_council agents --config config.example.json
```

## 2. 运行与查看

`run` 是面向用户的项目入口，**要求一次性的 Supervisor 项目运行审批**，绑定当前的
就绪团队与确切目标。审批在任何 Adapter 被调用之前就被消费。

```powershell
python -m model_council run "分析并设计一个个人知识库应用" `
  --start-approval <PROJECT_RUN_APPROVAL_ID> --config <LOCAL_CONFIG>
```

审批的创建与批准走本地 Supervisor 流程，见第 8 节。

```powershell
python -m model_council runs --config config.example.json
python -m model_council status <RUN_ID> --config config.example.json
```

`status` 会同时显示运行、任务、结构化消息和 Artifact 元数据。

## 3. Adapter 与启动发现

发现不会调用模型。`doctor` 只做检查，不启动进程也不发请求。

```powershell
python -m model_council doctor --config config.codex.example.json
python -m model_council discovery scan --config config.codex.example.json
python -m model_council discovery show --config config.codex.example.json
```

显式发现某个 Adapter 可见的模型：

```powershell
python -m model_council discovery models manager --config config.example.json
```

连通性测试必须由用户显式选择。CLI Adapter 会在空临时目录中使用固定探针，
**不传递项目目标、上下文、Agent 描述或 Artifact**：

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

发现记录把 executable、authentication、permission、connectivity 与 models
**分别保存**：

> 可执行文件存在**不等于**认证成功；配置了凭据**不等于**远端验证通过。

发现目录是**配置数据**，不是代码。加一个工具不需要改模块：

```json
"discovery_targets": [
  {"key": "myagent", "display_name": "My Agent",
   "command_candidates": ["myagent.cmd", "myagent"],
   "version_arguments": ["--version"],
   "extra_path_patterns": ["<ABS_DIR>/*.exe"]}
],
"gui_only_targets": [
  {"key": "some-desktop-app", "display_name": "Some Desktop App",
   "command_candidates": [], "version_arguments": [],
   "interface_kind": "gui_only"}
]
```

`interface_kind` 只有两个取值：`cli`（控制面可以自己调用）与 `gui_only`
（不可以，只登记可见性与手工移交）。声明成 `cli` 却没有任何命令会在**配置加载时直接报错**。

同一 Agent 存在多个安装时，会各自探测版本并按规则推荐：

| 层级 | 规则 |
| --- | --- |
| 比较两个版本 | 正式版只胜过**同号**的候选版：`1.35.0` > `1.35.0-rc.1` |
| 排序候选集 | 只要存在正式版，就不推荐任何候选版：`1.34.9` 胜过 `1.35.0-rc.1` |

排序规则可关闭（退化为纯数字比较）。**推荐永远不是替换**：任何结果都带
`auto_switch: false`，显式指定的 `preferred_version` 一定优先于推荐，
记为 `user_preference` 并把被压过的版本列进 `alternatives`。
无法比较的版本（例如 `latest` 与 `1.35.0` 混在一起）返回 `undecidable`，
**不给推荐、不猜**。

## 4. 用量、费用与预算

```powershell
python -m model_council ledger summary --config config.example.json
python -m model_council ledger events --run <RUN_ID> --config config.example.json
python -m model_council ledger alerts --run <RUN_ID> --config config.example.json
```

```powershell
python -m model_council ledger set-budget project-cost `
  --scope project --metric cost --warning 5 --hard 10 --currency USD `
  --config config.example.json
```

Provider 余额**只能显式查询**，而且只有 Adapter 声明支持余额 API 时才会访问：

```powershell
python -m model_council ledger balance <PROVIDER_ID> --config config.example.json
```

账本分别标记 `actual`、`provider_reported`、`estimated` 与 `unavailable`。
**未知值不会被当成零**；存在 hard budget 而历史消费不可度量时，下一次调用会被保守阻断。

### 输入 token 底噪：工具型 Agent 约 1.6 万

**实测结论，不是估算。** 2026-10-14 的一次真实观察：发给 `codex exec` 的 prompt
只有 **78 字节**，而服务端计费的输入 token 是 **16,078**（其中 15,232 命中缓存），
输出 12 token。差异几乎全部来自**宿主工具自己注入的系统提示和工具定义**，
与任务大小无关。

由此三条硬约束：

1. **`max_input_tokens` 必须 ≥ 20000**，否则必然 fail closed；
2. **不要用「prompt 字节数 × 系数」估算输入 token**，会低估两个数量级；
3. **缓存命中不能当预算依据**，命中与否不由我们控制，**预算按未缓存量算**。

适配器会把服务端回报的 `prompt_tokens` 记进调用元数据，所以每次调用后都能核对当次底噪。

## 5. 设置注册中心与路由

```powershell
python -m model_council settings sync --config config.example.json
python -m model_council settings show --config config.example.json
```

```powershell
python -m model_council settings assign detail_executor `
  --mode hybrid --agent implementer --model mock-general `
  --constraints '{"required_capabilities":["implementation"]}' `
  --config config.example.json
```

设置注册中心是本地设置界面的数据基础。JSON 配置只负责提供初始值，
**用户通过 CLI 或界面保存的值不会被后续同步覆盖**。

路由在**任何 Adapter 调用之前**解析已持久化的角色。查看选中的身份、证据与被拒候选：

```powershell
python -m model_council routing decisions --run <RUN_ID> `
  --config config.example.json
```

## 6. 本地设置界面

仅绑定回环地址，读写与 CLI 相同的 SQLite 注册表，
**从不调用模型、发现探针、Provider 余额 API 或外部服务**：

```powershell
python -m model_council web --config config.example.json
```

板块 12 把它扩展为本地产品界面：统一审批中心、工作区／修复／评测证据视图、
脱离引用文本的运行比较、以及页面刷新**只读**（不执行模型、网络、Git、测试、
合并、丢弃或恢复动作）。

## 7. 持久会话与远程互通

从 `config.interop.example.json` 开始。**每个真实端点都需要 `invoke_enabled: true`**，
这与启用注册表记录是两件事。

```powershell
python -m model_council interop show --config config.interop.example.json
python -m model_council interop sessions --config config.interop.example.json
python -m model_council interop approvals --config config.interop.example.json
```

MCP 工具执行**刻意分两步**：

```powershell
python -m model_council interop request-tool local-tools echo `
  --arguments '{"text":"local request"}' `
  --config config.interop.example.json
python -m model_council interop approve <APPROVAL_ID> `
  --config config.interop.example.json
python -m model_council interop call-tool <APPROVAL_ID> `
  --config config.interop.example.json
```

### 出站上下文审批（Codex App Server）

第一次调用会生成一个本地的待审批清单，并在 App Server 启动**之前**停住。
在本地检查确切 prompt，对**那个确切范围**取得显式授权，然后才继续：

```powershell
python -m model_council interop contexts --config <LOCAL_CONFIG>
python -m model_council interop context <MANIFEST_ID> --show-prompt `
  --config <LOCAL_CONFIG>
python -m model_council interop context <MANIFEST_ID> `
  --approve-sha256 <DISPLAYED_APPROVAL_SHA256> --config <LOCAL_CONFIG>
python -m model_council run "<SAME_SYNTHETIC_GOAL>" `
  --outbound-manifest <MANIFEST_ID> --config <LOCAL_CONFIG>
```

## 8. Supervisor：团队就绪与启动审批

向导导入一个只含**合成就绪检查**的本地 JSON；它不调用 Adapter，也不联系任何端点。

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

团队快照把绑定、就绪证据、生命周期证据、资质预检与观测记录**都绑进摘要**。
配置或就绪状态漂移会让审批失效。

### 资质预检（纯离线）

在考虑任何真实 Agent 资质之前，用这个纯离线校验器验证一份本地声明。
它**不加载项目配置、不起进程、不发请求、不授予执行权限**：

```powershell
python -m model_council supervisor qualification-preflight `
  --candidate-file <LOCAL_QUALIFICATION_JSON>
```

对一个已配置的非 mock 角色，在创建团队快照之前先把合格的预检绑到角色上：

```powershell
python -m model_council supervisor qualification-bind manager `
  --candidate-file <LOCAL_QUALIFICATION_JSON> --config <LOCAL_CONFIG>
```

绑定只在本地被忽略的运行时状态里存**经脱敏的范围元数据及其摘要**。
角色或范围漂移会让下游审批失效。

### 单次启动审批

```powershell
python -m model_council supervisor request-start <SNAPSHOT_ID> `
  --config <LOCAL_CONFIG>
python -m model_council supervisor approve <APPROVAL_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council supervisor start <APPROVAL_ID> --config <LOCAL_CONFIG>
```

### 真实 Agent 资质授权包

这是「到真实调用之间」的最后一个离线环节：把一次未来真实 Agent 资质的请求做成
**可审查、可摘要、可失效**的对象。它不启动任何东西。

```powershell
python -m model_council authorization build --candidate-file <声明.json>
python -m model_council authorization verify --package-file <包.json>
python -m model_council supervisor authorization-bind manager --package-file <包.json>
python -m model_council supervisor authorization-show [--role manager]
```

三个必须知道的行为：

- **工作目录只以「类别 + 环境变量名」出现**，例如
  `{"category": "synthetic_workspace", "env_var": "MODEL_COUNCIL_SYNTHETIC_CWD"}`，
  所以跟踪文件里永远不会出现本机绝对路径；
- **缺证据时状态是 `user_confirmation_required`**，这是构造性的：七个生命周期事实
  默认 `unknown`，没有观测值就不会变成可审查。默认产出的是**一个问你的问题**，不是放行；
- **事实状态绑进了包摘要**，任何观测值变化都会改变 `package_sha256`。重新读取时重新推导，
  所以被篡改的包报 `invalid`、事实漂移的报 `stale`、团队快照过期的报 `superseded`。

绑定**不创建启动审批、不启动进程、不授予任何权限**。

### 观测记录：只有探测产出才能给真实 Agent 定资质

| 来源 | 含义 | 能否用于就绪判定 |
| --- | --- | --- |
| `probe_run` | 由本系统实际运行的探测产出，事实从捕获的输出推导 | ✅ |
| `operator_authored` | 事实由调用方提供 | ❌ **默认拒绝** |

产生可用记录只有一条路——跑一次探测：

```powershell
python -m model_council supervisor observation-probe `
  --agent-id codex-architect --model-id codex-configured-default `
  --provider-id codex-local --executable <TOOL_PATH>
```

探测是**参数数组、`shell=False`、有超时（30 秒）**，只问工具自己的版本，
**不发送任何项目上下文**。开始与结束时间由探测自己记录，**测量时间不能由调用方指定**。
记录带来源凭证：命令摘要、输出哈希、起止时间。

```powershell
python -m model_council supervisor observation-bind manager `
  --observation-file <观测.json> --config <LOCAL_CONFIG>
python -m model_council supervisor observation-show [--role manager] \
  --config <LOCAL_CONFIG>
```

### 受控本地实验

先创建一个当前已确认的 Supervisor 团队快照，然后把占位快照 ID 替换进一份未跟踪的实验规格：

```powershell
python -m model_council experiment prepare `
  --spec-file <LOCAL_EXPERIMENT_JSON> --config <LOCAL_CONFIG>
python -m model_council experiment show <EXPERIMENT_ID> `
  --show-prompt --config <LOCAL_CONFIG>
```

模拟（纯本地，不出网）：

```powershell
python -m model_council experiment approve <EXPERIMENT_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council experiment arm <EXPERIMENT_ID> `
  --config <LOCAL_CONFIG>
python -m model_council experiment simulate <EXPERIMENT_ID> `
  --config <LOCAL_CONFIG>
```

对 `real_codex`，`arm` **只重新校验确切范围**。受控执行器只有在单独批准、
SHA-256 绑定的启动审批之后才可能启动一个回合；它在创建进程前重新校验团队、身份、
范围与来源完整性。假模拟器仍然拒绝该模式。**每个真实回合都是单次使用的，各自需要显式授权。**

参考：`config.board14.example.json`、`config.board14.team.example.json`、
`config.experiment.board14-fake.example.json`、`config.experiment.board14-codex.example.json`。

## 9. 隔离 Git 工作区

写、测试与合并权限**分别启用**并持久化在 SQLite。一个典型的本地流程：

```powershell
python -m model_council workspace prepare <ABS_REPO_PATH> writer `
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

待审批的合并会显示一个 `scope_sha256`，绑定干净的**目标 SHA、Agent 分支 SHA、
有界 diff 证据、以及在该精确 HEAD 上捕获的通过测试**。确认必须完全匹配：

```powershell
python -m model_council workspace approve <APPROVAL_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council workspace merge <APPROVAL_ID> `
  --config <LOCAL_CONFIG>
```

合并执行**重新校验范围、一次性消费审批**，并使用 `git merge --ff-only`。

## 10. 有界修复与恢复

每次迭代都从干净的 HEAD 开始：捕获检查点、运行配置的测试、收集 diff 证据，
并记录 `accept` 或 `repair`：

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

审查者不能接受失败的测试。

## 11. 第二模型家族客观评估

```powershell
python -m model_council evaluation prepare deepseek_evaluator `
  --config config.evaluation.example.json
python -m model_council evaluation context <EVALUATION_ID> --show-prompt `
  --config config.evaluation.example.json
```

运行需要一份本地未跟踪配置（含 `invoke_enabled: true`）、凭据环境变量，
以及对该确切清单的一次性显式批准：

```powershell
python -m model_council evaluation context <EVALUATION_ID> `
  --approve-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council evaluation run <EVALUATION_ID> `
  --outbound-manifest <MANIFEST_ID> --config <LOCAL_CONFIG>
```

评估表只保留哈希、字节数、断言与账本引用，**不复制响应文本**。
非回环端点要求 HTTPS，且**拒绝 HTTP 重定向**。

## 12. 备份与恢复

隐私安全的**默认只含数据库**备份：

```powershell
python -m model_council backup create --config config.example.json
```

显式包含已登记的 Artifact：

```powershell
python -m model_council backup create --include-artifacts `
  --config config.example.json
```

恢复**刻意分三步**：

```powershell
python -m model_council backup request-restore <BACKUP_ID> `
  --config config.example.json
python -m model_council backup approve <APPROVAL_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config config.example.json
python -m model_council backup restore <APPROVAL_ID> `
  --config config.example.json
```

凭据、环境文件、仓库与工作区**被排除**。恢复会先创建安全备份、重新校验确切状态，
并且**只添加缺失的、哈希校验通过的 Artifact**。

## 13. 运行比较

```powershell
python -m model_council compare runs <LEFT_RUN_ID> <RIGHT_RUN_ID> `
  --config config.example.json
```

## 14. 开发门禁

改代码前后都应运行：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q model_council tests scripts
python scripts/privacy_scan.py --history
python scripts/privacy_scan.py --local-state
python scripts/release_verify.py
```

发布候选校验器要求一种干净、同步的 `main` 状态；在本地故意未发布的孵化分支领先
`origin/main` 时，它预期失败（`local_refs_agree`）。
