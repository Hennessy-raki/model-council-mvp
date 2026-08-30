from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import build_adapters
from .adapters.base import AgentAdapter
from .config import CouncilConfig
from .registry import RegistryService
from .types import (
    AuthenticationStatus,
    ConnectivityStatus,
    ExecutableStatus,
    PermissionStatus,
)


@dataclass(frozen=True)
class LocalAgentTarget:
    key: str
    display_name: str
    command_candidates: tuple[str, ...]


KNOWN_LOCAL_AGENTS = (
    LocalAgentTarget("codex", "Codex CLI", ("codex.cmd", "codex")),
    LocalAgentTarget("claude", "Claude Code CLI", ("claude.cmd", "claude")),
    LocalAgentTarget("gemini", "Gemini CLI", ("gemini.cmd", "gemini")),
    LocalAgentTarget("opencode", "OpenCode CLI", ("opencode.cmd", "opencode")),
)


class DiscoveryService:
    """Local Agent discovery without automatic routing or project disclosure."""

    def __init__(
        self,
        config: CouncilConfig,
        registry: RegistryService,
        adapters: dict[str, AgentAdapter] | None = None,
        known_targets: tuple[LocalAgentTarget, ...] = KNOWN_LOCAL_AGENTS,
    ):
        self.config = config
        self.registry = registry
        self.adapters = adapters or build_adapters(config, registry.store)
        self.known_targets = known_targets

    def scan(self) -> list[dict[str, Any]]:
        existing = {
            item["id"]: item for item in self.registry.discovery_records()
        }
        for agent_id, settings in self.config.agents.items():
            self._scan_configured_agent(
                agent_id,
                settings,
                existing.get(self._configured_record_id(agent_id)),
            )
        for target in self.known_targets:
            self._scan_known_target(
                target,
                existing.get(self._known_record_id(target.key)),
            )
        return self.registry.discovery_records()

    def discover_models(self, agent_id: str) -> list[dict[str, Any]]:
        adapter = self._configured_adapter(agent_id)
        capabilities = adapter.discovery_capabilities()
        if not capabilities.get("model_discovery", False):
            raise ValueError(
                f"agent {agent_id!r} does not support model discovery"
            )
        record_id = self._configured_record_id(agent_id)
        if self.registry.discovery_record(record_id) is None:
            self._scan_configured_agent(
                agent_id,
                self.config.agents[agent_id],
                None,
            )
        models = adapter.discover_models()
        self.registry.update_discovered_models(record_id, models)
        return models

    def probe(self, agent_id: str) -> dict[str, Any]:
        adapter = self._configured_adapter(agent_id)
        capabilities = adapter.discovery_capabilities()
        if not capabilities.get("connectivity_test", False):
            raise ValueError(
                f"agent {agent_id!r} does not support connectivity testing"
            )
        record_id = self._configured_record_id(agent_id)
        if self.registry.discovery_record(record_id) is None:
            self._scan_configured_agent(
                agent_id,
                self.config.agents[agent_id],
                None,
            )
        result = adapter.connectivity_probe()
        status = ConnectivityStatus(
            result.get("status", ConnectivityStatus.FAILED)
        )
        details = result.get("details")
        self.registry.update_connectivity(
            record_id,
            status,
            details if isinstance(details, dict) else {},
        )
        return {
            "agent_id": agent_id,
            "status": status.value,
            "details": details if isinstance(details, dict) else {},
        }

    def register_gui(
        self,
        *,
        agent_id: str,
        display_name: str,
        provider_id: str | None = None,
        model_id: str | None = None,
        capabilities: list[str] | None = None,
        boundaries: list[str] | None = None,
    ) -> dict[str, Any]:
        self.registry.register_manual_gui_agent(
            agent_id=agent_id,
            display_name=display_name,
            provider_id=provider_id,
            model_id=model_id,
            capabilities=capabilities,
            boundaries=boundaries,
        )
        record = self.registry.discovery_record(f"manual:{agent_id}")
        if record is None:
            raise RuntimeError("manual GUI Agent registration was not persisted")
        return record

    def _scan_configured_agent(
        self,
        agent_id: str,
        settings: dict[str, Any],
        existing: dict[str, Any] | None,
    ) -> None:
        adapter = self.adapters[agent_id]
        executable = self._safe_check(
            adapter.check_executable,
            ExecutableStatus.UNKNOWN,
        )
        authentication = self._safe_check(
            adapter.check_authentication,
            AuthenticationStatus.UNKNOWN,
        )
        permission = self._safe_check(
            adapter.check_permissions,
            PermissionStatus.UNKNOWN,
        )
        configured_model = settings.get("model")
        models = (
            existing["models"]
            if existing and existing.get("models")
            else (
                [{"id": str(configured_model), "source": "configured"}]
                if configured_model
                else []
            )
        )
        connectivity = (
            existing["connectivity_status"]
            if existing
            else ConnectivityStatus.NOT_CHECKED.value
        )
        self.registry.upsert_discovery_record(
            record_id=self._configured_record_id(agent_id),
            agent_id=agent_id,
            display_name=agent_id,
            target_kind="configured_agent",
            adapter_type=str(settings.get("type", "mock")),
            executable_status=executable["status"],
            authentication_status=authentication["status"],
            permission_status=permission["status"],
            connectivity_status=connectivity,
            resolved_executable=executable.get("resolved_executable"),
            models=models,
            capabilities=adapter.discovery_capabilities(),
            details={
                "executable": executable.get("details", {}),
                "authentication": authentication.get("details", {}),
                "permissions": permission.get("details", {}),
            },
            source="config",
        )

    def _scan_known_target(
        self,
        target: LocalAgentTarget,
        existing: dict[str, Any] | None,
    ) -> None:
        resolved = self._resolve_command(target.command_candidates)
        agent_id = f"local-{target.key}" if resolved else None
        if resolved and agent_id:
            self.registry.register_discovered_cli(
                agent_id=agent_id,
                display_name=target.display_name,
                resolved_executable=resolved,
            )
        self.registry.upsert_discovery_record(
            record_id=self._known_record_id(target.key),
            agent_id=agent_id,
            display_name=target.display_name,
            target_kind="known_local_command",
            adapter_type="cli",
            executable_status=(
                ExecutableStatus.AVAILABLE
                if resolved
                else ExecutableStatus.MISSING
            ),
            authentication_status=AuthenticationStatus.UNKNOWN,
            permission_status=PermissionStatus.UNKNOWN,
            connectivity_status=(
                existing["connectivity_status"]
                if existing
                else ConnectivityStatus.NOT_CHECKED
            ),
            resolved_executable=resolved,
            models=existing["models"] if existing else [],
            capabilities={
                "executable_check": True,
                "authentication_check": False,
                "permission_check": False,
                "model_discovery": False,
                "connectivity_test": False,
                "manual_setup": True,
            },
            details={
                "command_candidates": list(target.command_candidates),
                "requires_configuration": True,
            },
            source="discovery",
        )

    def _configured_adapter(self, agent_id: str) -> AgentAdapter:
        try:
            return self.adapters[agent_id]
        except KeyError as exc:
            raise ValueError(
                f"agent {agent_id!r} is not a configured runnable Agent"
            ) from exc

    @staticmethod
    def _resolve_command(candidates: tuple[str, ...]) -> str | None:
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return str(Path(resolved).resolve())
            path = Path(candidate)
            if path.is_file():
                return str(path.resolve())
        return None

    @staticmethod
    def _safe_check(check, fallback_status) -> dict[str, Any]:
        try:
            result = check()
        except Exception as exc:
            return {
                "status": fallback_status.value,
                "details": {"error": type(exc).__name__},
            }
        if not isinstance(result, dict) or "status" not in result:
            return {
                "status": fallback_status.value,
                "details": {"error": "invalid_check_result"},
            }
        return result

    @staticmethod
    def _configured_record_id(agent_id: str) -> str:
        return f"configured:{agent_id}"

    @staticmethod
    def _known_record_id(key: str) -> str:
        return f"known:{key}"
