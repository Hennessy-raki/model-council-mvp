from __future__ import annotations

import glob
import shutil
import subprocess
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
from .versions import plan_upgrade, version_from_output


VERSION_PROBE_TIMEOUT_SECONDS = 15

# How a target can be driven. This is recorded per target so that a desktop
# application is never silently mixed in with something the control plane can
# invoke, which would violate "do not mistake a registered model for a runnable
# one".
INTERFACE_CLI = "cli"
INTERFACE_GUI_ONLY = "gui_only"
INTERFACE_KINDS = (INTERFACE_CLI, INTERFACE_GUI_ONLY)


@dataclass(frozen=True)
class LocalAgentTarget:
    key: str
    display_name: str
    # Empty for a GUI-only target: there is no command for the control plane to
    # resolve or invoke.
    command_candidates: tuple[str, ...] = ()
    # The argument that makes the tool print its version, and the path patterns
    # worth probing in addition to PATH. Both are data so that an operator can
    # add a tool without editing this module.
    version_arguments: tuple[str, ...] = ("--version",)
    extra_path_patterns: tuple[str, ...] = ()
    # `cli` means the control plane can invoke the tool itself. `gui_only` means
    # it cannot, and the Agent is recorded for visibility and manual handoff.
    interface_kind: str = INTERFACE_CLI


# A starting catalogue, not a closed list. An operator extends or replaces it
# through `discovery_targets` in the configuration, which is what keeps the
# control plane from being bound to any single vendor.
KNOWN_LOCAL_AGENTS = (
    LocalAgentTarget("codex", "Codex CLI", ("codex.cmd", "codex")),
    LocalAgentTarget("claude", "Claude Code CLI", ("claude.cmd", "claude")),
    LocalAgentTarget("gemini", "Gemini CLI", ("gemini.cmd", "gemini")),
    LocalAgentTarget("opencode", "OpenCode CLI", ("opencode.cmd", "opencode")),
    LocalAgentTarget("reasonix", "Reasonix", ("reasonix.cmd", "reasonix")),
)

# Desktop applications that have no command-line interface of their own. They
# are recorded so the operator can see what exists on the machine and hand work
# over manually. No command is probed and no invocation path is claimed.
KNOWN_GUI_ONLY_AGENTS = (
    LocalAgentTarget(
        "zcode",
        "ZCode",
        (),
        version_arguments=(),
        extra_path_patterns=(),
        interface_kind=INTERFACE_GUI_ONLY,
    ),
)


def target_from_config(item: Any, label: str) -> LocalAgentTarget:
    """Build one discovery target from configuration data."""
    if not isinstance(item, dict):
        raise ValueError(f"{label} must be an object")
    key = item.get("key")
    if not isinstance(key, str) or not key.strip():
        raise ValueError(f"{label}.key must be a non-empty string")
    display_name = item.get("display_name")
    if display_name is not None and not isinstance(display_name, str):
        raise ValueError(f"{label}.display_name must be a string")
    commands = item.get("command_candidates", [])
    if not isinstance(commands, list) or any(
        not isinstance(value, str) or not value for value in commands
    ):
        raise ValueError(
            f"{label}.command_candidates must be a list of non-empty strings"
        )
    interface_kind = item.get("interface_kind", INTERFACE_CLI)
    if interface_kind not in INTERFACE_KINDS:
        choices = ", ".join(INTERFACE_KINDS)
        raise ValueError(f"{label}.interface_kind must be one of: {choices}")
    if interface_kind == INTERFACE_CLI and not commands:
        raise ValueError(
            f"{label}.command_candidates must name at least one command for a "
            "cli target"
        )
    arguments = item.get("version_arguments", ["--version"])
    if not isinstance(arguments, list) or any(
        not isinstance(value, str) for value in arguments
    ):
        raise ValueError(f"{label}.version_arguments must be a list of strings")
    patterns = item.get("extra_path_patterns", [])
    if not isinstance(patterns, list) or any(
        not isinstance(value, str) or not value for value in patterns
    ):
        raise ValueError(
            f"{label}.extra_path_patterns must be a list of non-empty strings"
        )
    return LocalAgentTarget(
        key=key.strip(),
        display_name=(display_name or key).strip(),
        command_candidates=tuple(commands),
        version_arguments=tuple(arguments),
        extra_path_patterns=tuple(patterns),
        interface_kind=interface_kind,
    )


def targets_from_config(value: Any) -> tuple[LocalAgentTarget, ...]:
    if value is None:
        return KNOWN_LOCAL_AGENTS
    if not isinstance(value, list) or not value:
        raise ValueError("discovery_targets must be a non-empty list")
    return tuple(
        target_from_config(item, f"discovery_targets[{index}]")
        for index, item in enumerate(value)
    )


def gui_targets_from_config(value: Any) -> tuple[LocalAgentTarget, ...]:
    """Build the GUI-only part of the catalogue.

    GUI-only entries live in their own list so that a declared application can
    never be mistaken for something the control plane can invoke. An entry here
    is recorded for visibility and manual handoff only.
    """
    if value is None:
        return KNOWN_GUI_ONLY_AGENTS
    if not isinstance(value, list):
        raise ValueError("gui_only_targets must be a list")
    if not value:
        return ()
    targets = []
    for index, item in enumerate(value):
        label = f"gui_only_targets[{index}]"
        target = target_from_config(item, label)
        if target.interface_kind != INTERFACE_GUI_ONLY:
            raise ValueError(
                f"{label}.interface_kind must be {INTERFACE_GUI_ONLY!r} in "
                "gui_only_targets"
            )
        targets.append(target)
    return tuple(targets)


class DiscoveryService:
    """Local Agent discovery without automatic routing or project disclosure."""

    def __init__(
        self,
        config: CouncilConfig,
        registry: RegistryService,
        adapters: dict[str, AgentAdapter] | None = None,
        known_targets: tuple[LocalAgentTarget, ...] | None = None,
        version_probe: Any = None,
        gui_targets: tuple[LocalAgentTarget, ...] | None = None,
    ):
        self.config = config
        self.registry = registry
        # An explicitly supplied mapping is honoured even when it is empty: an
        # empty dict means "no configured runnable Agent", which is different
        # from "not supplied". `adapters or ...` would treat the two the same
        # and then fail on a missing config.
        if adapters is None:
            if config is None:
                raise ValueError(
                    "a config or an explicit adapters mapping is required"
                )
            adapters = build_adapters(config, registry.store)
        self.adapters = adapters
        if known_targets is None:
            known_targets = targets_from_config(
                config.discovery_targets if config else None
            )
        self.known_targets = known_targets
        if gui_targets is None:
            gui_targets = gui_targets_from_config(
                config.gui_only_targets if config else None
            )
        self.gui_targets = gui_targets
        self.version_probe = version_probe or self._probe_version

    def version_candidates(
        self,
        target: LocalAgentTarget,
        *,
        existing: dict[str, Any] | None = None,
        resolved_commands: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Collect every installed form of one target and rank them.

        Several Agents exist in more than one version on the same machine at the
        same time, so 'which one' is a decision rather than a detail. The
        ranking is a recommendation only: it changes no binding.

        ``resolved_commands`` lets a caller that has already resolved the target
        reuse that work instead of resolving each candidate a second time.
        """
        seen: set[str] = set()
        candidates: list[dict[str, Any]] = []
        if resolved_commands is None:
            resolved_commands = tuple(
                resolved
                for resolved in (
                    self._resolve_command((candidate,))
                    for candidate in target.command_candidates
                )
                if resolved
            )
        for resolved in resolved_commands:
            if resolved in seen:
                continue
            seen.add(resolved)
            candidates.append(
                {
                    "version": self.version_probe(resolved, target),
                    "source": "path",
                    "agent_id": f"local-{target.key}",
                    "path": resolved,
                }
            )
        for pattern in target.extra_path_patterns:
            # glob.glob handles absolute patterns; pathlib.Path.glob rejects
            # them, which would make an operator-supplied absolute pattern fail
            # at scan time.
            for match in sorted(glob.glob(pattern)):
                path = Path(match)
                text = str(path)
                if text in seen or not path.is_file():
                    continue
                seen.add(text)
                candidates.append(
                    {
                        "version": self.version_probe(text, target),
                        "source": "configured_path",
                        "agent_id": f"local-{target.key}",
                        "path": text,
                    }
                )
        preferred = None
        if existing and existing.get("details"):
            details = existing["details"]
            if isinstance(details, dict):
                value = details.get("preferred_version")
                if isinstance(value, str) and value:
                    preferred = value
        plan = plan_upgrade(candidates, preferred_version=preferred)
        return {
            "target_key": target.key,
            "display_name": target.display_name,
            "candidates": candidates,
            "versions_detected": [
                item["version"] for item in candidates if item["version"]
            ],
            "undetected": [
                item["path"] for item in candidates if not item["version"]
            ],
            "plan": plan,
            "auto_switch": False,
        }

    def scan(self) -> list[dict[str, Any]]:
        existing = {
            item["id"]: item for item in self.registry.discovery_records()
        }
        # A catalogue-only scan is valid: the service can rank installed Agent
        # versions without any configured runnable Agent.
        for agent_id, settings in (self.config.agents.items() if self.config else ()):
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
        for target in self.gui_targets:
            self._scan_gui_target(
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
        # Resolve once and reuse: the command candidates are the same list for
        # registration and for version ranking, so probing must not trigger a
        # second `which` sweep.
        resolved_all = self._resolve_all_commands(target)
        resolved = resolved_all[0] if resolved_all else None
        agent_id = f"local-{target.key}" if resolved else None
        if resolved and agent_id:
            self.registry.register_discovered_cli(
                agent_id=agent_id,
                display_name=target.display_name,
                resolved_executable=resolved,
            )
        ranking = self.version_candidates(
            target,
            existing=existing,
            resolved_commands=resolved_all,
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
                "version_probe": True,
            },
            details={
                "command_candidates": list(target.command_candidates),
                "version_arguments": list(target.version_arguments),
                "extra_path_patterns": list(target.extra_path_patterns),
                "requires_configuration": True,
                "version_candidates": ranking["candidates"],
                "versions_detected": ranking["versions_detected"],
                "undetected": ranking["undetected"],
                "version_plan": ranking["plan"],
            },
            source="discovery",
        )

    def _scan_gui_target(
        self,
        target: LocalAgentTarget,
        existing: dict[str, Any] | None,
    ) -> None:
        """Record a GUI-only Agent without claiming any invocation path.

        This exists so the operator can see what is installed. It registers no
        runnable Agent, resolves no command, probes no version and creates no
        binding: a desk application is not mistaken for something the control
        plane can drive.
        """
        existing_paths = []
        if existing and isinstance(existing.get("details"), dict):
            value = existing["details"].get("install_locations")
            if isinstance(value, list):
                existing_paths = [item for item in value if isinstance(item, str)]
        self.registry.upsert_discovery_record(
            record_id=self._known_record_id(target.key),
            agent_id=None,
            display_name=target.display_name,
            target_kind="gui_only_application",
            adapter_type="manual",
            executable_status=ExecutableStatus.UNKNOWN,
            authentication_status=AuthenticationStatus.UNKNOWN,
            permission_status=PermissionStatus.UNKNOWN,
            connectivity_status=(
                existing["connectivity_status"]
                if existing
                else ConnectivityStatus.NOT_CHECKED
            ),
            resolved_executable=None,
            models=[],
            capabilities={
                "executable_check": False,
                "authentication_check": False,
                "permission_check": False,
                "model_discovery": False,
                "connectivity_test": False,
                "manual_setup": True,
                "invocable": False,
                "version_probe": False,
            },
            details={
                "interface_kind": INTERFACE_GUI_ONLY,
                "install_locations": existing_paths,
                "requires_manual_handoff": True,
                "note": (
                    "no command-line interface; the operator drives this "
                    "application by hand"
                ),
            },
            source="discovery",
        )

    def _resolve_all_commands(
        self,
        target: LocalAgentTarget,
    ) -> tuple[str, ...]:
        """Resolve every command candidate of one target once."""
        resolved: list[str] = []
        for candidate in target.command_candidates:
            found = self._resolve_command((candidate,))
            if found:
                resolved.append(found)
        return tuple(resolved)

    def _probe_version(
        self,
        executable: str,
        target: LocalAgentTarget,
    ) -> str | None:
        """Ask one installed executable for its version.

        Bounded, argument-array, shell-free and time-limited, matching the
        project's rule for every CLI invocation. The probe sends no project
        context; it only asks the tool to identify itself.
        """
        if not target.version_arguments:
            return None
        try:
            completed = subprocess.run(
                [executable, *target.version_arguments],
                shell=False,
                capture_output=True,
                timeout=VERSION_PROBE_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        output = (completed.stdout or b"") + b"\n" + (completed.stderr or b"")
        return version_from_output(
            output.decode("utf-8", "replace")
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
