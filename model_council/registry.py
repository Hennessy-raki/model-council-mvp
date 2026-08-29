from __future__ import annotations

import json
from typing import Any

from .config import CouncilConfig
from .store import CouncilStore, utc_now
from .types import ProvenanceDisplayMode


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
        if table not in {"agent_profiles", "models"}:
            raise ValueError("unsupported registry table")
        row = conn.execute(
            f"SELECT 1 FROM {table} WHERE id = ?",
            (record_id,),
        ).fetchone()
        return row is not None

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
            if (
                not is_environment_reference
                and any(part in normalized for part in SENSITIVE_KEY_PARTS)
            ):
                result[key] = "[REDACTED]"
            else:
                result[key] = sanitize_for_storage(item)
        return result
    if isinstance(value, list):
        return [sanitize_for_storage(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_storage(item) for item in value]
    return value


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
