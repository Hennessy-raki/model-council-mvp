from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .types import AgentCard


@dataclass(frozen=True)
class CouncilConfig:
    path: Path
    project_name: str
    state_dir: Path
    max_parallel: int
    manager: str
    reviewer: str | None
    agents: dict[str, dict[str, Any]]

    def card(self, name: str) -> AgentCard:
        item = self.agents[name]
        return AgentCard(
            name=name,
            role=str(item.get("role", name)),
            description=str(item.get("description", "")),
            capabilities=tuple(str(x) for x in item.get("capabilities", [])),
            boundaries=tuple(str(x) for x in item.get("boundaries", [])),
        )


def load_config(path: str | Path) -> CouncilConfig:
    config_path = Path(path).resolve()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    agents = data.get("agents")
    if not isinstance(agents, dict) or not agents:
        raise ValueError("config.agents must be a non-empty object")

    manager = str(data.get("manager", "manager"))
    reviewer_raw = data.get("reviewer")
    reviewer = str(reviewer_raw) if reviewer_raw else None
    if manager not in agents:
        raise ValueError(f"manager agent {manager!r} is not configured")
    if reviewer and reviewer not in agents:
        raise ValueError(f"reviewer agent {reviewer!r} is not configured")

    state_value = Path(str(data.get("state_dir", "runtime")))
    state_dir = state_value if state_value.is_absolute() else config_path.parent / state_value
    max_parallel = int(data.get("max_parallel", 3))
    if max_parallel < 1:
        raise ValueError("max_parallel must be at least 1")

    for name, item in agents.items():
        if not isinstance(item, dict):
            raise ValueError(f"agent {name!r} must be an object")
        if item.get("type", "mock") not in {"mock", "cli", "openai_compatible"}:
            raise ValueError(f"agent {name!r} has unsupported type {item.get('type')!r}")

    return CouncilConfig(
        path=config_path,
        project_name=str(data.get("project_name", "model-council")),
        state_dir=state_dir.resolve(),
        max_parallel=max_parallel,
        manager=manager,
        reviewer=reviewer,
        agents=agents,
    )
