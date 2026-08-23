from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import AgentCard, AgentRequest, AgentResponse


class AgentAdapter(ABC):
    def __init__(self, card: AgentCard):
        self.card = card

    @abstractmethod
    def invoke(self, request: AgentRequest) -> AgentResponse:
        raise NotImplementedError

    def system_prompt(self) -> str:
        capabilities = ", ".join(self.card.capabilities) or "未声明"
        boundaries = "\n".join(f"- {x}" for x in self.card.boundaries) or "- 无额外边界"
        return (
            f"你的身份是：{self.card.role}。\n"
            f"职责：{self.card.description}\n"
            f"能力：{capabilities}\n"
            f"必须遵守的边界：\n{boundaries}\n"
            "只处理当前指派的工作；明确区分事实、推断和未知信息。"
        )

    def render_prompt(self, request: AgentRequest) -> str:
        artifact_lines = "\n".join(
            f"- {item.name}: {item.path} (sha256={item.sha256})"
            for item in request.artifacts
        ) or "- 无"
        return (
            f"{self.system_prompt()}\n\n"
            f"运行ID：{request.run_id}\n"
            f"任务ID：{request.task_id}\n"
            f"模式：{request.mode}\n"
            f"总目标：{request.goal}\n\n"
            f"当前指令：\n{request.instruction}\n\n"
            f"上游上下文：\n{request.context or '无'}\n\n"
            f"可用Artifact：\n{artifact_lines}\n"
        )
