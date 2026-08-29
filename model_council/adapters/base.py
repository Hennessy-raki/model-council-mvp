from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..types import (
    AgentCard,
    AgentRequest,
    AgentResponse,
    AuthenticationStatus,
    ConnectivityStatus,
    ExecutableStatus,
    PermissionStatus,
)


class AgentAdapter(ABC):
    def __init__(self, card: AgentCard):
        self.card = card

    @abstractmethod
    def invoke(self, request: AgentRequest) -> AgentResponse:
        raise NotImplementedError

    def diagnose(self) -> dict[str, Any]:
        return {
            "ok": True,
            "adapter": type(self).__name__,
            "agent": self.card.name,
        }

    def discovery_capabilities(self) -> dict[str, bool]:
        return {
            "executable_check": False,
            "authentication_check": False,
            "permission_check": False,
            "model_discovery": False,
            "connectivity_test": False,
        }

    def check_executable(self) -> dict[str, Any]:
        return {"status": ExecutableStatus.NOT_APPLICABLE.value}

    def check_authentication(self) -> dict[str, Any]:
        return {"status": AuthenticationStatus.UNKNOWN.value}

    def check_permissions(self) -> dict[str, Any]:
        return {"status": PermissionStatus.UNKNOWN.value}

    def discover_models(self) -> list[dict[str, Any]]:
        raise RuntimeError(
            f"adapter {type(self).__name__} does not support model discovery"
        )

    def connectivity_probe(self) -> dict[str, Any]:
        return {
            "status": ConnectivityStatus.NOT_SUPPORTED.value,
            "details": {},
        }

    def billing_capabilities(self) -> dict[str, bool]:
        return {"provider_balance": False}

    def provider_balance(self) -> dict[str, Any]:
        raise RuntimeError(
            f"adapter {type(self).__name__} does not support provider balance"
        )

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
