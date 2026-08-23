from __future__ import annotations

import json

from .base import AgentAdapter
from ..types import AgentRequest, AgentResponse


class MockAdapter(AgentAdapter):
    def invoke(self, request: AgentRequest) -> AgentResponse:
        if request.mode == "plan":
            workers = request.metadata.get("workers", [])
            tasks = []
            previous_key: str | None = None
            for index, worker in enumerate(workers, start=1):
                key = f"work_{index}"
                role = worker.get("role", worker["name"])
                depends_on = []
                if index > 1 and request.metadata.get("sequential", False):
                    depends_on = [previous_key]
                tasks.append(
                    {
                        "key": key,
                        "title": f"{role}专项分析",
                        "instruction": (
                            f"围绕总目标，从{role}视角形成可执行建议。"
                            "列出关键决策、风险、待确认问题，并给下一位模型留下清晰交接。"
                        ),
                        "agent": worker["name"],
                        "depends_on": depends_on,
                    }
                )
                previous_key = key
            return AgentResponse(json.dumps({"tasks": tasks}, ensure_ascii=False))

        if request.mode == "review":
            return AgentResponse(
                "# 独立审查\n\n"
                f"目标：{request.goal}\n\n"
                "## 检查结果\n\n"
                "- 已收到各专业模型的独立成果。\n"
                "- 建议在真实模型接入后增加事实核验和可执行测试。\n"
                "- 对互相冲突的决策，应由管理员记录取舍依据，而非简单多数投票。\n"
                "- 涉及文件写入、部署或凭据的步骤必须经过确定性权限检查。\n\n"
                "## 当前结论\n\n"
                "该方案可以进入小规模真实模型试点。"
            )

        if request.mode == "synthesize":
            return AgentResponse(
                "# Model Council 综合结果\n\n"
                f"## 总目标\n\n{request.goal}\n\n"
                "## 管理员结论\n\n"
                "各专业角色已完成分工并由独立角色复核。当前成果证明了任务分派、"
                "并行执行、Artifact传递、审查和最终综合这条最小闭环可以运行。\n\n"
                "## 汇总依据\n\n"
                f"{request.context}\n\n"
                "## 下一步\n\n"
                "选择一个真实模型替换对应的 mock adapter，保持其余角色不变，"
                "确认一次完整运行后再接入第二个真实模型。"
            )

        return AgentResponse(
            f"# {self.card.role}工作结果\n\n"
            f"## 对目标的理解\n\n{request.goal}\n\n"
            f"## 当前任务\n\n{request.instruction}\n\n"
            "## 建议\n\n"
            f"- 从“{self.card.role}”职责出发，先定义输入、输出和验收条件。\n"
            "- 使用结构化消息传递结论，文件内容通过 Artifact 引用交接。\n"
            "- 对未知信息显式标记，交给管理员决定是否追问或更换模型。\n"
            "- 任何高风险操作都由确定性编排器检查，不由语言模型自行授权。\n\n"
            "## 风险\n\n"
            "- 模型输出可能自洽但不正确，需要测试或独立审查。\n"
            "- 不同模型的上下文长度和工具能力不同，需要适配器裁剪上下文。\n"
        )
