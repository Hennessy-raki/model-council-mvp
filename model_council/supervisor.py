from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from hashlib import sha256
from typing import Any, Protocol
from uuid import uuid4

from .registry import RegistryService, sanitize_for_storage
from .store import CouncilStore, utc_now


REQUIRED_ROLES = ("manager", "worker", "reviewer")
LAUNCH_MODES = {"spawn", "attach", "attach_or_spawn", "remote", "manual"}
TRANSPORTS = {"cli", "acp", "a2a", "mcp", "http", "manual"}
CHECK_NAMES = (
    "process",
    "login",
    "model",
    "permission",
    "version",
    "connection",
)
CANONICAL_LIFECYCLE_CHECKS = (
    "process",
    "login",
    "actual_model",
    "permission",
    "version",
    "protocol",
    "connectivity",
)
LIFECYCLE_STATES = {
    "configured",
    "starting",
    "started",
    "connecting",
    "connected",
    "attaching",
    "attached",
    "detaching",
    "detached",
    "stopping",
    "stopped",
    "failed",
    "user_confirmation_required",
}
LIFECYCLE_OPERATIONS = {"start", "connect", "attach", "detach", "stop"}
CHECK_STATUSES = {
    "passed",
    "failed",
    "user_confirmation_required",
    "not_applicable",
}
READY_STATUSES = {"ready", "not_ready", "user_confirmation_required"}
APPROVAL_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "stale",
    "consumed",
}
MAX_PROJECT_GOAL_BYTES = 64_000


class SupervisorError(ValueError):
    pass


class ReadinessInspector(Protocol):
    """Produces local, bounded readiness evidence for one Agent binding."""

    def inspect(self, binding: dict[str, Any]) -> dict[str, Any]:
        """Return a check-name keyed mapping of synthetic local observations."""


class AgentLifecycleFixture(Protocol):
    """Deterministic local lifecycle transition provider."""

    def transition(
        self,
        binding: dict[str, Any],
        operation: str,
        current_state: str,
        session: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a bounded status and optional reason/details."""


class StaticAgentLifecycleFixture:
    """Resolve lifecycle outcomes from a local, synthetic binding profile."""

    def transition(
        self,
        binding: dict[str, Any],
        operation: str,
        current_state: str,
        session: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile = binding.get("check_profile", {})
        lifecycle = profile.get("lifecycle", {}) if isinstance(profile, dict) else {}
        outcomes = lifecycle.get("operations", {}) if isinstance(lifecycle, dict) else {}
        outcome = outcomes.get(operation, {}) if isinstance(outcomes, dict) else {}
        if not isinstance(outcome, dict):
            outcome = {}
        status = str(outcome.get("status", "passed"))
        if status not in {"passed", "failed", "user_confirmation_required"}:
            return {
                "status": "failed",
                "code": "invalid_lifecycle_status",
                "details": {},
            }
        return {
            "status": status,
            "code": str(outcome.get("code", ""))[:120] or None,
            "details": sanitize_for_storage(
                outcome.get("details", {})
                if isinstance(outcome.get("details", {}), dict)
                else {}
            ),
        }


class SubprocessAgentLifecycleFixture:
    """Run one explicitly configured local fake process per role.

    This fixture is intentionally opt-in through dependency injection. It
    never uses a shell, never captures process output, and persists no process
    handle or machine-specific path.
    """

    def __init__(self, *, default_command: list[str] | None = None):
        self.default_command = list(default_command or [])
        self._processes: dict[str, subprocess.Popen] = {}
        self._attached: set[str] = set()

    def transition(
        self,
        binding: dict[str, Any],
        operation: str,
        current_state: str,
        session: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        role_key = binding["role_key"]
        process = self._processes.get(role_key)
        if operation == "start":
            if process is not None and process.poll() is None:
                return {
                    "status": "failed",
                    "code": "process_already_running",
                    "details": {},
                }
            command = self._command(binding)
            if not command:
                return {
                    "status": "failed",
                    "code": "fixture_command_missing",
                    "details": {},
                }
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=False,
                )
            except (OSError, ValueError):
                return {
                    "status": "failed",
                    "code": "fixture_process_start_failed",
                    "details": {},
                }
            self._processes[role_key] = process
            marker = sha256(
                f"{role_key}:{process.pid}".encode("utf-8")
            ).hexdigest()
            return {
                "status": "passed",
                "code": "fixture_process_started",
                "details": {
                    "process_marker": marker,
                    "command_sha256": sha256(
                        _dump(command).encode("utf-8")
                    ).hexdigest(),
                },
            }
        if operation in {"connect", "attach"}:
            if process is None:
                return {
                    "status": "failed",
                    "code": "fixture_process_missing",
                    "details": {},
                }
            if process.poll() is not None:
                return {
                    "status": "failed",
                    "code": "fixture_process_exited",
                    "details": {},
                }
            if operation == "attach":
                self._attached.add(role_key)
            return {
                "status": "passed",
                "code": f"fixture_{operation}_verified",
                "details": {
                    "attached": role_key in self._attached,
                },
            }
        if operation == "detach":
            if process is None or process.poll() is not None:
                return {
                    "status": "failed",
                    "code": "fixture_process_missing",
                    "details": {},
                }
            self._attached.discard(role_key)
            return {
                "status": "passed",
                "code": "fixture_detached",
                "details": {"attached": False},
            }
        if operation == "stop":
            if process is None:
                return {
                    "status": "failed",
                    "code": "fixture_process_missing",
                    "details": {},
                }
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        process.kill()
                        process.wait(timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        return {
                            "status": "failed",
                            "code": "fixture_process_stop_failed",
                            "details": {},
                        }
            self._attached.discard(role_key)
            self._processes.pop(role_key, None)
            return {
                "status": "passed",
                "code": "fixture_process_stopped",
                "details": {
                    "exit_code": process.returncode,
                },
            }
        return {
            "status": "failed",
            "code": "unsupported_lifecycle_operation",
            "details": {},
        }

    def _command(self, binding: dict[str, Any]) -> list[str]:
        profile = binding.get("check_profile", {})
        lifecycle = profile.get("lifecycle", {}) if isinstance(profile, dict) else {}
        command = lifecycle.get("command") if isinstance(lifecycle, dict) else None
        if command is None:
            command = self.default_command
        if not isinstance(command, list) or not command:
            return []
        if any(not isinstance(item, str) or not item for item in command):
            return []
        return list(command)


class StaticReadinessInspector:
    """Reads synthetic check results from a local team-wizard profile.

    This is deliberately not an Adapter or network client. It permits Board 13
    to exercise the Supervisor state machine with fake CLI/ACP/A2A/MCP/HTTP
    observations, while a real transport checker remains an explicit later
    authorization boundary.
    """

    def inspect(self, binding: dict[str, Any]) -> dict[str, Any]:
        profile = binding["check_profile"]
        checks = profile.get("synthetic_checks", {})
        return checks if isinstance(checks, dict) else {}


class LocalManagerPlatform:
    """A SQLite-backed stand-in for the first-stage Manager platform."""

    def __init__(self, store: CouncilStore):
        self.store = store

    def publish(
        self,
        *,
        event_type: str,
        manager_agent_id: str,
        snapshot_id: str | None,
        approval_id: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        event_id = str(uuid4())
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO supervisor_platform_events(
                    id, event_type, manager_agent_id, snapshot_id, approval_id,
                    payload_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'delivered', ?)
                """,
                (
                    event_id,
                    event_type,
                    manager_agent_id,
                    snapshot_id,
                    approval_id,
                    _dump(sanitize_for_storage(payload)),
                    now,
                ),
            )
        return self.event(event_id)

    def event(self, event_id: str) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM supervisor_platform_events WHERE id = ?",
                (event_id,),
            ).fetchone()
        if row is None:
            raise SupervisorError(f"manager-platform event {event_id!r} not found")
        return _decode_event(row)

    def events(self) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM supervisor_platform_events
                ORDER BY created_at, id
                """
            ).fetchall()
        return [_decode_event(row) for row in rows]


class SupervisorService:
    """Durable local team-readiness and start-approval control plane."""

    def __init__(
        self,
        store: CouncilStore,
        registry: RegistryService,
        *,
        inspector: ReadinessInspector | None = None,
        lifecycle: AgentLifecycleFixture | None = None,
        platform: LocalManagerPlatform | None = None,
        allow_synthetic_fixture_for_tests: bool = False,
    ):
        self.store = store
        self.registry = registry
        self.inspector = inspector or StaticReadinessInspector()
        self.lifecycle = lifecycle or StaticAgentLifecycleFixture()
        self.platform = platform or LocalManagerPlatform(store)
        self.allow_synthetic_fixture_for_tests = allow_synthetic_fixture_for_tests

    def lifecycle_session(self, role_key: str) -> dict[str, Any] | None:
        self._validate_role(role_key)
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM supervisor_agent_sessions WHERE role_key = ?",
                (role_key,),
            ).fetchone()
        return _decode_lifecycle_session(row) if row is not None else None

    def lifecycle_sessions(self) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM supervisor_agent_sessions
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        return [_decode_lifecycle_session(row) for row in rows]

    def lifecycle_events(self, role_key: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT e.*, s.role_key
            FROM supervisor_agent_events e
            JOIN supervisor_agent_sessions s ON s.id = e.session_id
        """
        params: tuple[Any, ...] = ()
        if role_key is not None:
            self._validate_role(role_key)
            query += " WHERE s.role_key = ?"
            params = (role_key,)
        query += " ORDER BY e.created_at, e.id"
        with self.store.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_decode_lifecycle_event(row) for row in rows]

    def qualification_preflight(self, role_key: str) -> dict[str, Any] | None:
        self._validate_role(role_key)
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM supervisor_qualification_preflights
                WHERE role_key = ?
                """,
                (role_key,),
            ).fetchone()
        return _decode_qualification_preflight(row) if row is not None else None

    def qualification_preflights(self) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM supervisor_qualification_preflights
                ORDER BY role_key
                """
            ).fetchall()
        return [_decode_qualification_preflight(row) for row in rows]

    def bind_qualification_preflight(
        self,
        role_key: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Bind one eligible Board 21 result to a configured role."""
        self._validate_role(role_key)
        if not isinstance(result, dict):
            raise SupervisorError("qualification preflight result must be an object")
        if result.get("status") != "eligible_for_separate_review":
            raise SupervisorError("only an eligible qualification preflight can be bound")
        if result.get("execution_authorized") is not False:
            raise SupervisorError("qualification preflight cannot authorize execution")
        scope = result.get("normalized_scope")
        scope_sha256 = result.get("scope_sha256")
        if not isinstance(scope, dict) or not isinstance(scope_sha256, str):
            raise SupervisorError("qualification preflight scope is incomplete")
        if _digest(scope) != scope_sha256:
            raise SupervisorError("qualification preflight scope digest is invalid")
        if scope.get("kind") != "offline_agent_qualification_preflight":
            raise SupervisorError("unsupported qualification preflight scope")
        identity = scope.get("identity")
        if not isinstance(identity, dict):
            raise SupervisorError("qualification preflight identity is missing")
        binding = self.binding(role_key)
        expected = {
            "agent_id": binding["agent_id"],
            "model_id": binding["model_id"],
        }
        if identity.get("agent_id") != expected["agent_id"] or identity.get(
            "model_id"
        ) != expected["model_id"]:
            raise SupervisorError("qualification preflight identity does not match role")
        provider_id = identity.get("provider_id")
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT provider_id FROM agent_profiles WHERE id = ?",
                (binding["agent_id"],),
            ).fetchone()
        if row is None or provider_id != row["provider_id"]:
            raise SupervisorError(
                "qualification preflight Provider does not match role Agent"
            )
        now = utc_now()
        preflight_id = str(uuid4())
        with self.store.connect() as conn:
            previous = conn.execute(
                """
                SELECT scope_sha256 FROM supervisor_qualification_preflights
                WHERE role_key = ?
                """,
                (role_key,),
            ).fetchone()
            if previous is not None and previous["scope_sha256"] != scope_sha256:
                self._mark_pending_approvals_stale(
                    conn,
                    failure="qualification preflight changed after approval",
                )
            conn.execute(
                """
                INSERT INTO supervisor_qualification_preflights(
                    id, role_key, agent_id, model_id, provider_id, scope_sha256,
                    scope_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'current', ?, ?)
                ON CONFLICT(role_key) DO UPDATE SET
                    id = excluded.id,
                    agent_id = excluded.agent_id,
                    model_id = excluded.model_id,
                    provider_id = excluded.provider_id,
                    scope_sha256 = excluded.scope_sha256,
                    scope_json = excluded.scope_json,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    preflight_id,
                    role_key,
                    identity["agent_id"],
                    identity["model_id"],
                    provider_id,
                    scope_sha256,
                    _dump(sanitize_for_storage(scope)),
                    now,
                    now,
                ),
            )
        return self.qualification_preflight(role_key)

    def transition_agent(self, role_key: str, operation: str) -> dict[str, Any]:
        """Run one deterministic local lifecycle transition."""
        self._validate_role(role_key)
        if operation not in LIFECYCLE_OPERATIONS:
            raise SupervisorError(f"unsupported Agent lifecycle operation {operation!r}")
        binding = self.binding(role_key)
        current = self.lifecycle_session(role_key)
        current_state = current["state"] if current else "configured"
        next_state = _next_lifecycle_state(
            operation,
            current_state,
            binding["launch_mode"],
            binding["transport"],
        )
        outcome = self.lifecycle.transition(
            binding,
            operation,
            current_state,
            session=current,
        )
        status = outcome.get("status")
        if status == "failed":
            next_state = "failed"
        elif status == "user_confirmation_required":
            next_state = "user_confirmation_required"
        elif next_state is None:
            raise SupervisorError(
                f"lifecycle operation {operation!r} is invalid from state {current_state!r}"
            )
        now = utc_now()
        evidence = {
            "operation": operation,
            "status": status,
            "code": outcome.get("code"),
            "details": sanitize_for_storage(outcome.get("details", {})),
            "role_key": role_key,
            "agent_id": binding["agent_id"],
            "model_id": binding["model_id"],
            "launch_mode": binding["launch_mode"],
            "transport": binding["transport"],
        }
        evidence_sha256 = _digest(evidence)
        session_id = current["id"] if current else str(uuid4())
        with self.store.connect() as conn:
            if current is None:
                conn.execute(
                    """
                    INSERT INTO supervisor_agent_sessions(
                        id, role_key, agent_id, model_id, launch_mode, transport,
                        state, evidence_json, evidence_sha256, failure,
                        created_at, updated_at, detached_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        session_id,
                        role_key,
                        binding["agent_id"],
                        binding["model_id"],
                        binding["launch_mode"],
                        binding["transport"],
                        next_state,
                        _dump(evidence),
                        evidence_sha256,
                        evidence.get("code") if status != "passed" else None,
                        now,
                        now,
                    ),
                )
            else:
                updated = conn.execute(
                    """
                    UPDATE supervisor_agent_sessions
                    SET state = ?, evidence_json = ?, evidence_sha256 = ?,
                        failure = ?, updated_at = ?, detached_at = ?
                    WHERE id = ? AND state = ?
                    """,
                    (
                        next_state,
                        _dump(evidence),
                        evidence_sha256,
                        evidence.get("code") if status != "passed" else None,
                        now,
                        now if next_state in {"detached", "stopped"} else current["detached_at"],
                        session_id,
                        current_state,
                    ),
                ).rowcount
                if not updated:
                    raise SupervisorError(
                        f"Agent lifecycle session for {role_key!r} changed before transition"
                    )
            event_id = str(uuid4())
            conn.execute(
                """
                INSERT INTO supervisor_agent_events(
                    id, session_id, event_type, from_state, to_state,
                    payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    session_id,
                    f"agent_{operation}",
                    current_state,
                    next_state,
                    _dump(evidence),
                    now,
                ),
            )
        return {
            "session": self.lifecycle_session(role_key),
            "event": self.lifecycle_events(role_key)[-1],
        }

    def start_agent(self, role_key: str) -> dict[str, Any]:
        return self.transition_agent(role_key, "start")

    def connect_agent(self, role_key: str) -> dict[str, Any]:
        return self.transition_agent(role_key, "connect")

    def attach_agent(self, role_key: str) -> dict[str, Any]:
        return self.transition_agent(role_key, "attach")

    def detach_agent(self, role_key: str) -> dict[str, Any]:
        return self.transition_agent(role_key, "detach")

    def stop_agent(self, role_key: str) -> dict[str, Any]:
        return self.transition_agent(role_key, "stop")

    def configure_role(
        self,
        *,
        role_key: str,
        agent_id: str,
        model_id: str,
        launch_mode: str,
        transport: str,
        check_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._validate_role(role_key)
        self._validate_binding_input(
            agent_id=agent_id,
            model_id=model_id,
            launch_mode=launch_mode,
            transport=transport,
            check_profile=check_profile or {},
        )
        self._require_agent_model_binding(agent_id, model_id)
        profile = sanitize_for_storage(check_profile or {})
        binding_payload = {
            "role_key": role_key,
            "agent_id": agent_id,
            "model_id": model_id,
            "launch_mode": launch_mode,
            "transport": transport,
            "check_profile": profile,
        }
        binding_sha256 = _digest(binding_payload)
        now = utc_now()
        with self.store.connect() as conn:
            previous = conn.execute(
                """
                SELECT binding_sha256 FROM supervisor_team_bindings
                WHERE role_key = ?
                """,
                (role_key,),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO supervisor_team_bindings(
                    role_key, agent_id, model_id, launch_mode, transport,
                    check_profile_json, binding_sha256, source, created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'user', ?, ?)
                ON CONFLICT(role_key) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    model_id = excluded.model_id,
                    launch_mode = excluded.launch_mode,
                    transport = excluded.transport,
                    check_profile_json = excluded.check_profile_json,
                    binding_sha256 = excluded.binding_sha256,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (
                    role_key,
                    agent_id,
                    model_id,
                    launch_mode,
                    transport,
                    _dump(profile),
                    binding_sha256,
                    now,
                    now,
                ),
            )
            if previous is not None and previous["binding_sha256"] != binding_sha256:
                self._mark_pending_approvals_stale(
                    conn,
                    failure="team configuration changed after start request",
                )
                conn.execute(
                    """
                    UPDATE supervisor_qualification_preflights
                    SET status = 'stale', updated_at = ?
                    WHERE role_key = ?
                    """,
                    (now, role_key),
                )
                conn.execute(
                    """
                    UPDATE supervisor_agent_sessions
                    SET agent_id = ?, model_id = ?, launch_mode = ?, transport = ?,
                        state = 'configured', evidence_json = ?, evidence_sha256 = ?,
                        failure = 'binding_changed', updated_at = ?,
                        detached_at = NULL
                    WHERE role_key = ?
                    """,
                    (
                        agent_id,
                        model_id,
                        launch_mode,
                        transport,
                        _dump({}),
                        _digest({}),
                        now,
                        role_key,
                    ),
                )
        return self.binding(role_key)

    def apply_wizard(self, team: dict[str, Any]) -> list[dict[str, Any]]:
        roles = team.get("roles")
        if not isinstance(roles, dict):
            raise SupervisorError("team wizard input requires a roles object")
        missing = set(REQUIRED_ROLES) - set(roles)
        extra = set(roles) - set(REQUIRED_ROLES)
        if missing or extra:
            raise SupervisorError(
                "team wizard roles must be exactly manager, worker and reviewer"
            )
        result = []
        for role_key in REQUIRED_ROLES:
            item = roles[role_key]
            if not isinstance(item, dict):
                raise SupervisorError(f"wizard role {role_key!r} must be an object")
            result.append(
                self.configure_role(
                    role_key=role_key,
                    agent_id=str(item.get("agent_id", "")),
                    model_id=str(item.get("model_id", "")),
                    launch_mode=str(item.get("launch_mode", "")),
                    transport=str(item.get("transport", "")),
                    check_profile=item.get("check_profile", {}),
                )
            )
        return result

    def bindings(self) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM supervisor_team_bindings
                ORDER BY CASE role_key
                    WHEN 'manager' THEN 1
                    WHEN 'worker' THEN 2
                    WHEN 'reviewer' THEN 3
                    ELSE 4
                END
                """
            ).fetchall()
        return [_decode_binding(row) for row in rows]

    def binding(self, role_key: str) -> dict[str, Any]:
        self._validate_role(role_key)
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM supervisor_team_bindings WHERE role_key = ?",
                (role_key,),
            ).fetchone()
        if row is None:
            raise SupervisorError(f"required team role {role_key!r} is not configured")
        return _decode_binding(row)

    def check_team(self) -> dict[str, Any]:
        reports = []
        for binding in self.bindings():
            reports.append(self.check_role(binding["role_key"]))
        present = {item["role_key"] for item in reports}
        for role_key in REQUIRED_ROLES:
            if role_key not in present:
                reports.append(
                    {
                        "role_key": role_key,
                        "status": "not_ready",
                        "errors": [
                            {
                                "check": "configuration",
                                "code": "role_not_configured",
                                "suggestion": (
                                    "Complete the local team wizard with an "
                                    "Agent and Model binding."
                                ),
                            }
                        ],
                    }
                )
        reports.sort(key=lambda item: REQUIRED_ROLES.index(item["role_key"]))
        statuses = {item["status"] for item in reports}
        status = (
            "not_ready"
            if "not_ready" in statuses
            else (
                "user_confirmation_required"
                if "user_confirmation_required" in statuses
                else "ready"
            )
        )
        return {"status": status, "agents": reports}

    def check_role(self, role_key: str) -> dict[str, Any]:
        binding = self.binding(role_key)
        observed = self.inspector.inspect(binding)
        if not isinstance(observed, dict):
            observed = {}
        checks: dict[str, dict[str, Any]] = {}
        confirmations = self._current_confirmations(binding)
        for check_name in CHECK_NAMES:
            item = observed.get(check_name)
            if check_name == "model" and item is None:
                item = observed.get("actual_model")
            if check_name == "connection" and item is None:
                item = observed.get("connectivity")
            check = self._normalize_check(check_name, item)
            if (
                check_name == "model"
                and check["status"] == "passed"
                and check["details"].get("model_id") != binding["model_id"]
            ):
                check = {
                    "status": "failed",
                    "code": "bound_model_not_observed",
                    "details": {
                        "expected_model_id": binding["model_id"],
                        "observed_model_id": check["details"].get("model_id"),
                    },
                }
            if (
                check["status"] == "user_confirmation_required"
                and check_name in confirmations
            ):
                check = {
                    "status": "passed",
                    "source": "user_confirmation",
                    "details": {
                        "confirmation_id": confirmations[check_name]["id"],
                    },
                }
            checks[check_name] = check

        session = self.lifecycle_session(role_key)
        lifecycle_profile = binding.get("check_profile", {}).get("lifecycle", {})
        if isinstance(lifecycle_profile, dict) and lifecycle_profile:
            lifecycle_checks = lifecycle_profile.get("checks", {})
            if isinstance(lifecycle_checks, dict):
                for check_name in ("process", "login", "actual_model", "permission",
                                   "version", "protocol", "connectivity"):
                    item = lifecycle_checks.get(check_name)
                    if item is None and check_name == "actual_model":
                        item = lifecycle_checks.get("model")
                    if item is None and check_name == "connectivity":
                        item = lifecycle_checks.get("connection")
                    if item is None and check_name == "protocol":
                        item = {
                            "status": "passed",
                            "details": {"transport": binding["transport"]},
                        }
                    if item is None:
                        fallback_name = {
                            "actual_model": "model",
                            "connectivity": "connection",
                        }.get(check_name, check_name)
                        item = observed.get(fallback_name)
                    checks[check_name] = self._normalize_lifecycle_check(
                        check_name, item, binding
                    )
        else:
            checks["actual_model"] = checks["model"]
            checks["connectivity"] = checks["connection"]
            checks["protocol"] = {
                "status": "not_applicable",
                "details": {},
            }

        if self._qualification_required(binding):
            preflight = self.qualification_preflight(role_key)
            if (
                preflight is None
                or preflight["status"] != "current"
                or preflight["agent_id"] != binding["agent_id"]
                or preflight["model_id"] != binding["model_id"]
            ):
                checks["qualification_preflight"] = {
                    "status": "failed",
                    "code": "qualification_preflight_required",
                    "details": {},
                }
            else:
                checks["qualification_preflight"] = {
                    "status": "passed",
                    "source": "qualification_preflight",
                    "details": {
                        "preflight_id": preflight["id"],
                        "scope_sha256": preflight["scope_sha256"],
                    },
                }

        if session is not None:
            if session["state"] in {"failed", "user_confirmation_required"}:
                checks["process"] = {
                    "status": session["state"],
                    "code": session.get("failure") or "lifecycle_transition_failed",
                    "details": {"session_id": session["id"]},
                }
            elif session["state"] in {"detached", "stopped"}:
                checks["process"] = {
                    "status": "failed",
                    "code": f"agent_{session['state']}",
                    "details": {"session_id": session["id"], "state": session["state"]},
                }
            elif session["state"] in {
                "started",
                "connecting",
                "connected",
                "attaching",
                "attached",
                "detaching",
                "stopping",
            }:
                checks["process"] = {
                    "status": "passed",
                    "source": "lifecycle_session",
                    "details": {"session_id": session["id"], "state": session["state"]},
                }
            checks["lifecycle"] = {
                "status": "passed"
                if session["state"] not in {"failed", "user_confirmation_required"}
                else session["state"],
                "details": {
                    "session_id": session["id"],
                    "state": session["state"],
                    "evidence_sha256": session["evidence_sha256"],
                },
            }

        error_names = list(CANONICAL_LIFECYCLE_CHECKS)
        if self._qualification_required(binding):
            error_names.append("qualification_preflight")
        errors = [
            {
                "check": name,
                "code": checks[name].get("code", checks[name]["status"]),
                "suggestion": _suggestion(name, checks[name]["status"], binding),
            }
            for name in error_names
            if name in checks
            if checks[name]["status"]
            in {"failed", "user_confirmation_required"}
        ]
        statuses = {checks[name]["status"] for name in error_names if name in checks}
        status = (
            "not_ready"
            if "failed" in statuses
            else (
                "user_confirmation_required"
                if "user_confirmation_required" in statuses
                else "ready"
            )
        )
        report = {
            "role_key": role_key,
            "agent_id": binding["agent_id"],
            "model_id": binding["model_id"],
            "launch_mode": binding["launch_mode"],
            "transport": binding["transport"],
            "binding_sha256": binding["binding_sha256"],
            "status": status,
            "checks": checks,
            "errors": errors,
        }
        report_id = str(uuid4())
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO supervisor_readiness_reports(
                    id, role_key, binding_sha256, status, report_json, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    role_key,
                    binding["binding_sha256"],
                    status,
                    _dump(sanitize_for_storage(report)),
                    now,
                ),
            )
        report["id"] = report_id
        report["checked_at"] = now
        return report

    def confirm(
        self,
        *,
        role_key: str,
        check_names: list[str],
        note: str = "",
    ) -> list[dict[str, Any]]:
        binding = self.binding(role_key)
        if not check_names:
            raise SupervisorError("choose at least one readiness check to confirm")
        unsupported = set(check_names) - (
            set(CHECK_NAMES) | set(CANONICAL_LIFECYCLE_CHECKS)
        )
        if unsupported:
            raise SupervisorError(f"unsupported readiness checks: {sorted(unsupported)}")
        current = self._latest_current_report(binding)
        if current is None:
            raise SupervisorError(
                "run the local readiness check before recording confirmation"
            )
        result = []
        with self.store.connect() as conn:
            for check_name in check_names:
                if check_name == "actual_model":
                    source_name = "actual_model"
                elif check_name == "connectivity":
                    source_name = "connectivity"
                else:
                    source_name = check_name
                check = current["report"]["checks"].get(source_name)
                if check is None:
                    raise SupervisorError(
                        f"{role_key} {check_name} evidence is unavailable"
                    )
                if check["status"] != "user_confirmation_required":
                    raise SupervisorError(
                        f"{role_key} {check_name} is not awaiting user confirmation"
                    )
                confirmation_id = str(uuid4())
                now = utc_now()
                conn.execute(
                    """
                    INSERT INTO supervisor_user_confirmations(
                        id, role_key, binding_sha256, check_name, note,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        confirmation_id,
                        role_key,
                        binding["binding_sha256"],
                        check_name,
                        _bounded_note(note),
                        now,
                    ),
                )
                result.append(
                    {
                        "id": confirmation_id,
                        "role_key": role_key,
                        "check_name": check_name,
                        "created_at": now,
                    }
                )
        return result

    def snapshot(self) -> dict[str, Any]:
        team = self._current_ready_team()
        payload = {
            "version": 1,
            "roles": [
                {
                    "role_key": item["binding"]["role_key"],
                    "agent_id": item["binding"]["agent_id"],
                    "model_id": item["binding"]["model_id"],
                    "launch_mode": item["binding"]["launch_mode"],
                    "transport": item["binding"]["transport"],
                    "binding_sha256": item["binding"]["binding_sha256"],
                    "readiness_report_id": item["report"]["id"],
                    "checks": item["report"]["report"]["checks"],
                    "lifecycle_session_id": (
                        self.lifecycle_session(item["binding"]["role_key"]) or {}
                    ).get("id"),
                    "lifecycle_evidence_sha256": (
                        self.lifecycle_session(item["binding"]["role_key"]) or {}
                    ).get("evidence_sha256"),
                    "qualification_preflight_id": (
                        self.qualification_preflight(
                            item["binding"]["role_key"]
                        )
                        or {}
                    ).get("id"),
                    "qualification_preflight_sha256": (
                        self.qualification_preflight(
                            item["binding"]["role_key"]
                        )
                        or {}
                    ).get("scope_sha256"),
                }
                for item in team
            ],
        }
        snapshot_id = str(uuid4())
        snapshot_sha256 = _digest(payload)
        now = utc_now()
        manager_agent_id = next(
            item["binding"]["agent_id"]
            for item in team
            if item["binding"]["role_key"] == "manager"
        )
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO supervisor_team_snapshots(
                    id, snapshot_sha256, payload_json, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (snapshot_id, snapshot_sha256, _dump(payload), now),
            )
        snapshot = self.snapshot_record(snapshot_id)
        self.platform.publish(
            event_type="team_ready",
            manager_agent_id=manager_agent_id,
            snapshot_id=snapshot_id,
            approval_id=None,
            payload={
                "snapshot_sha256": snapshot_sha256,
                "roles": [
                    {
                        "role_key": item["role_key"],
                        "agent_id": item["agent_id"],
                        "model_id": item["model_id"],
                    }
                    for item in payload["roles"]
                ],
            },
        )
        return snapshot

    def snapshots(self) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM supervisor_team_snapshots
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [_decode_snapshot(row) for row in rows]

    def snapshot_record(self, snapshot_id: str) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM supervisor_team_snapshots WHERE id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise SupervisorError(f"team snapshot {snapshot_id!r} not found")
        return _decode_snapshot(row)

    def validate_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """Return one snapshot only when its bindings and evidence are current."""
        snapshot = self.snapshot_record(snapshot_id)
        self._require_current_snapshot(snapshot)
        return snapshot

    def request_start(self, snapshot_id: str) -> dict[str, Any]:
        snapshot = self.validate_snapshot(snapshot_id)
        scope = {
            "version": 1,
            "action": "start_synthetic_team_task",
            "snapshot_id": snapshot["id"],
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "roles": snapshot["payload"]["roles"],
            "execution_boundary": (
                "Local fake Manager platform only; no Adapter, model, network, "
                "workspace, Git or task execution is invoked by Board 13."
            ),
        }
        approval_id = str(uuid4())
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO supervisor_start_approvals(
                    id, snapshot_id, scope_sha256, scope_json, status,
                    requested_at, decided_at, consumed_at, failure
                ) VALUES (?, ?, ?, ?, 'pending', ?, NULL, NULL, NULL)
                """,
                (approval_id, snapshot_id, _digest(scope), _dump(scope), now),
            )
        approval = self.approval(approval_id)
        manager = self.binding("manager")
        self.platform.publish(
            event_type="task_start_requested",
            manager_agent_id=manager["agent_id"],
            snapshot_id=snapshot_id,
            approval_id=approval_id,
            payload={
                "scope_sha256": approval["scope_sha256"],
                "snapshot_sha256": snapshot["snapshot_sha256"],
            },
        )
        return approval

    def request_project_run(self, snapshot_id: str, goal: str) -> dict[str, Any]:
        """Queue an exact, user-visible project-run authorization.

        This approval is distinct from the Board 13 synthetic Manager-platform
        start request. It binds the current ready team to the exact project
        goal, but does not invoke an Adapter or start a process.
        """
        snapshot = self.validate_snapshot(snapshot_id)
        normalized_goal = _bounded_project_goal(goal)
        scope = {
            "version": 1,
            "action": "start_project_run",
            "goal": normalized_goal,
            "goal_sha256": sha256(
                normalized_goal.encode("utf-8")
            ).hexdigest(),
            "snapshot_id": snapshot["id"],
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "roles": snapshot["payload"]["roles"],
            "execution_boundary": (
                "Local orchestrator run after one exact approval; the goal and "
                "current team snapshot must remain unchanged."
            ),
        }
        approval_id = str(uuid4())
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO supervisor_start_approvals(
                    id, snapshot_id, scope_sha256, scope_json, status,
                    requested_at, decided_at, consumed_at, failure
                ) VALUES (?, ?, ?, ?, 'pending', ?, NULL, NULL, NULL)
                """,
                (approval_id, snapshot_id, _digest(scope), _dump(scope), now),
            )
        approval = self.approval(approval_id)
        manager = self.binding("manager")
        self.platform.publish(
            event_type="project_run_start_requested",
            manager_agent_id=manager["agent_id"],
            snapshot_id=snapshot_id,
            approval_id=approval_id,
            payload={
                "scope_sha256": approval["scope_sha256"],
                "snapshot_sha256": snapshot["snapshot_sha256"],
                "goal_sha256": scope["goal_sha256"],
            },
        )
        return approval

    def approval(self, approval_id: str) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM supervisor_start_approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
        if row is None:
            raise SupervisorError(f"team start approval {approval_id!r} not found")
        return _decode_approval(row)

    def approvals(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is not None and status not in APPROVAL_STATUSES:
            raise SupervisorError(f"unsupported team start approval status {status!r}")
        query = "SELECT * FROM supervisor_start_approvals"
        params: tuple[Any, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY requested_at DESC, id DESC"
        with self.store.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_decode_approval(row) for row in rows]

    def decide_start(
        self,
        approval_id: str,
        *,
        approve: bool,
        confirmation: str = "",
    ) -> dict[str, Any]:
        approval = self.approval(approval_id)
        if approval["status"] != "pending":
            raise SupervisorError(f"team start approval {approval_id!r} is not pending")
        if approve and confirmation != approval["scope_sha256"]:
            raise SupervisorError(
                "start approval confirmation must exactly match the displayed "
                "scope SHA-256"
            )
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE supervisor_start_approvals
                SET status = ?, decided_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                ("approved" if approve else "rejected", utc_now(), approval_id),
            ).rowcount
        if not updated:
            raise SupervisorError(
                f"team start approval {approval_id!r} changed before decision"
            )
        return self.approval(approval_id)

    def start(self, approval_id: str) -> dict[str, Any]:
        approval = self.approval(approval_id)
        if approval["status"] != "approved" or approval["consumed_at"] is not None:
            raise SupervisorError(
                f"team start approval {approval_id!r} is not approved and unused"
            )
        snapshot = self.snapshot_record(approval["snapshot_id"])
        try:
            self._require_current_snapshot(snapshot)
        except SupervisorError:
            with self.store.connect() as conn:
                conn.execute(
                    """
                    UPDATE supervisor_start_approvals
                    SET status = 'stale', failure = ?
                    WHERE id = ? AND status = 'approved' AND consumed_at IS NULL
                    """,
                    ("team configuration or readiness changed after approval", approval_id),
                )
            raise SupervisorError("team start approval is stale")
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE supervisor_start_approvals
                SET status = 'consumed', consumed_at = ?
                WHERE id = ? AND status = 'approved' AND consumed_at IS NULL
                """,
                (utc_now(), approval_id),
            ).rowcount
        if not updated:
            raise SupervisorError(
                f"team start approval {approval_id!r} changed before start"
            )
        manager = self.binding("manager")
        event = self.platform.publish(
            event_type="task_start_authorized",
            manager_agent_id=manager["agent_id"],
            snapshot_id=snapshot["id"],
            approval_id=approval_id,
            payload={
                "scope_sha256": approval["scope_sha256"],
                "snapshot_sha256": snapshot["snapshot_sha256"],
                "execution": "synthetic_manager_platform",
            },
        )
        return {"approval": self.approval(approval_id), "event": event}

    def start_project_run(self, approval_id: str, goal: str) -> dict[str, Any]:
        """Consume one approved project-run scope after revalidation."""
        approval = self.approval(approval_id)
        if approval["status"] != "approved" or approval["consumed_at"] is not None:
            raise SupervisorError(
                f"project run approval {approval_id!r} is not approved and unused"
            )
        scope = approval["scope"]
        if scope.get("action") != "start_project_run":
            raise SupervisorError(
                "approval is for the local synthetic platform, not a project run"
            )
        normalized_goal = _bounded_project_goal(goal)
        if scope.get("goal") != normalized_goal:
            raise SupervisorError("project run goal differs from approved scope")
        try:
            snapshot = self.snapshot_record(approval["snapshot_id"])
            self._require_current_snapshot(snapshot)
        except SupervisorError:
            with self.store.connect() as conn:
                conn.execute(
                    """
                    UPDATE supervisor_start_approvals
                    SET status = 'stale', failure = ?
                    WHERE id = ? AND status = 'approved' AND consumed_at IS NULL
                    """,
                    (
                        "team configuration or readiness changed after approval",
                        approval_id,
                    ),
                )
            raise SupervisorError("project run approval is stale")
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE supervisor_start_approvals
                SET status = 'consumed', consumed_at = ?
                WHERE id = ? AND status = 'approved' AND consumed_at IS NULL
                """,
                (utc_now(), approval_id),
            ).rowcount
        if not updated:
            raise SupervisorError(
                f"project run approval {approval_id!r} changed before start"
            )
        manager = self.binding("manager")
        event = self.platform.publish(
            event_type="project_run_start_authorized",
            manager_agent_id=manager["agent_id"],
            snapshot_id=snapshot["id"],
            approval_id=approval_id,
            payload={
                "scope_sha256": approval["scope_sha256"],
                "snapshot_sha256": snapshot["snapshot_sha256"],
                "goal_sha256": scope["goal_sha256"],
                "execution": "orchestrator",
            },
        )
        return {
            "approval": self.approval(approval_id),
            "event": event,
            "snapshot": snapshot,
            "scope": scope,
        }

    def events(self) -> list[dict[str, Any]]:
        return self.platform.events()

    def _current_ready_team(self) -> list[dict[str, Any]]:
        bindings = {item["role_key"]: item for item in self.bindings()}
        if set(bindings) != set(REQUIRED_ROLES):
            raise SupervisorError(
                "all required Agent bindings must be configured before snapshot"
            )
        result = []
        for role_key in REQUIRED_ROLES:
            binding = bindings[role_key]
            report = self._latest_current_report(binding)
            if report is None or report["status"] != "ready":
                raise SupervisorError(
                    f"{role_key} is not ready; run local team checks and resolve "
                    "all failures or requested confirmations"
                )
            result.append({"binding": binding, "report": report})
        return result

    def _require_current_snapshot(self, snapshot: dict[str, Any]) -> None:
        expected = self._current_snapshot_payload()
        if _digest(expected) != snapshot["snapshot_sha256"]:
            raise SupervisorError("team snapshot is stale")

    def _current_snapshot_payload(self) -> dict[str, Any]:
        team = self._current_ready_team()
        return {
            "version": 1,
            "roles": [
                {
                    "role_key": item["binding"]["role_key"],
                    "agent_id": item["binding"]["agent_id"],
                    "model_id": item["binding"]["model_id"],
                    "launch_mode": item["binding"]["launch_mode"],
                    "transport": item["binding"]["transport"],
                    "binding_sha256": item["binding"]["binding_sha256"],
                    "readiness_report_id": item["report"]["id"],
                    "checks": item["report"]["report"]["checks"],
                    "lifecycle_session_id": (
                        self.lifecycle_session(item["binding"]["role_key"]) or {}
                    ).get("id"),
                    "lifecycle_evidence_sha256": (
                        self.lifecycle_session(item["binding"]["role_key"]) or {}
                    ).get("evidence_sha256"),
                    "qualification_preflight_id": (
                        self.qualification_preflight(
                            item["binding"]["role_key"]
                        )
                        or {}
                    ).get("id"),
                    "qualification_preflight_sha256": (
                        self.qualification_preflight(
                            item["binding"]["role_key"]
                        )
                        or {}
                    ).get("scope_sha256"),
                }
                for item in team
            ],
        }

    def _latest_current_report(
        self,
        binding: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM supervisor_readiness_reports
                WHERE role_key = ? AND binding_sha256 = ?
                ORDER BY checked_at DESC, id DESC LIMIT 1
                """,
                (binding["role_key"], binding["binding_sha256"]),
            ).fetchone()
        return _decode_report(row) if row is not None else None

    def _current_confirmations(
        self,
        binding: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM supervisor_user_confirmations
                WHERE role_key = ? AND binding_sha256 = ?
                ORDER BY created_at DESC, id DESC
                """,
                (binding["role_key"], binding["binding_sha256"]),
            ).fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = dict(row)
            result.setdefault(item["check_name"], item)
        return result

    def _normalize_check(
        self,
        check_name: str,
        value: Any,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {
                "status": "user_confirmation_required",
                "code": "machine_evidence_unavailable",
                "details": {},
            }
        status = str(value.get("status", "user_confirmation_required"))
        if status not in CHECK_STATUSES:
            return {
                "status": "failed",
                "code": "invalid_check_status",
                "details": {},
            }
        details = value.get("details", {})
        if not isinstance(details, dict):
            details = {}
        result = {
            "status": status,
            "details": sanitize_for_storage(details),
        }
        if "code" in value:
            result["code"] = str(value["code"])[:120]
        if check_name == "model" and status == "passed":
            observed_model = details.get("model_id")
            if observed_model is not None and not isinstance(observed_model, str):
                result["status"] = "failed"
                result["code"] = "invalid_observed_model"
        return result

    def _normalize_lifecycle_check(
        self,
        check_name: str,
        value: Any,
        binding: dict[str, Any],
    ) -> dict[str, Any]:
        if check_name == "actual_model":
            result = self._normalize_check("model", value)
            if (
                result["status"] == "passed"
                and result["details"].get("model_id") != binding["model_id"]
            ):
                return {
                    "status": "failed",
                    "code": "bound_model_not_observed",
                    "details": {
                        "expected_model_id": binding["model_id"],
                        "observed_model_id": result["details"].get("model_id"),
                    },
                }
            return result
        return self._normalize_check(
            "connection" if check_name == "connectivity" else check_name,
            value,
        )

    def _require_agent_model_binding(self, agent_id: str, model_id: str) -> None:
        with self.store.connect() as conn:
            agent = conn.execute(
                """
                SELECT id, model_id, enabled FROM agent_profiles WHERE id = ?
                """,
                (agent_id,),
            ).fetchone()
            model = conn.execute(
                "SELECT id, enabled FROM models WHERE id = ?",
                (model_id,),
            ).fetchone()
        if agent is None:
            raise SupervisorError(f"unknown Agent {agent_id!r}")
        if model is None:
            raise SupervisorError(f"unknown Model {model_id!r}")
        if not bool(agent["enabled"]):
            raise SupervisorError(f"Agent {agent_id!r} is disabled")
        if not bool(model["enabled"]):
            raise SupervisorError(f"Model {model_id!r} is disabled")
        if agent["model_id"] != model_id:
            raise SupervisorError(
                f"Agent {agent_id!r} is not bound to Model {model_id!r}"
            )

    def _qualification_required(self, binding: dict[str, Any]) -> bool:
        """Require Board 21 preflight for real/non-mock Agent adapters."""
        profile = binding.get("check_profile", {})
        if (
            self.allow_synthetic_fixture_for_tests
            and isinstance(profile, dict)
            and "synthetic_checks" in profile
        ):
            return False
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT adapter_type FROM agent_profiles WHERE id = ?",
                (binding["agent_id"],),
            ).fetchone()
        return row is not None and row["adapter_type"] != "mock"

    @staticmethod
    def _validate_role(role_key: str) -> None:
        if role_key not in REQUIRED_ROLES:
            raise SupervisorError(
                "team role must be manager, worker or reviewer"
            )

    @staticmethod
    def _validate_binding_input(
        *,
        agent_id: str,
        model_id: str,
        launch_mode: str,
        transport: str,
        check_profile: dict[str, Any],
    ) -> None:
        if not agent_id.strip() or not model_id.strip():
            raise SupervisorError("Agent and Model bindings cannot be empty")
        if launch_mode not in LAUNCH_MODES:
            raise SupervisorError(f"unsupported launch mode {launch_mode!r}")
        if transport not in TRANSPORTS:
            raise SupervisorError(f"unsupported Supervisor transport {transport!r}")
        if launch_mode == "manual" and transport != "manual":
            raise SupervisorError("manual launch mode requires manual transport")
        if launch_mode == "remote" and transport == "manual":
            raise SupervisorError("remote launch mode requires a protocol transport")
        if not isinstance(check_profile, dict):
            raise SupervisorError("readiness check profile must be an object")

    @staticmethod
    def _mark_pending_approvals_stale(conn, *, failure: str) -> None:
        conn.execute(
            """
            UPDATE supervisor_start_approvals
            SET status = 'stale', failure = ?
            WHERE status IN ('pending', 'approved') AND consumed_at IS NULL
            """,
            (failure,),
        )


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return sha256(_dump(value).encode("utf-8")).hexdigest()


def _bounded_note(value: str) -> str:
    return value.strip()[:500]


def _bounded_project_goal(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SupervisorError("project goal must be non-empty text")
    normalized = value.strip()
    if len(normalized.encode("utf-8")) > MAX_PROJECT_GOAL_BYTES:
        raise SupervisorError(
            f"project goal exceeds {MAX_PROJECT_GOAL_BYTES} UTF-8 bytes"
        )
    return normalized


def _decode_binding(row) -> dict[str, Any]:
    item = dict(row)
    item["check_profile"] = json.loads(item.pop("check_profile_json"))
    return item


def _decode_report(row) -> dict[str, Any]:
    item = dict(row)
    item["report"] = json.loads(item.pop("report_json"))
    return item


def _decode_qualification_preflight(row) -> dict[str, Any]:
    item = dict(row)
    item["scope"] = json.loads(item.pop("scope_json"))
    return item


def _decode_snapshot(row) -> dict[str, Any]:
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    return item


def _decode_approval(row) -> dict[str, Any]:
    item = dict(row)
    item["scope"] = json.loads(item.pop("scope_json"))
    return item


def _decode_event(row) -> dict[str, Any]:
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    return item


def _decode_lifecycle_session(row) -> dict[str, Any]:
    item = dict(row)
    item["evidence"] = json.loads(item.pop("evidence_json"))
    return item


def _decode_lifecycle_event(row) -> dict[str, Any]:
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    return item


def _next_lifecycle_state(
    operation: str,
    current_state: str,
    launch_mode: str,
    transport: str,
) -> str | None:
    transitions = {
        ("start", "configured"): "started",
        ("start", "stopped"): "started",
        ("start", "failed"): "started",
        ("start", "user_confirmation_required"): "started",
        ("connect", "started"): "connected",
        ("connect", "connected"): "connected",
        ("attach", "connected"): "attached",
        ("attach", "started"): "attached",
        ("detach", "attached"): "detached",
        ("detach", "connected"): "detached",
        ("detach", "started"): "detached",
        ("stop", "detached"): "stopped",
        ("stop", "started"): "stopped",
        ("stop", "connected"): "stopped",
        ("stop", "attached"): "stopped",
        ("stop", "stopped"): "stopped",
        ("stop", "failed"): "stopped",
        ("stop", "user_confirmation_required"): "stopped",
    }
    if launch_mode in {"remote", "manual"} and operation == "start":
        return None
    return transitions.get((operation, current_state))


def _suggestion(
    check_name: str,
    status: str,
    binding: dict[str, Any],
) -> str:
    if status == "user_confirmation_required":
        display_name = "connection" if check_name == "connectivity" else check_name
        return (
            f"Review the local {display_name} evidence for {binding['role_key']} and "
            "record an explicit user confirmation if it cannot be machine-verified."
        )
    suggestions = {
        "process": (
            "Start or attach the approved local fake Agent process, then rerun "
            "the readiness check."
        ),
        "login": (
            "Complete the local fake-service login setup without placing a "
            "credential in Git or SQLite, then rerun the readiness check."
        ),
        "model": (
            "Select the bound Model in the local fake service and rerun the "
            "readiness check."
        ),
        "actual_model": (
            "Select the bound Model in the local fake service and rerun the "
            "lifecycle evidence check."
        ),
        "permission": (
            "Grant only the configured least-privilege permission and rerun "
            "the readiness check."
        ),
        "version": (
            "Install the required local fake-service version or update the "
            "team binding after review."
        ),
        "connection": (
            "Restore the approved loopback fake-service connection and rerun "
            "the readiness check."
        ),
        "connectivity": (
            "Review the local connection evidence (connectivity), restore the "
            "approved loopback fake-service connection and rerun the lifecycle "
            "evidence check."
        ),
        "protocol": (
            "Use the configured local protocol fixture and rerun the lifecycle "
            "evidence check."
        ),
        "qualification_preflight": (
            "Bind a current, matching offline qualification preflight for this "
            "non-mock Agent before creating a team snapshot."
        ),
    }
    return suggestions[check_name]
