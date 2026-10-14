# Model Council

**语言**：[中文](README.md) · [English](README.en.md)

一个本地优先的多模型协作编排器。它不要求模型之间建立网络连接，而是由一个管理者模型
通过统一消息、共享任务库和 Artifact 文件，把不同模型的成果传递给彼此。

设计上有一条主线：**认知与控制分离**。管理者模型负责提出计划和整合成果，
而身份、依赖、权限、预算、审批、超时和持久化全部由确定性 Python 代码执行。
**模型无法绕过编排器扩大自己的权限。**

```text
用户目标
   |
管理者模型 -- 生成 JSON 任务计划
   |
确定性编排器 -- 校验身份、依赖、并发和边界
   |
   +-- 架构模型 ----+
   +-- 实现模型 ----+--> Artifact 仓库 + SQLite 消息黑板
   +-- 研究模型 ----+
   |
审查模型
   |
管理者模型 -- 最终综合
```

## 它解决什么问题

不是"同时启动更多模型"，也不是"把多个聊天窗口放在一起"。

真实的痛点是：你手上有多个能力、速度、价格和工具条件都不同的 Agent＋模型，
于是你必须**自己**判断谁适合做什么、自己打开和检查每个工具、自己搬运上下文和文件、
自己核对跑的是不是配置的那个模型、自己发现登录或权限问题。做完之后，
你还不清楚成果**到底是谁做的**、花了多少钱。

Model Council 想把这条链路交给一个可信的本地控制平面，同时把
**模型选择、数据外发、任务开始、文件修改、费用和最终交付**的决定权留给你。

目标是让这个闭环可配置、可检查、可追踪、可暂停、可恢复、可审查：

```text
配置或接受推荐的一组 Agent＋Model（管理者／执行者／审查者／整合者）
  → 逐个启动、连接或附着，并分项检查真实状态
  → 有成员不可用就精确报告是哪个 Agent、哪个模型、哪一项失败
  → 全部就绪后，系统向你发出「可以开始」的请求
  → 你明确授权，冻结本次团队、任务、上下文、权限、预算和停止规则
  → 管理者拆解任务，执行者通过结构化消息与 Artifact 交换成果
  → 审查者独立复核，管理者整合并交付
  → 交付物保留 Provider → Model → Agent → Role → Task → Artifact 来源链
```

## 当前状态

**这是一个实验性系统，不是"任意 Agent＋任意模型开箱即用"的产品。**
请按下面的边界理解它的成熟度。

**已经扎实做出来并且可信的（有实测）**

- 控制平面：注册表、确定性路由、用量与预算账本、来源追溯；
- 授权链：每一次真实外部调用都需要**单次、精确、SHA-256 绑定、可失效**的审批。
  没有审批就发不出调用——这条有实测；
- 隔离工作区：显式读／写／测试／合并权限，合并在人工确认后才执行，且用 `--ff-only`；
- 隐私门禁：三个不同口径的扫描，含可达历史与被忽略的本地运行数据；
- 离线质量门禁：**306 项测试**，零第三方依赖，只需要 Python 3.11+。

**没有验证过的（这是缺陷，不是免责声明）**

- **整个协作闭环从未用两个真实模型跑过。** 系统名叫 Model Council，初心是"多个不同模型
  协作完成真实项目"，而真实调用累计只有少数几次单 Agent 合成任务；
- **Board 14 is complete** only for one local-private, read-only, synthetic Manager
  execution. 那次执行**不可重放**，也**不授权**任何重复、仓库上下文、工具、写入、
  Git 或并行。它的公共安全收尾报告在
  [`docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md`](docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md)；
- A2A 与 MCP 的真实第三方端点：协议客户端和审批都实现了，但**只对仓库内的假服务器验证过**；
- 本机**无法观测实际模型身份**（工具的事件流没有模型字段，配置的中转站端点对直接请求
  返回 Cloudflare 403）。系统把它记为 `unknown`，而不是用配置值顶替。

完整清单见 [「本项目还有哪些缺陷」](#本项目还有哪些缺陷)。

## 快速开始

只要求 **Python 3.11 或更新版本，零第三方依赖**。

```powershell
python -m model_council demo "设计一个支持多模型协作的本地项目管理工具"
```

输出写入 `runtime/`（`council.db` + `artifacts/`）。

不调用任何模型，先看清本机有什么：

```powershell
python -m model_council agents --config config.example.json
python -m model_council doctor --config config.codex.example.json
python -m model_council discovery scan --config config.codex.example.json
python -m model_council discovery show --config config.codex.example.json
```

跑一次真实项目前，需要走一次本地 Supervisor 流程来创建并批准运行授权：

```powershell
python -m model_council supervisor wizard `
  --team-file config.supervisor.team.example.json `
  --config config.example.json
python -m model_council supervisor check --config <LOCAL_CONFIG>
python -m model_council supervisor snapshot --config <LOCAL_CONFIG>
python -m model_council supervisor request-run <SNAPSHOT_ID> "<你的目标>" `
  --config <LOCAL_CONFIG>
python -m model_council supervisor approve <APPROVAL_ID> `
  --scope-sha256 <DISPLAYED_SCOPE_SHA256> --config <LOCAL_CONFIG>
python -m model_council run "<你的目标>" `
  --start-approval <APPROVAL_ID> --config <LOCAL_CONFIG>
```

看用量和预算，以及启动仅回环的本地界面：

```powershell
python -m model_council ledger summary --config config.example.json
python -m model_council web --config config.example.json
```

**完整的 21 个顶层命令、96 个子命令参考在 [`docs/CLI.md`](docs/CLI.md)。**
接入真实 Codex 或 OpenAI 兼容 API 的配置在 [`docs/ADAPTERS.md`](docs/ADAPTERS.md)。

## 核心概念

项目严格区分四种身份，混用会导致错误的判断：

| 概念 | 含义 |
| --- | --- |
| **Provider** | 提供模型服务、认证、端点、用量或账单能力的一方 |
| **Model** | 真正推理的模型，拥有能力、上下文、速度、价格等属性 |
| **Agent** | 承载模型并提供执行接口的工具，如 CLI、App Server、桌面应用 |
| **Role** | 本次项目中承担的职责，不是固定的厂商身份 |

最低限度需要四个角色：

- `manager` —— 理解目标、拆解任务、分派、追问、仲裁和整合；
- `worker` —— 执行架构、研究、编码、测试、文档或其他专业任务；
- `reviewer` —— 独立检查结论、代码、证据、风险和遗漏；
- `integrator` —— 形成最终交付，可以与 manager 相同，也可以单独配置。

同一个 Agent＋Model 可以承担多个 Role，但**系统必须记录每个 Role 在本次运行中的实际身份**。
你也可以要求关键角色必须由不同模型承担。

## 不可逾越的约束

这些是系统设计里不打算放松的部分：

- **用户是最终授权者**，管理者模型不是最高权限者；
- **没有审批就发不出外部调用**。真实外发需要单次、精确、可失效的授权，
  消费过的审批**不可重放**；
- **不向所有模型广播完整历史**，只传递完成当前任务所需的最小上下文；
- **不允许把「清单里有」当成「实际可用」**，也不允许把配置的模型身份
  当成它服务了请求的证据；
- **不允许静默替换**你锁定的 Agent 或 Model；
- **未知值保持 `unavailable`，不能当 0**，估算不能冒充账单；
- **真实编码 Agent 默认只读**，写权限需要独立的隔离工作区与单独审批；
- **失败要可见、可定位、可恢复**，不允许用伪成功掩盖不确定性。

## 本机观测现状

项目的目标是"验证每个成员的真实状态"，所以这里如实报告**能验证到什么程度**。

七个资质事实的实测结果（2026-10-14，codex 0.154.0）：

| 事实 | 能否观测 | 说明 |
| --- | --- | --- |
| `process` | ✅ | 进程起、退出码 |
| `version` | ✅ | 版本探测直接得到 |
| `protocol` | ✅ | JSONL 事件流握手 |
| `connectivity` | ✅ | 合成的 token 精确返回 |
| `login` | ➖ 不适用 | api key 模式没有交互登录态 |
| `actual_model` | ❌ **两侧都不可达** | 工具事件流无模型字段；中转站对直接请求返回 Cloudflare 403 |
| `permission` | ❌ | 工具没有回报它实际使用的沙箱；**请求值不是观测值** |

**结果是四个可观测、两个不可观测、一个不适用。**

而且观测记录分两种来源，只有一种能用来给真实 Agent 定资质：

| 来源 | 含义 | 能否用于就绪判定 |
| --- | --- | --- |
| `probe_run` | 由本系统实际运行的探测产出，事实从捕获的输出推导 | ✅ |
| `operator_authored` | 事实由调用方提供 | ❌ **默认拒绝** |

这条区分很重要：一个能在 JSON 里打出 `observed` 的操作者，并没有测量任何东西。
所以记录里必须有来源凭证（命令摘要、输出哈希、探测自己的起止时间），
而且**测量时间不能由调用方指定**。

**诚实边界**：这套机制**不能阻止**一个有权限的操作者事后伪造证据——本机操作者拥有
进程、磁盘和工具。它改变的是**信任边界**，不是伪造的可能性。

## 本项目还有哪些缺陷

分类的存在原因不同，混为一谈会误判项目进度。

### 能力缺口（尚未实现）

- **多轮争论与动态重新规划**：管理者只做一次规划、一次综合，失败后不重规划；
- **worker 之间的交互式问答**：只能通过已存结果和最终上下文传递；
- **自动价格目录刷新、货币换算与按时间窗口预算**：价格表由操作者声明；
- **通用上下文摘要**：需要先有经审查的留存与披露政策；
- **远程节点认证与签名**：A2A 的远端身份只做到端点校验；
- **Artifact 保留与清除策略**：目前只增不减；
- **Electron 打包与更广的操作台工作流**。

### 验证缺口（实现了，但只在假条件下验证过）

**这是最需要留意的一类：代码在，测试绿，但没碰过真实世界。**

- **整个协作闭环从未用两个真实模型跑过**；
- **A2A 与 MCP 的真实第三方端点**：只对假服务器跑通过；
- **Codex App Server**：真实运行次数少，样本薄。

### 观测缺口（本机结构上测不到）

- **`actual_model`** 与 **`permission`**，原因见上一节。系统把它们记为 `unknown`，
  而不是用配置值顶替；
- **当前还没有"不可观测事实的例外政策"**——就绪门禁要求全部七个事实，
  因此非 mock 角色目前无法在本机走到就绪。

### 接口缺口（能力在，但没有生产入口）

- `RepairService.run_local_until_terminal()` 与 `WorkspaceService.invoke_cli()`：
  只被测试使用，是**明确标注**的本地回调与假 CLI 演练，不是遗漏的接线。

### 已评估并决定不做

这一条不是缺陷，是决策记录，写在这里为了可追溯：

- **本地传输可靠性加固**：只观察到一次不可复现的 Windows 回环中断。除非先拿到可复现的
  失败测试，否则不启动——盲修一个复现不了的故障只会引入新风险。

### 一句话总结

真正没验证过的不是这些机制，而是**它们面对真实 Agent 时的行为**。
控制面和授权链是可信的（有实测），缺的是真实条件下的覆盖广度。

## 隐私扫描

扫描有三个不同口径，不要混用：

| 命令 | 作用范围 | 用途 |
| --- | --- | --- |
| `privacy_scan.py` | Git 已跟踪 + 未忽略的未跟踪文件 | 每次板块完成的公开门禁 |
| `privacy_scan.py --history` | 加上可达的全部历史 blob 与提交者域名 | 公开推送前的门禁 |
| `privacy_scan.py --local-state` | 加上被忽略的 `runtime/`、`runtime-*` | 搬迁、归档或迁移工作目录之前 |

第三个口径是被忽略的本地运行数据。它不进 Git，但**仍可从这台机器或它的任何副本读出**，
所以在本机隐私要求下也是一个需要检查的面。

扫描只打印 `路径:行号:类别`，**从不回显匹配到的值本身**。

## 项目地图

| 想看什么 | 去哪 |
| --- | --- |
| 完整命令参考（21 个顶层命令） | [`docs/CLI.md`](docs/CLI.md) |
| 接入真实 Codex／OpenAI 兼容 API | [`docs/ADAPTERS.md`](docs/ADAPTERS.md) |
| 项目要解决的最终问题、不可偏离原则 | [`docs/PROJECT_GOAL.md`](docs/PROJECT_GOAL.md) |
| 当前实现状态与每个板块的边界 | [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) |
| 每个开发板块的范围与验收报告 | [`docs/DEVELOPMENT_BOARDS.md`](docs/DEVELOPMENT_BOARDS.md)　＋　[`docs/reports/`](docs/reports/) |
| 架构与不变量 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 隐私分级政策与登记册 | [`docs/PRIVACY_ISSUES.md`](docs/PRIVACY_ISSUES.md) |
| 改代码前必读的工作约定 | [`AGENTS.md`](AGENTS.md) |
| 跨会话接手说明 | [`docs/START_HERE_NEXT_SESSION.md`](docs/START_HERE_NEXT_SESSION.md) |

## 开发门禁

改代码前后都应运行：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q model_council tests scripts
python scripts/privacy_scan.py --history
python scripts/privacy_scan.py --local-state
python scripts/release_verify.py
```

项目按**开发板块**推进。每个板块完成时必须同时交付：实现、自动化测试、
`docs/reports/` 下的验收报告、路线图与交接文档更新、**恰好一个**可识别的 Git 提交、
以及一次完整隐私扫描。

## 许可

[MIT](LICENSE)
