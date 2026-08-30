from __future__ import annotations

from pathlib import Path

from .base import AgentAdapter
from .a2a import A2AAdapter
from .cli import CliAdapter
from .codex_app_server import CodexAppServerAdapter
from .mock import MockAdapter
from .openai_compatible import OpenAICompatibleAdapter
from ..config import CouncilConfig
from ..interoperability import InteroperabilityService
from ..outbound_context import OutboundContextService
from ..store import CouncilStore


def build_adapters(
    config: CouncilConfig,
    store: CouncilStore | None = None,
) -> dict[str, AgentAdapter]:
    adapters: dict[str, AgentAdapter] = {}
    config_dir = Path(config.path).parent
    needs_interoperability = bool(config.mcp_servers) or any(
        item.get("type") in {"codex_app_server", "a2a"}
        for item in config.agents.values()
    )
    interoperability = (
        InteroperabilityService(
            config,
            store or CouncilStore(config.state_dir / "council.db"),
        )
        if needs_interoperability
        else None
    )
    for name, settings in config.agents.items():
        card = config.card(name)
        adapter_type = settings.get("type", "mock")
        if adapter_type == "mock":
            adapter = MockAdapter(card, settings)
        elif adapter_type == "cli":
            adapter = CliAdapter(card, settings, config_dir)
        elif adapter_type == "openai_compatible":
            adapter = OpenAICompatibleAdapter(
                card,
                settings,
                outbound_context=OutboundContextService(
                    store or CouncilStore(config.state_dir / "council.db")
                ),
            )
        elif adapter_type == "codex_app_server":
            assert interoperability is not None
            adapter = CodexAppServerAdapter(
                card,
                settings,
                config_dir,
                interoperability,
            )
        elif adapter_type == "a2a":
            assert interoperability is not None
            adapter = A2AAdapter(
                card,
                settings,
                interoperability,
            )
        else:
            raise ValueError(f"unsupported adapter type {adapter_type!r}")
        adapters[name] = adapter
    return adapters
