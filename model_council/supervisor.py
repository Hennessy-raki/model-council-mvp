from __future__ import annotations

import json
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
        platform: LocalManagerPlatform | None = None,
    ):
        self.store = store
        self.registry = registry
        self.inspector = inspector or StaticReadinessInspector()
        self.platform = platform or LocalManagerPlatform(store)

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

        errors = [
            {
                "check": name,
                "code": checks[name].get("code", checks[name]["status"]),
                "suggestion": _suggestion(name, checks[name]["status"], binding),
            }
            for name in CHECK_NAMES
            if checks[name]["status"]
            in {"failed", "user_confirmation_required"}
        ]
        statuses = {item["status"] for item in checks.values()}
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
        unsupported = set(check_names) - set(CHECK_NAMES)
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
                check = current["report"]["checks"][check_name]
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


def _suggestion(
    check_name: str,
    status: str,
    binding: dict[str, Any],
) -> str:
    if status == "user_confirmation_required":
        return (
            f"Review the local {check_name} evidence for {binding['role_key']} and "
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
    }
    return suggestions[check_name]
