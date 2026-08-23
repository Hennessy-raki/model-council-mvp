from __future__ import annotations

from pathlib import Path

from .base import AgentAdapter
from .cli import CliAdapter
from .mock import MockAdapter
from .openai_compatible import OpenAICompatibleAdapter
from ..config import CouncilConfig


def build_adapters(config: CouncilConfig) -> dict[str, AgentAdapter]:
    adapters: dict[str, AgentAdapter] = {}
    config_dir = Path(config.path).parent
    for name, settings in config.agents.items():
        card = config.card(name)
        adapter_type = settings.get("type", "mock")
        if adapter_type == "mock":
            adapter = MockAdapter(card)
        elif adapter_type == "cli":
            adapter = CliAdapter(card, settings, config_dir)
        elif adapter_type == "openai_compatible":
            adapter = OpenAICompatibleAdapter(card, settings)
        else:
            raise ValueError(f"unsupported adapter type {adapter_type!r}")
        adapters[name] = adapter
    return adapters
