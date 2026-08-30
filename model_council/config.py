from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .types import AgentCard, ProvenanceDisplayMode


@dataclass(frozen=True)
class CouncilConfig:
    path: Path
    project_name: str
    state_dir: Path
    max_parallel: int
    manager: str
    reviewer: str | None
    providers: dict[str, dict[str, Any]]
    models: dict[str, dict[str, Any]]
    agents: dict[str, dict[str, Any]]
    role_assignments: dict[str, dict[str, Any]]
    settings: dict[str, Any]
    budgets: dict[str, dict[str, Any]]
    mcp_servers: dict[str, dict[str, Any]]

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
    providers = _optional_object(data, "providers")
    models = _optional_object(data, "models")
    role_assignments = _optional_object(data, "role_assignments")
    settings = _optional_object(data, "settings")
    budgets = _optional_object(data, "budgets")
    mcp_servers = _optional_object(data, "mcp_servers")
    project_name = str(data.get("project_name", "model-council"))
    if "artifact_provenance_display" in settings:
        try:
            ProvenanceDisplayMode(settings["artifact_provenance_display"])
        except ValueError as exc:
            choices = ", ".join(mode.value for mode in ProvenanceDisplayMode)
            raise ValueError(
                "settings.artifact_provenance_display must be one of: "
                f"{choices}"
            ) from exc

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
        if item.get("type", "mock") not in {
            "mock",
            "cli",
            "openai_compatible",
            "codex_app_server",
            "a2a",
        }:
            raise ValueError(f"agent {name!r} has unsupported type {item.get('type')!r}")
        adapter_type = str(item.get("type", "mock"))
        if adapter_type == "codex_app_server":
            _validate_interop_flags(item, f"agent {name!r}")
            _command_array(
                item.get("command"),
                f"agent {name!r} command",
            )
            _reject_plaintext_auth(item, f"agent {name!r}")
            _validate_outbound_context_policy(item, f"agent {name!r}")
            _validate_codex_cwd(item, f"agent {name!r}")
        elif adapter_type == "a2a":
            _validate_interop_flags(item, f"agent {name!r}")
            if not str(item.get("endpoint", "")).strip():
                raise ValueError(f"A2A agent {name!r} requires endpoint")
            _reject_plaintext_auth(item, f"agent {name!r}")
        provider = item.get("provider")
        model = item.get("model")
        if provider is not None and str(provider) not in providers:
            raise ValueError(
                f"agent {name!r} references unknown provider {provider!r}"
            )
        if model is not None and str(model) not in models:
            raise ValueError(f"agent {name!r} references unknown model {model!r}")

    for name, item in providers.items():
        if not isinstance(item, dict):
            raise ValueError(f"provider {name!r} must be an object")

    for name, item in models.items():
        if not isinstance(item, dict):
            raise ValueError(f"model {name!r} must be an object")
        provider = item.get("provider")
        if not provider:
            raise ValueError(f"model {name!r} must reference a provider")
        if str(provider) not in providers:
            raise ValueError(
                f"model {name!r} references unknown provider {provider!r}"
            )

    for role_key, item in role_assignments.items():
        if not isinstance(item, dict):
            raise ValueError(f"role assignment {role_key!r} must be an object")
        mode = str(item.get("mode", "manual"))
        if mode not in {"manual", "auto", "hybrid"}:
            raise ValueError(
                f"role assignment {role_key!r} has unsupported mode {mode!r}"
            )
        agent = item.get("agent")
        model = item.get("model")
        if mode == "manual" and not agent:
            raise ValueError(
                f"manual role assignment {role_key!r} requires an agent"
            )
        if bool(item.get("locked", False)) and not agent:
            raise ValueError(
                f"locked role assignment {role_key!r} requires an agent"
            )
        if agent is not None and str(agent) not in agents:
            raise ValueError(
                f"role assignment {role_key!r} references unknown agent {agent!r}"
            )
        if model is not None and str(model) not in models:
            raise ValueError(
                f"role assignment {role_key!r} references unknown model {model!r}"
            )
        validate_routing_constraints(
            item.get("constraints", {}),
            f"role assignment {role_key!r}",
        )

    for budget_id, item in budgets.items():
        if not isinstance(item, dict):
            raise ValueError(f"budget {budget_id!r} must be an object")
        scope = str(item.get("scope", "project"))
        metric = str(item.get("metric", "tokens"))
        if scope not in {"project", "run", "role"}:
            raise ValueError(f"budget {budget_id!r} has unsupported scope {scope!r}")
        if metric not in {"tokens", "cost"}:
            raise ValueError(
                f"budget {budget_id!r} has unsupported metric {metric!r}"
            )
        scope_key = item.get("scope_key")
        if scope in {"run", "role"} and not scope_key:
            raise ValueError(
                f"budget {budget_id!r} requires scope_key for {scope!r}"
            )
        warning = _optional_non_negative_decimal(
            item.get("warning"),
            f"budget {budget_id!r} warning",
        )
        hard = _optional_non_negative_decimal(
            item.get("hard"),
            f"budget {budget_id!r} hard",
        )
        if warning is None and hard is None:
            raise ValueError(
                f"budget {budget_id!r} requires warning or hard limit"
            )
        if warning is not None and hard is not None and warning > hard:
            raise ValueError(
                f"budget {budget_id!r} warning cannot exceed hard limit"
            )
        if metric == "cost" and not str(item.get("currency", "")).strip():
            raise ValueError(f"cost budget {budget_id!r} requires currency")

    for server_id, item in mcp_servers.items():
        if not isinstance(item, dict):
            raise ValueError(f"MCP server {server_id!r} must be an object")
        transport = str(item.get("transport", "stdio"))
        _validate_interop_flags(item, f"MCP server {server_id!r}")
        if transport not in {"stdio", "streamable_http"}:
            raise ValueError(
                f"MCP server {server_id!r} has unsupported transport "
                f"{transport!r}"
            )
        if transport == "stdio":
            _command_array(
                item.get("command"),
                f"MCP server {server_id!r} command",
            )
        elif not str(item.get("endpoint", "")).strip():
            raise ValueError(
                f"Streamable HTTP MCP server {server_id!r} requires endpoint"
            )
        _reject_plaintext_auth(item, f"MCP server {server_id!r}")

    return CouncilConfig(
        path=config_path,
        project_name=project_name,
        state_dir=state_dir.resolve(),
        max_parallel=max_parallel,
        manager=manager,
        reviewer=reviewer,
        providers=providers,
        models=models,
        agents=agents,
        role_assignments=role_assignments,
        settings=settings,
        budgets=budgets,
        mcp_servers=mcp_servers,
    )


def _optional_object(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"config.{key} must be an object")
    return value


def _optional_non_negative_decimal(
    value: Any,
    label: str,
) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return result


def _command_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"{label} must be a non-empty string array")
    sensitive_flags = (
        "--api-key",
        "--authorization",
        "--bearer",
        "--password",
        "--secret",
        "--token",
    )
    for item in value:
        normalized = item.lower()
        if normalized in sensitive_flags or any(
            normalized.startswith(f"{flag}=") for flag in sensitive_flags
        ):
            raise ValueError(
                f"{label} must not contain inline credential arguments"
            )
    return value


def _reject_plaintext_auth(value: dict[str, Any], label: str) -> None:
    def inspect(item: Any) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                normalized = str(key).lower().replace("-", "_")
                if normalized.endswith(("_env", "_env_var")):
                    continue
                token_key = (
                    normalized == "token"
                    or normalized.endswith("_token")
                    or "access_token" in normalized
                    or "refresh_token" in normalized
                )
                if token_key or any(
                    part in normalized
                    for part in (
                        "api_key",
                        "authorization",
                        "bearer",
                        "password",
                        "secret",
                    )
                ):
                    if nested not in (None, "", False):
                        raise ValueError(
                            f"{label} must reference credentials through "
                            "environment variable names"
                        )
                inspect(nested)
        elif isinstance(item, list):
            for nested in item:
                inspect(nested)

    inspect(value)


def _validate_interop_flags(value: dict[str, Any], label: str) -> None:
    for key in ("enabled", "invoke_enabled"):
        if key in value and not isinstance(value[key], bool):
            raise ValueError(f"{label} {key} must be true or false")
    if "auth_env" in value and (
        not isinstance(value["auth_env"], str)
        or not value["auth_env"].strip()
    ):
        raise ValueError(f"{label} auth_env must be a non-empty string")


def _validate_outbound_context_policy(
    value: dict[str, Any],
    label: str,
) -> None:
    policy = value.get("outbound_context")
    if not isinstance(policy, dict):
        raise ValueError(
            f"{label} requires an outbound_context object for exact scope approval"
        )
    source = policy.get("source")
    if source not in {"synthetic", "repository"}:
        raise ValueError(
            f"{label} outbound_context.source must be 'synthetic' or 'repository'"
        )
    allowed_sources = policy.get("allowed_sources")
    if (
        not isinstance(allowed_sources, list)
        or not allowed_sources
        or not all(item in {"synthetic", "repository"} for item in allowed_sources)
    ):
        raise ValueError(
            f"{label} outbound_context.allowed_sources must be a non-empty "
            "array containing only 'synthetic' or 'repository'"
        )
    if source not in allowed_sources:
        raise ValueError(
            f"{label} outbound_context.source must be included in allowed_sources"
        )
    for key in (
        "max_files",
        "max_total_bytes",
        "max_artifacts",
        "max_artifact_bytes",
    ):
        number = policy.get(key)
        if not isinstance(number, int) or number < 0:
            raise ValueError(
                f"{label} outbound_context.{key} must be a non-negative integer"
            )
    patterns = policy.get("excluded_patterns")
    if patterns is not None and (
        not isinstance(patterns, list)
        or not all(isinstance(item, str) and item for item in patterns)
    ):
        raise ValueError(
            f"{label} outbound_context.excluded_patterns must be a string array"
        )


def _validate_codex_cwd(value: dict[str, Any], label: str) -> None:
    cwd = value.get("cwd")
    cwd_env = value.get("cwd_env")
    if cwd and cwd_env:
        raise ValueError(f"{label} must not set both cwd and cwd_env")
    if not cwd and not cwd_env:
        raise ValueError(
            f"{label} requires cwd or cwd_env so working-directory disclosure "
            "is explicit"
        )
    if cwd_env is not None and (
        not isinstance(cwd_env, str) or not cwd_env.strip()
    ):
        raise ValueError(f"{label} cwd_env must be a non-empty string")


def validate_routing_constraints(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} constraints must be an object")
    list_fields = (
        "required_capabilities",
        "excluded_agents",
        "excluded_models",
        "excluded_providers",
        "separate_from_roles",
        "separation_dimensions",
        "distinct_agent_from_roles",
        "distinct_model_from_roles",
        "distinct_provider_from_roles",
    )
    for field in list_fields:
        if field in value and not isinstance(value[field], list):
            raise ValueError(f"{label} constraints.{field} must be an array")
    for field in (
        "max_cost",
        "max_average_cost",
        "max_latency_ms",
        "max_average_latency_ms",
    ):
        if field in value:
            _optional_non_negative_decimal(
                value[field],
                f"{label} constraints.{field}",
            )
    dimensions = {
        str(item) for item in value.get("separation_dimensions", [])
    }
    unsupported = dimensions - {"agent", "model", "provider"}
    if unsupported:
        raise ValueError(
            f"{label} has unsupported separation dimensions "
            f"{sorted(unsupported)}"
        )
    separation = value.get("separation")
    if separation is not None:
        if not isinstance(separation, dict):
            raise ValueError(f"{label} constraints.separation must be an object")
        if not isinstance(separation.get("roles", []), list):
            raise ValueError(
                f"{label} constraints.separation.roles must be an array"
            )
        if not isinstance(separation.get("dimensions", []), list):
            raise ValueError(
                f"{label} constraints.separation.dimensions must be an array"
            )
        unsupported = {
            str(item) for item in separation.get("dimensions", [])
        } - {"agent", "model", "provider"}
        if unsupported:
            raise ValueError(
                f"{label} has unsupported separation dimensions "
                f"{sorted(unsupported)}"
            )
