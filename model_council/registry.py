from __future__ import annotations

import json
from typing import Any

from .config import CouncilConfig, validate_routing_constraints
from .store import CouncilStore, utc_now
from .types import (
    AuthenticationStatus,
    ConnectivityStatus,
    ExecutableStatus,
    PermissionStatus,
    ProvenanceDisplayMode,
)


ROLE_MODES = {"manual", "auto", "hybrid"}
SENSITIVE_KEY_PARTS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "password",
    "secret",
    "token",
}
PROVENANCE_DISPLAY_SETTING = "artifact_provenance_display"


class RegistryService:
    """Persistent settings and provider/model/agent catalog."""

    def __init__(self, store: CouncilStore):
        self.store = store

    def sync_from_config(self, config: CouncilConfig) -> dict[str, int]:
        now = utc_now()
        role_assignments = dict(config.role_assignments)
        if "decision_manager" not in role_assignments:
            role_assignments["decision_manager"] = {
                "mode": "manual",
                "agent": config.manager,
                "locked": True,
            }
        if config.reviewer and "independent_reviewer" not in role_assignments:
            role_assignments["independent_reviewer"] = {
                "mode": "manual",
                "agent": config.reviewer,
                "locked": True,
            }

        with self.store.connect() as conn:
            for provider_id, item in config.providers.items():
                conn.execute(
                    """
                    INSERT INTO providers(
                        id, display_name, kind, enabled, config_json, source,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'config', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        display_name = excluded.display_name,
                        kind = excluded.kind,
                        enabled = excluded.enabled,
                        config_json = excluded.config_json,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    WHERE excluded.source = 'user' OR providers.source != 'user'
                    """,
                    (
                        provider_id,
                        str(item.get("display_name", provider_id)),
                        str(item.get("kind", "custom")),
                        int(bool(item.get("enabled", True))),
                        _dump(sanitize_for_storage(item)),
                        now,
                        now,
                    ),
                )

            for model_id, item in config.models.items():
                conn.execute(
                    """
                    INSERT INTO models(
                        id, provider_id, display_name, enabled,
                        capabilities_json, metadata_json, source,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'config', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        provider_id = excluded.provider_id,
                        display_name = excluded.display_name,
                        enabled = excluded.enabled,
                        capabilities_json = excluded.capabilities_json,
                        metadata_json = excluded.metadata_json,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    WHERE excluded.source = 'user' OR models.source != 'user'
                    """,
                    (
                        model_id,
                        str(item["provider"]),
                        str(item.get("display_name", model_id)),
                        int(bool(item.get("enabled", True))),
                        _dump(item.get("capabilities", [])),
                        _dump(
                            sanitize_for_storage(
                                {
                                    key: value
                                    for key, value in item.items()
                                    if key
                                    not in {
                                        "provider",
                                        "display_name",
                                        "enabled",
                                        "capabilities",
                                    }
                                }
                            )
                        ),
                        now,
                        now,
                    ),
                )

            for agent_id, item in config.agents.items():
                excluded = {
                    "type",
                    "provider",
                    "model",
                    "role",
                    "description",
                    "enabled",
                    "capabilities",
                    "boundaries",
                }
                conn.execute(
                    """
                    INSERT INTO agent_profiles(
                        id, adapter_type, provider_id, model_id, role,
                        description, enabled, capabilities_json,
                        boundaries_json, config_json, source,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'config', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        adapter_type = excluded.adapter_type,
                        provider_id = excluded.provider_id,
                        model_id = excluded.model_id,
                        role = excluded.role,
                        description = excluded.description,
                        enabled = excluded.enabled,
                        capabilities_json = excluded.capabilities_json,
                        boundaries_json = excluded.boundaries_json,
                        config_json = excluded.config_json,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    WHERE excluded.source = 'user' OR agent_profiles.source != 'user'
                    """,
                    (
                        agent_id,
                        str(item.get("type", "mock")),
                        _optional_text(item.get("provider")),
                        _optional_text(item.get("model")),
                        str(item.get("role", agent_id)),
                        str(item.get("description", "")),
                        int(bool(item.get("enabled", True))),
                        _dump(item.get("capabilities", [])),
                        _dump(item.get("boundaries", [])),
                        _dump(
                            sanitize_for_storage(
                                {
                                    key: value
                                    for key, value in item.items()
                                    if key not in excluded
                                }
                            )
                        ),
                        now,
                        now,
                    ),
                )

            for role_key, item in role_assignments.items():
                self._upsert_role(
                    conn=conn,
                    role_key=role_key,
                    mode=str(item.get("mode", "manual")),
                    agent_id=_optional_text(item.get("agent")),
                    model_id=_optional_text(item.get("model")),
                    locked=bool(item.get("locked", False)),
                    constraints=item.get("constraints", {}),
                    source="config",
                    now=now,
                )

            for key, value in config.settings.items():
                conn.execute(
                    """
                    INSERT INTO app_settings(key, value_json, source, updated_at)
                    VALUES (?, ?, 'config', ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value_json = excluded.value_json,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    WHERE excluded.source = 'user' OR app_settings.source != 'user'
                    """,
                    (key, _dump(sanitize_for_storage(value)), now),
                )

        return {
            "providers": len(config.providers),
            "models": len(config.models),
            "agents": len(config.agents),
            "roles": len(role_assignments),
            "settings": len(config.settings),
        }

    def assign_role(
        self,
        role_key: str,
        mode: str,
        agent_id: str | None = None,
        model_id: str | None = None,
        locked: bool = False,
        constraints: dict[str, Any] | None = None,
    ) -> None:
        if mode not in ROLE_MODES:
            raise ValueError(f"unsupported role mode {mode!r}")
        if mode == "manual" and not agent_id:
            raise ValueError("manual role assignment requires an agent")
        if locked and not agent_id:
            raise ValueError("locked role assignment requires an agent")
        validate_routing_constraints(
            constraints or {},
            f"role assignment {role_key!r}",
        )
        now = utc_now()
        with self.store.connect() as conn:
            if agent_id and not self._exists(conn, "agent_profiles", agent_id):
                raise ValueError(f"unknown agent {agent_id!r}")
            if model_id and not self._exists(conn, "models", model_id):
                raise ValueError(f"unknown model {model_id!r}")
            self._upsert_role(
                conn=conn,
                role_key=role_key,
                mode=mode,
                agent_id=agent_id,
                model_id=model_id,
                locked=locked,
                constraints=constraints or {},
                source="user",
                now=now,
            )

    def set_setting(self, key: str, value: Any) -> None:
        if not key.strip():
            raise ValueError("setting key cannot be empty")
        if key == PROVENANCE_DISPLAY_SETTING:
            try:
                value = ProvenanceDisplayMode(value).value
            except ValueError as exc:
                choices = ", ".join(mode.value for mode in ProvenanceDisplayMode)
                raise ValueError(
                    f"{PROVENANCE_DISPLAY_SETTING} must be one of: {choices}"
                ) from exc
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings(key, value_json, source, updated_at)
                VALUES (?, ?, 'user', ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (key, _dump(sanitize_for_storage(value)), utc_now()),
            )

    def provenance_display_mode(self) -> ProvenanceDisplayMode:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE key = ?",
                (PROVENANCE_DISPLAY_SETTING,),
            ).fetchone()
        if row is None:
            return ProvenanceDisplayMode.COMPACT
        try:
            return ProvenanceDisplayMode(json.loads(row["value_json"]))
        except ValueError as exc:
            choices = ", ".join(mode.value for mode in ProvenanceDisplayMode)
            raise ValueError(
                f"stored {PROVENANCE_DISPLAY_SETTING} must be one of: {choices}"
            ) from exc

    def setting_value(self, key: str, default: Any = None) -> Any:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        return json.loads(row["value_json"])

    def upsert_discovery_record(
        self,
        *,
        record_id: str,
        agent_id: str | None,
        display_name: str,
        target_kind: str,
        adapter_type: str,
        executable_status: str | ExecutableStatus,
        authentication_status: str | AuthenticationStatus,
        permission_status: str | PermissionStatus,
        connectivity_status: str | ConnectivityStatus,
        resolved_executable: str | None = None,
        models: list[dict[str, Any]] | None = None,
        capabilities: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
        source: str = "discovery",
    ) -> None:
        if not record_id.strip():
            raise ValueError("discovery record id cannot be empty")
        executable_status = ExecutableStatus(executable_status).value
        authentication_status = AuthenticationStatus(
            authentication_status
        ).value
        permission_status = PermissionStatus(permission_status).value
        connectivity_status = ConnectivityStatus(connectivity_status).value
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_discovery(
                    id, agent_id, display_name, target_kind, adapter_type,
                    executable_status, authentication_status, permission_status,
                    connectivity_status, resolved_executable, models_json,
                    capabilities_json, details_json, source, checked_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    display_name = excluded.display_name,
                    target_kind = excluded.target_kind,
                    adapter_type = excluded.adapter_type,
                    executable_status = excluded.executable_status,
                    authentication_status = excluded.authentication_status,
                    permission_status = excluded.permission_status,
                    connectivity_status = excluded.connectivity_status,
                    resolved_executable = excluded.resolved_executable,
                    models_json = excluded.models_json,
                    capabilities_json = excluded.capabilities_json,
                    details_json = excluded.details_json,
                    source = excluded.source,
                    checked_at = excluded.checked_at,
                    updated_at = excluded.updated_at
                WHERE excluded.source = 'user' OR agent_discovery.source != 'user'
                """,
                (
                    record_id,
                    agent_id,
                    display_name,
                    target_kind,
                    adapter_type,
                    executable_status,
                    authentication_status,
                    permission_status,
                    connectivity_status,
                    resolved_executable,
                    _dump(sanitize_for_storage(models or [])),
                    _dump(sanitize_for_storage(capabilities or {})),
                    _dump(sanitize_for_storage(details or {})),
                    source,
                    now,
                    now,
                    now,
                ),
            )

    def update_discovered_models(
        self,
        record_id: str,
        models: list[dict[str, Any]],
    ) -> None:
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE agent_discovery
                SET models_json = ?, checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    _dump(sanitize_for_storage(models)),
                    utc_now(),
                    utc_now(),
                    record_id,
                ),
            ).rowcount
        if not updated:
            raise ValueError(f"discovery record {record_id!r} not found")

    def update_connectivity(
        self,
        record_id: str,
        status: str | ConnectivityStatus,
        details: dict[str, Any] | None = None,
    ) -> None:
        status = ConnectivityStatus(status).value
        now = utc_now()
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT details_json FROM agent_discovery WHERE id = ?",
                (record_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"discovery record {record_id!r} not found")
            current_details = json.loads(row["details_json"])
            current_details["connectivity"] = sanitize_for_storage(details or {})
            conn.execute(
                """
                UPDATE agent_discovery
                SET connectivity_status = ?, details_json = ?,
                    checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    _dump(current_details),
                    now,
                    now,
                    record_id,
                ),
            )

    def discovery_record(self, record_id: str) -> dict[str, Any] | None:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_discovery WHERE id = ?",
                (record_id,),
            ).fetchone()
        return self._decode_discovery(row) if row else None

    def discovery_records(self) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM agent_discovery
                ORDER BY target_kind, display_name, id
                """
            ).fetchall()
        return [self._decode_discovery(row) for row in rows]

    def register_discovered_cli(
        self,
        agent_id: str,
        display_name: str,
        resolved_executable: str,
    ) -> None:
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_profiles(
                    id, adapter_type, provider_id, model_id, role,
                    description, enabled, capabilities_json,
                    boundaries_json, config_json, source,
                    created_at, updated_at
                ) VALUES (?, 'cli', NULL, NULL, 'unassigned', ?, 1, '[]',
                    ?, ?, 'discovery', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    adapter_type = excluded.adapter_type,
                    description = excluded.description,
                    enabled = excluded.enabled,
                    boundaries_json = excluded.boundaries_json,
                    config_json = excluded.config_json,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                WHERE agent_profiles.source = 'discovery'
                """,
                (
                    agent_id,
                    f"Locally discovered {display_name}",
                    _dump(["discovery-only", "not assigned to a project role"]),
                    _dump(
                        {
                            "command": [resolved_executable],
                            "discovered": True,
                        }
                    ),
                    now,
                    now,
                ),
            )

    def register_manual_gui_agent(
        self,
        *,
        agent_id: str,
        display_name: str,
        provider_id: str | None = None,
        model_id: str | None = None,
        capabilities: list[str] | None = None,
        boundaries: list[str] | None = None,
    ) -> None:
        if not agent_id.strip():
            raise ValueError("agent id cannot be empty")
        if not display_name.strip():
            raise ValueError("display name cannot be empty")
        now = utc_now()
        with self.store.connect() as conn:
            if provider_id and not self._exists(conn, "providers", provider_id):
                raise ValueError(f"unknown provider {provider_id!r}")
            if model_id and not self._exists(conn, "models", model_id):
                raise ValueError(f"unknown model {model_id!r}")
            if model_id and provider_id:
                model_provider = conn.execute(
                    "SELECT provider_id FROM models WHERE id = ?",
                    (model_id,),
                ).fetchone()["provider_id"]
                if model_provider != provider_id:
                    raise ValueError(
                        f"model {model_id!r} does not belong to provider "
                        f"{provider_id!r}"
                    )
            conn.execute(
                """
                INSERT INTO agent_profiles(
                    id, adapter_type, provider_id, model_id, role,
                    description, enabled, capabilities_json,
                    boundaries_json, config_json, source,
                    created_at, updated_at
                ) VALUES (?, 'gui', ?, ?, 'unassigned', ?, 1, ?, ?, '{}',
                    'user', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    adapter_type = excluded.adapter_type,
                    provider_id = excluded.provider_id,
                    model_id = excluded.model_id,
                    role = excluded.role,
                    description = excluded.description,
                    enabled = excluded.enabled,
                    capabilities_json = excluded.capabilities_json,
                    boundaries_json = excluded.boundaries_json,
                    config_json = excluded.config_json,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (
                    agent_id,
                    provider_id,
                    model_id,
                    display_name,
                    _dump(capabilities or []),
                    _dump(boundaries or []),
                    now,
                    now,
                ),
            )
        self.upsert_discovery_record(
            record_id=f"manual:{agent_id}",
            agent_id=agent_id,
            display_name=display_name,
            target_kind="manual_gui",
            adapter_type="gui",
            executable_status=ExecutableStatus.NOT_APPLICABLE,
            authentication_status=AuthenticationStatus.UNKNOWN,
            permission_status=PermissionStatus.UNKNOWN,
            connectivity_status=ConnectivityStatus.NOT_CHECKED,
            models=(
                [{"id": model_id, "source": "manual"}] if model_id else []
            ),
            capabilities={
                "model_discovery": False,
                "connectivity_test": False,
                "manual_setup": True,
            },
            details={"provider_id": provider_id},
            source="user",
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "providers": self._rows(
                "SELECT * FROM providers ORDER BY id",
                json_fields=("config_json",),
            ),
            "models": self._rows(
                "SELECT * FROM models ORDER BY id",
                json_fields=("capabilities_json", "metadata_json"),
            ),
            "agents": self._rows(
                "SELECT * FROM agent_profiles ORDER BY id",
                json_fields=(
                    "capabilities_json",
                    "boundaries_json",
                    "config_json",
                ),
            ),
            "roles": self._rows(
                "SELECT * FROM role_assignments ORDER BY role_key",
                json_fields=("constraints_json",),
            ),
            "settings": self._settings(),
            "discovery": self.discovery_records(),
        }

    def _settings(self) -> dict[str, dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                "SELECT key, value_json, source, updated_at FROM app_settings ORDER BY key"
            ).fetchall()
        return {
            row["key"]: {
                "value": json.loads(row["value_json"]),
                "source": row["source"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        }

    def _rows(
        self,
        query: str,
        json_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(query).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for field in json_fields:
                item[field.removesuffix("_json")] = json.loads(item.pop(field))
            for flag in ("enabled", "locked"):
                if flag in item:
                    item[flag] = bool(item[flag])
            result.append(item)
        return result

    @staticmethod
    def _exists(conn, table: str, record_id: str) -> bool:
        if table not in {"agent_profiles", "models", "providers"}:
            raise ValueError("unsupported registry table")
        row = conn.execute(
            f"SELECT 1 FROM {table} WHERE id = ?",
            (record_id,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _decode_discovery(row) -> dict[str, Any]:
        item = dict(row)
        for field in ("models_json", "capabilities_json", "details_json"):
            item[field.removesuffix("_json")] = json.loads(item.pop(field))
        return item

    @staticmethod
    def _upsert_role(
        conn,
        role_key: str,
        mode: str,
        agent_id: str | None,
        model_id: str | None,
        locked: bool,
        constraints: Any,
        source: str,
        now: str,
    ) -> None:
        if mode not in ROLE_MODES:
            raise ValueError(f"unsupported role mode {mode!r}")
        if mode == "manual" and not agent_id:
            raise ValueError("manual role assignment requires an agent")
        if locked and not agent_id:
            raise ValueError("locked role assignment requires an agent")
        conn.execute(
            """
            INSERT INTO role_assignments(
                role_key, mode, agent_id, model_id, locked,
                constraints_json, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(role_key) DO UPDATE SET
                mode = excluded.mode,
                agent_id = excluded.agent_id,
                model_id = excluded.model_id,
                locked = excluded.locked,
                constraints_json = excluded.constraints_json,
                source = excluded.source,
                updated_at = excluded.updated_at
            WHERE excluded.source = 'user' OR role_assignments.source != 'user'
            """,
            (
                role_key,
                mode,
                agent_id,
                model_id,
                int(locked),
                _dump(sanitize_for_storage(constraints)),
                source,
                now,
                now,
            ),
        )


def sanitize_for_storage(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            is_environment_reference = normalized.endswith(
                ("_env", "_env_var", "_environment_variable")
            )
            if not is_environment_reference and _is_sensitive_key(normalized):
                result[key] = "[REDACTED]"
            else:
                result[key] = sanitize_for_storage(item)
        return result
    if isinstance(value, list):
        return [sanitize_for_storage(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_storage(item) for item in value]
    return value


def _is_sensitive_key(normalized: str) -> bool:
    if any(
        part in normalized
        for part in SENSITIVE_KEY_PARTS - {"token"}
    ):
        return True
    token_metrics = (
        normalized == "tokens"
        or normalized == "token_source"
        or normalized == "token_sources"
        or normalized.endswith("_tokens")
        or normalized.endswith("_token_count")
        or normalized.endswith("_token_counts")
        or normalized.endswith("_token_source")
        or normalized.endswith("_token_sources")
    )
    return "token" in normalized and not token_metrics


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
