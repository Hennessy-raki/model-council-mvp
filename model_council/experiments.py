from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from .interoperability import InteroperabilityError, JsonLineProcess
from .registry import RegistryService, sanitize_for_storage
from .store import CouncilStore, utc_now
from .supervisor import SupervisorError, SupervisorService


EXPERIMENT_PHASES = {"14.0", "14.1"}
EXPERIMENT_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "armed",
    "running",
    "completed",
    "failed",
    "stale",
    "stopped",
}
DEFAULT_PERMISSIONS = {
    "sandbox": "read-only",
    "tools_enabled": False,
    "workspace_write": False,
    "git_enabled": False,
    "files": 0,
    "artifacts": 0,
}
DEFAULT_LIMITS = {
    "max_prompt_bytes": 4096,
    "max_transport_bytes": 4096,
    "max_total_bytes": 8192,
    "max_response_bytes": 16384,
    "max_calls": 1,
    "max_retries": 0,
    "parallelism": 1,
    "timeout_seconds": 120,
}
STOP_RULES = (
    "team snapshot or Agent/Model identity changed",
    "prompt or transport scope changed",
    "unexpected file or Artifact appeared",
    "permission, tool, workspace or Git access was requested",
    "model, version or working directory differed from the approved scope",
    "redirect, additional endpoint or auxiliary network request was observed",
    "call, retry, timeout, response-byte, token or cost limit was exceeded",
)
EXCLUDED_PATTERNS = (
    re.compile(
        r"(?i)(api[_-]?key|authorization|bearer|password|secret|token)\s*[:=]"
    ),
    re.compile(r"(?i)-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    re.compile(r"(?i)[a-z]:\\users\\[^\\\s]+"),
    re.compile(r"(?i)/(?:home|users)/[^/\s]+"),
)


class ExperimentError(ValueError):
    pass


class ExperimentService:
    """Board 14 offline experiment manifests and one-time approvals."""

    def __init__(
        self,
        store: CouncilStore,
        registry: RegistryService,
        supervisor: SupervisorService,
    ):
        self.store = store
        self.registry = registry
        self.supervisor = supervisor

    def prepare(self, spec: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(spec, dict):
            raise ExperimentError("experiment specification must be an object")
        phase = str(spec.get("phase", ""))
        execution_mode = str(spec.get("execution_mode", ""))
        if phase not in EXPERIMENT_PHASES:
            raise ExperimentError("experiment phase must be 14.0 or 14.1")
        expected_mode = "synthetic_fake" if phase == "14.0" else "real_codex"
        if execution_mode != expected_mode:
            raise ExperimentError(
                f"phase {phase} requires execution_mode {expected_mode!r}"
            )

        snapshot_id = _required_text(spec.get("team_snapshot_id"), "team snapshot id")
        try:
            snapshot = self.supervisor.validate_snapshot(snapshot_id)
        except SupervisorError as exc:
            raise ExperimentError("team snapshot is unavailable or stale") from exc

        prompt = _required_text(spec.get("prompt"), "synthetic prompt")
        if spec.get("source") != "synthetic":
            raise ExperimentError("Board 14.0/14.1 permits synthetic source only")
        _reject_excluded_text(prompt, "synthetic prompt")

        limits = _validate_limits(spec.get("limits", {}))
        prompt_bytes = len(prompt.encode("utf-8"))
        if prompt_bytes > limits["max_prompt_bytes"]:
            raise ExperimentError(
                f"prompt is {prompt_bytes} bytes, exceeding "
                f"{limits['max_prompt_bytes']}"
            )
        permissions = _validate_permissions(spec.get("permissions", {}))

        manager_agent_id = _required_text(
            spec.get("manager_agent_id"),
            "manager Agent id",
        )
        manager_model_id = _required_text(
            spec.get("manager_model_id"),
            "manager Model id",
        )
        manager_binding = next(
            (
                item
                for item in snapshot["payload"]["roles"]
                if item["role_key"] == "manager"
            ),
            None,
        )
        if manager_binding is None:
            raise ExperimentError("team snapshot has no Manager binding")
        if (
            manager_binding["agent_id"] != manager_agent_id
            or manager_binding["model_id"] != manager_model_id
        ):
            raise ExperimentError(
                "experiment Manager must exactly match the team snapshot"
            )

        manager_identity = self._identity(manager_agent_id, manager_model_id)
        allowed_manager_types = (
            {"mock"} if phase == "14.0" else {"cli", "codex_app_server"}
        )
        if manager_identity["agent"]["adapter_type"] not in allowed_manager_types:
            raise ExperimentError(
                f"phase {phase} Manager requires one of "
                f"{sorted(allowed_manager_types)}"
            )
        if (
            phase == "14.1"
            and manager_identity["agent"]["config"].get(
                "invoke_enabled",
                False,
            )
        ):
            raise ExperimentError(
                "Board 14.1 preparation requires invoke_enabled to remain false"
            )

        workers_raw = spec.get("workers")
        if not isinstance(workers_raw, list) or len(workers_raw) != 2:
            raise ExperimentError("experiment requires exactly two fake Workers")
        workers = []
        worker_ids: set[str] = set()
        for index, item in enumerate(workers_raw, start=1):
            if not isinstance(item, dict):
                raise ExperimentError(f"Worker {index} must be an object")
            agent_id = _required_text(item.get("agent_id"), f"Worker {index} Agent id")
            model_id = _required_text(item.get("model_id"), f"Worker {index} Model id")
            role_key = _required_text(item.get("role_key"), f"Worker {index} role")
            if agent_id in worker_ids:
                raise ExperimentError("the two fake Workers must be distinct")
            worker_ids.add(agent_id)
            identity = self._identity(agent_id, model_id)
            if identity["agent"]["adapter_type"] != "mock":
                raise ExperimentError(
                    f"Worker {agent_id!r} must use the local mock Adapter"
                )
            workers.append(
                {
                    "agent_id": agent_id,
                    "model_id": model_id,
                    "role_key": role_key,
                    "identity": identity,
                }
            )

        transport = _validate_transport(
            spec.get("transport", {}),
            execution_mode=execution_mode,
            manager_model_id=manager_model_id,
        )
        expected_host_type = (
            "synthetic_fake"
            if phase == "14.0"
            else manager_identity["agent"]["adapter_type"]
        )
        if transport["host_type"] != expected_host_type:
            raise ExperimentError(
                "transport host_type must match the Manager Adapter"
            )
        configured_command = manager_identity["agent"]["config"].get("command")
        if configured_command is not None and configured_command != transport["command"]:
            raise ExperimentError(
                "transport command must match the registered Manager command"
            )
        transport_bytes = len(_dump(transport).encode("utf-8"))
        if transport_bytes > limits["max_transport_bytes"]:
            raise ExperimentError(
                f"transport metadata is {transport_bytes} bytes, exceeding "
                f"{limits['max_transport_bytes']}"
            )
        total_outbound_bytes = prompt_bytes + transport_bytes
        if total_outbound_bytes > limits["max_total_bytes"]:
            raise ExperimentError(
                f"prompt plus transport metadata is {total_outbound_bytes} "
                f"bytes, exceeding {limits['max_total_bytes']}"
            )
        expected_output = spec.get("expected_output", {})
        if not isinstance(expected_output, dict):
            raise ExperimentError("expected_output must be an object")
        output_schema = str(
            expected_output.get("schema", "manager_two_worker_plan_v1")
        )
        if output_schema != "manager_two_worker_plan_v1":
            raise ExperimentError(
                "Board 14.0/14.1 requires manager_two_worker_plan_v1"
            )

        scope = {
            "version": 1,
            "board": 14,
            "phase": phase,
            "execution_mode": execution_mode,
            "source": "synthetic",
            "team_snapshot_id": snapshot["id"],
            "team_snapshot_sha256": snapshot["snapshot_sha256"],
            "manager": {
                "agent_id": manager_agent_id,
                "model_id": manager_model_id,
                "identity": manager_identity,
            },
            "workers": workers,
            "prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_bytes": prompt_bytes,
            "transport_bytes": transport_bytes,
            "total_outbound_bytes": total_outbound_bytes,
            "transport": transport,
            "permissions": permissions,
            "limits": limits,
            "expected_output": {"schema": output_schema, "task_count": 2},
            "stop_rules": list(STOP_RULES),
            "actions": [
                (
                    "run deterministic local simulation"
                    if execution_mode == "synthetic_fake"
                    else "arm exact Codex Manager candidate without invoking it"
                )
            ],
        }
        scope_sha256 = _digest(scope)
        experiment_id = str(uuid4())
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO controlled_experiments(
                    id, phase, team_snapshot_id, execution_mode,
                    manager_agent_id, manager_model_id, prompt_sha256,
                    prompt_bytes, prompt_text, scope_sha256, scope_json,
                    status, requested_at, decided_at, armed_at, started_at,
                    completed_at, failure
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?,
                    NULL, NULL, NULL, NULL, NULL)
                """,
                (
                    experiment_id,
                    phase,
                    snapshot_id,
                    execution_mode,
                    manager_agent_id,
                    manager_model_id,
                    scope["prompt_sha256"],
                    prompt_bytes,
                    prompt,
                    scope_sha256,
                    _dump(scope),
                    now,
                ),
            )
        self._event(
            experiment_id,
            "experiment_prepared",
            {
                "phase": phase,
                "execution_mode": execution_mode,
                "scope_sha256": scope_sha256,
                "external_invocation": False,
            },
        )
        return self.experiment(experiment_id)

    def decide(
        self,
        experiment_id: str,
        *,
        approve: bool,
        confirmation: str = "",
    ) -> dict[str, Any]:
        experiment = self.experiment(experiment_id)
        if experiment["status"] != "pending":
            raise ExperimentError(f"experiment {experiment_id!r} is not pending")
        if approve and confirmation != experiment["scope_sha256"]:
            raise ExperimentError(
                "experiment confirmation must exactly match scope_sha256"
            )
        status = "approved" if approve else "rejected"
        now = utc_now()
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE controlled_experiments
                SET status = ?, decided_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, now, experiment_id),
            ).rowcount
        if not updated:
            raise ExperimentError("experiment changed before approval decision")
        self._event(
            experiment_id,
            f"experiment_{status}",
            {"scope_sha256": experiment["scope_sha256"]},
        )
        return self.experiment(experiment_id)

    def arm(self, experiment_id: str) -> dict[str, Any]:
        experiment = self.experiment(experiment_id, include_prompt=True)
        if experiment["status"] != "approved":
            raise ExperimentError(f"experiment {experiment_id!r} is not approved")
        try:
            self._revalidate(experiment)
        except ExperimentError as exc:
            self._mark_stale(experiment_id, str(exc))
            raise
        now = utc_now()
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE controlled_experiments
                SET status = 'armed', armed_at = ?
                WHERE id = ? AND status = 'approved'
                """,
                (now, experiment_id),
            ).rowcount
        if not updated:
            raise ExperimentError("experiment changed before it could be armed")
        self._event(
            experiment_id,
            "experiment_armed",
            {
                "execution_mode": experiment["execution_mode"],
                "external_invocation": False,
            },
        )
        return self.experiment(experiment_id)

    def request_start(self, experiment_id: str) -> dict[str, Any]:
        experiment = self.experiment(experiment_id, include_prompt=True)
        if experiment["execution_mode"] != "real_codex":
            raise ExperimentError("only real_codex experiments require start approval")
        if experiment["status"] != "armed":
            raise ExperimentError(f"experiment {experiment_id!r} is not armed")
        try:
            self._revalidate(experiment)
        except ExperimentError as exc:
            self._mark_stale(experiment_id, str(exc))
            raise
        scope = experiment["scope"]
        manager_config = scope["manager"]["identity"]["agent"]["config"]
        if manager_config.get("strict_no_approvals") is not True:
            raise ExperimentError("real execution requires strict_no_approvals")
        start_scope = {
            "version": 1,
            "action": "start_codex_app_server_and_one_turn",
            "experiment_id": experiment_id,
            "experiment_scope_sha256": experiment["scope_sha256"],
            "manager_identity_sha256": scope["manager"]["identity"][
                "identity_sha256"
            ],
            "prompt_sha256": scope["prompt_sha256"],
            "transport": scope["transport"],
            "permissions": scope["permissions"],
            "limits": scope["limits"],
        }
        approval_id = str(uuid4())
        digest = _digest(start_scope)
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO controlled_experiment_start_approvals(
                    id, experiment_id, scope_sha256, scope_json, status,
                    requested_at, decided_at, consumed_at, failure
                ) VALUES (?, ?, ?, ?, 'pending', ?, NULL, NULL, NULL)
                """,
                (approval_id, experiment_id, digest, _dump(start_scope), utc_now()),
            )
        self._event(
            experiment_id,
            "experiment_start_requested",
            {"start_approval_id": approval_id, "scope_sha256": digest},
        )
        return self.start_approval(approval_id)

    def start_approval(self, approval_id: str) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM controlled_experiment_start_approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
        if row is None:
            raise ExperimentError(f"start approval {approval_id!r} does not exist")
        result = dict(row)
        result["scope"] = json.loads(result.pop("scope_json"))
        return result

    def decide_start(
        self, approval_id: str, *, approve: bool, confirmation: str = ""
    ) -> dict[str, Any]:
        approval = self.start_approval(approval_id)
        if approval["status"] != "pending":
            raise ExperimentError(f"start approval {approval_id!r} is not pending")
        if approve and confirmation != approval["scope_sha256"]:
            raise ExperimentError(
                "start confirmation must exactly match scope_sha256"
            )
        status = "approved" if approve else "rejected"
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE controlled_experiment_start_approvals
                SET status = ?, decided_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, utc_now(), approval_id),
            )
        self._event(
            approval["experiment_id"],
            f"experiment_start_{status}",
            {"start_approval_id": approval_id, "scope_sha256": approval["scope_sha256"]},
        )
        return self.start_approval(approval_id)

    def consume_start(self, approval_id: str) -> dict[str, Any]:
        approval = self.start_approval(approval_id)
        if approval["status"] != "approved":
            raise ExperimentError(
                f"start approval {approval_id!r} is not approved"
            )
        experiment = self.experiment(approval["experiment_id"], include_prompt=True)
        if experiment["status"] != "armed":
            raise ExperimentError(
                f"experiment {experiment['id']!r} is not armed"
            )
        try:
            self._revalidate(experiment)
        except ExperimentError as exc:
            self._mark_stale(experiment["id"], str(exc))
            with self.store.connect() as conn:
                conn.execute(
                    """
                    UPDATE controlled_experiment_start_approvals
                    SET status = 'stale', failure = ?
                    WHERE id = ? AND status = 'approved'
                    """,
                    (_bounded_text(str(exc), 500, "failure"), approval_id),
                )
            raise
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE controlled_experiment_start_approvals
                SET status = 'consumed', consumed_at = ?
                WHERE id = ? AND status = 'approved'
                """,
                (utc_now(), approval_id),
            ).rowcount
        if not updated:
            raise ExperimentError("start approval changed before consumption")
        self._event(
            experiment["id"],
            "experiment_start_consumed",
            {"start_approval_id": approval_id, "external_invocation": False},
        )
        return self.start_approval(approval_id)

    def execute_start(self, approval_id: str) -> dict[str, Any]:
        approval = self.consume_start(approval_id)
        experiment = self.experiment(approval["experiment_id"], include_prompt=True)
        scope = experiment["scope"]
        try:
            self._start_running(experiment["id"])
            response, usage = self._execute_codex_app_server(experiment)
            self._validate_manager_response(response, scope)
            response_bytes = len(response.encode("utf-8"))
            if response_bytes > scope["limits"]["max_response_bytes"]:
                raise ExperimentError("Manager response exceeded max_response_bytes")
            total_tokens = usage.get("total_tokens") if usage else None
            token_limit = scope["limits"].get("max_total_tokens")
            if token_limit is not None and (
                total_tokens is None or total_tokens > token_limit
            ):
                raise ExperimentError(
                    "Manager usage is unavailable or exceeded max_total_tokens"
                )
            evidence = {
                "version": 1,
                "kind": "codex_app_server_turn",
                "response_sha256": sha256(response.encode("utf-8")).hexdigest(),
                "response_bytes": response_bytes,
                "response_text_stored": False,
                "usage": usage,
                "process_invocation_count": 1,
                "retry_count": 0,
                "expected_output_schema": scope["expected_output"]["schema"],
            }
            self._evidence(experiment["id"], "codex_app_server_turn", "passed", evidence)
            with self.store.connect() as conn:
                conn.execute(
                    """
                    UPDATE controlled_experiments
                    SET status = 'completed', completed_at = ?
                    WHERE id = ? AND status = 'running'
                    """,
                    (utc_now(), experiment["id"]),
                )
            self._event(
                experiment["id"],
                "experiment_completed",
                {
                    "start_approval_id": approval["id"],
                    "process_invocation_count": 1,
                    "response_sha256": evidence["response_sha256"],
                },
            )
        except Exception as exc:
            self._fail(experiment["id"], str(exc))
            raise
        return self.snapshot(experiment["id"], include_prompt=False)

    def simulate(self, experiment_id: str) -> dict[str, Any]:
        experiment = self.experiment(experiment_id, include_prompt=True)
        if experiment["execution_mode"] != "synthetic_fake":
            raise ExperimentError(
                "real_codex experiments cannot run through the local simulator"
            )
        if experiment["status"] != "armed":
            raise ExperimentError(f"experiment {experiment_id!r} is not armed")
        try:
            self._revalidate(experiment)
        except ExperimentError as exc:
            self._mark_stale(experiment_id, str(exc))
            raise
        started = utc_now()
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE controlled_experiments
                SET status = 'running', started_at = ?
                WHERE id = ? AND status = 'armed'
                """,
                (started, experiment_id),
            ).rowcount
        if not updated:
            raise ExperimentError("experiment changed before simulation")

        scope = experiment["scope"]
        plan = {
            "tasks": [
                {
                    "key": f"work_{index}",
                    "title": f"Synthetic worker {index}",
                    "instruction": "Return one bounded synthetic observation.",
                    "agent": worker["agent_id"],
                    "role": worker["role_key"],
                    "depends_on": [],
                }
                for index, worker in enumerate(scope["workers"], start=1)
            ]
        }
        plan_text = _dump(plan)
        worker_evidence = []
        for index, worker in enumerate(scope["workers"], start=1):
            output = (
                f"synthetic-result-{index}:"
                f"{worker['role_key']}:{worker['agent_id']}"
            )
            output_bytes = output.encode("utf-8")
            worker_evidence.append(
                {
                    "agent_id": worker["agent_id"],
                    "model_id": worker["model_id"],
                    "role_key": worker["role_key"],
                    "output_sha256": sha256(output_bytes).hexdigest(),
                    "output_bytes": len(output_bytes),
                }
            )
        evidence = {
            "version": 1,
            "status": "passed",
            "assertions": {
                "task_count_is_two": len(plan["tasks"]) == 2,
                "workers_are_distinct": len(
                    {item["agent"] for item in plan["tasks"]}
                )
                == 2,
                "zero_files": scope["permissions"]["files"] == 0,
                "zero_artifacts": scope["permissions"]["artifacts"] == 0,
                "read_only": scope["permissions"]["sandbox"] == "read-only",
                "tools_disabled": not scope["permissions"]["tools_enabled"],
                "workspace_write_disabled": not scope["permissions"][
                    "workspace_write"
                ],
                "git_disabled": not scope["permissions"]["git_enabled"],
                "no_adapter_invocation": True,
                "no_network_request": True,
            },
            "plan_sha256": sha256(plan_text.encode("utf-8")).hexdigest(),
            "plan_bytes": len(plan_text.encode("utf-8")),
            "worker_results": worker_evidence,
            "external_call_count": 0,
            "adapter_invocation_count": 0,
        }
        if not all(evidence["assertions"].values()):
            self._fail(experiment_id, "synthetic experiment assertion failed")
            raise ExperimentError("synthetic experiment assertion failed")
        self._evidence(experiment_id, "synthetic_run", "passed", evidence)
        completed = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE controlled_experiments
                SET status = 'completed', completed_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (completed, experiment_id),
            )
        self._event(
            experiment_id,
            "experiment_completed",
            {
                "external_call_count": 0,
                "adapter_invocation_count": 0,
                "evidence_status": "passed",
            },
        )
        return self.snapshot(experiment_id)

    def stop(self, experiment_id: str, *, reason: str) -> dict[str, Any]:
        experiment = self.experiment(experiment_id)
        if experiment["status"] not in {"pending", "approved", "armed"}:
            raise ExperimentError(
                f"experiment {experiment_id!r} cannot be stopped from "
                f"{experiment['status']!r}"
            )
        failure = _bounded_text(reason, 500, "stop reason")
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE controlled_experiments
                SET status = 'stopped', completed_at = ?, failure = ?
                WHERE id = ? AND status IN ('pending', 'approved', 'armed')
                """,
                (utc_now(), failure, experiment_id),
            )
        self._event(experiment_id, "experiment_stopped", {"reason": failure})
        return self.experiment(experiment_id)

    def experiment(
        self,
        experiment_id: str,
        *,
        include_prompt: bool = False,
    ) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM controlled_experiments WHERE id = ?",
                (experiment_id,),
            ).fetchone()
        if row is None:
            raise ExperimentError(f"experiment {experiment_id!r} not found")
        item = dict(row)
        item["scope"] = json.loads(item.pop("scope_json"))
        prompt = item.pop("prompt_text")
        if include_prompt:
            item["prompt"] = prompt
        return item

    def experiments(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status is not None and status not in EXPERIMENT_STATUSES:
            raise ExperimentError(f"unsupported experiment status {status!r}")
        query = "SELECT id FROM controlled_experiments"
        params: tuple[Any, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY requested_at DESC, id DESC"
        with self.store.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self.experiment(row["id"]) for row in rows]

    def snapshot(
        self,
        experiment_id: str,
        *,
        include_prompt: bool = False,
    ) -> dict[str, Any]:
        return {
            "experiment": self.experiment(
                experiment_id,
                include_prompt=include_prompt,
            ),
            "events": self.events(experiment_id),
            "evidence": self.evidence(experiment_id),
        }

    def events(self, experiment_id: str) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM controlled_experiment_events
                WHERE experiment_id = ?
                ORDER BY created_at, id
                """,
                (experiment_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def evidence(self, experiment_id: str) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM controlled_experiment_evidence
                WHERE experiment_id = ?
                ORDER BY created_at, id
                """,
                (experiment_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["evidence"] = json.loads(item.pop("evidence_json"))
            result.append(item)
        return result

    def _identity(self, agent_id: str, model_id: str) -> dict[str, Any]:
        with self.store.connect() as conn:
            agent = conn.execute(
                "SELECT * FROM agent_profiles WHERE id = ?",
                (agent_id,),
            ).fetchone()
            model = conn.execute(
                "SELECT * FROM models WHERE id = ?",
                (model_id,),
            ).fetchone()
        if agent is None:
            raise ExperimentError(f"unknown Agent {agent_id!r}")
        if model is None:
            raise ExperimentError(f"unknown Model {model_id!r}")
        if not bool(agent["enabled"]) or not bool(model["enabled"]):
            raise ExperimentError("experiment Agent and Model must be enabled")
        if agent["model_id"] != model_id:
            raise ExperimentError(
                f"Agent {agent_id!r} is not bound to Model {model_id!r}"
            )
        agent_item = dict(agent)
        model_item = dict(model)
        for field in (
            "capabilities_json",
            "boundaries_json",
            "config_json",
        ):
            agent_item[field.removesuffix("_json")] = json.loads(
                agent_item.pop(field)
            )
        for field in ("capabilities_json", "metadata_json"):
            model_item[field.removesuffix("_json")] = json.loads(
                model_item.pop(field)
            )
        for item in (agent_item, model_item):
            item["enabled"] = bool(item["enabled"])
            item.pop("created_at", None)
            item.pop("updated_at", None)
        payload = {
            "agent": sanitize_for_storage(agent_item),
            "model": sanitize_for_storage(model_item),
        }
        payload["identity_sha256"] = _digest(payload)
        return payload

    def _revalidate(self, experiment: dict[str, Any]) -> None:
        scope = experiment["scope"]
        try:
            snapshot = self.supervisor.validate_snapshot(
                experiment["team_snapshot_id"]
            )
        except SupervisorError as exc:
            raise ExperimentError("team snapshot changed after preparation") from exc
        if snapshot["snapshot_sha256"] != scope["team_snapshot_sha256"]:
            raise ExperimentError("team snapshot digest changed after preparation")
        prompt = experiment["prompt"]
        if sha256(prompt.encode("utf-8")).hexdigest() != scope["prompt_sha256"]:
            raise ExperimentError("prompt changed after preparation")
        identities = [
            scope["manager"],
            *scope["workers"],
        ]
        for item in identities:
            current = self._identity(item["agent_id"], item["model_id"])
            if current["identity_sha256"] != item["identity"]["identity_sha256"]:
                raise ExperimentError(
                    f"Agent or Model identity changed for {item['agent_id']!r}"
                )
        if _digest(scope) != experiment["scope_sha256"]:
            raise ExperimentError("experiment scope changed after preparation")

    def _start_running(self, experiment_id: str) -> None:
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE controlled_experiments
                SET status = 'running', started_at = ?
                WHERE id = ? AND status = 'armed'
                """,
                (utc_now(), experiment_id),
            ).rowcount
        if not updated:
            raise ExperimentError("experiment changed before execution")

    def _execute_codex_app_server(
        self,
        experiment: dict[str, Any],
    ) -> tuple[str, dict[str, int] | None]:
        scope = experiment["scope"]
        manager_config = scope["manager"]["identity"]["agent"]["config"]
        transport_scope = scope["transport"]
        if (
            manager_config.get("strict_no_approvals") is not True
            or manager_config.get("invoke_enabled") is not False
        ):
            raise ExperimentError("Manager is not a disabled strict candidate")
        if transport_scope["host_type"] != "codex_app_server":
            raise ExperimentError("real execution requires codex_app_server transport")
        command = transport_scope["command"]
        cwd = Path(transport_scope["working_directory"])
        if not cwd.is_dir():
            raise ExperimentError("approved working directory is unavailable")
        transport = JsonLineProcess(
            command,
            cwd=cwd,
            timeout_seconds=scope["limits"]["timeout_seconds"],
        )
        try:
            self._exchange(
                transport,
                1,
                "initialize",
                {"clientInfo": {"name": "model-council", "version": "0.2.0rc1"}},
            )
            transport.send({"method": "initialized", "params": {}})
            thread = self._exchange(
                transport,
                2,
                "thread/start",
                {
                    "cwd": str(cwd),
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "experimentalRawEvents": False,
                    "persistExtendedHistory": False,
                    "model": transport_scope["model_id"],
                },
            )
            thread_id = self._result_id(thread, "thread")
            turn = self._exchange(
                transport,
                3,
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": [{"type": "text", "text": experiment["prompt"]}],
                },
            )
            turn_id = self._result_id(turn, "turn")
            return self._read_turn(
                transport,
                turn_id=turn_id,
                max_response_bytes=scope["limits"]["max_response_bytes"],
            )
        except InteroperabilityError as exc:
            raise ExperimentError(str(exc)) from exc
        finally:
            transport.close()

    @staticmethod
    def _result_id(result: dict[str, Any], key: str) -> str:
        item = result.get(key)
        value = item.get("id") if isinstance(item, dict) else None
        if not isinstance(value, str) or not value:
            raise ExperimentError(f"Codex App Server {key}/start result lacks id")
        return value

    def _exchange(
        self,
        transport: JsonLineProcess,
        request_id: int,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        transport.send({"id": request_id, "method": method, "params": params})
        while True:
            payload = transport.receive()
            if "method" in payload and "id" in payload:
                self._reject_server_request(transport, payload)
            if payload.get("id") != request_id:
                continue
            if "error" in payload:
                raise ExperimentError(
                    f"Codex App Server {method} failed: {payload['error']}"
                )
            result = payload.get("result")
            if not isinstance(result, dict):
                raise ExperimentError(
                    f"Codex App Server {method} result must be an object"
                )
            return result

    def _read_turn(
        self,
        transport: JsonLineProcess,
        *,
        turn_id: str,
        max_response_bytes: int,
    ) -> tuple[str, dict[str, int] | None]:
        messages: list[str] = []
        usage: dict[str, int] | None = None
        while True:
            payload = transport.receive()
            if "method" in payload and "id" in payload:
                self._reject_server_request(transport, payload)
            method = payload.get("method")
            params = payload.get("params")
            if not isinstance(params, dict):
                params = {}
            if method == "item/completed":
                item = params.get("item")
                if isinstance(item, dict) and item.get("type") == "agentMessage":
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        if len(text.encode("utf-8")) > max_response_bytes:
                            raise ExperimentError(
                                "Manager response exceeded max_response_bytes"
                            )
                        messages.append(text)
            elif method == "thread/tokenUsage/updated":
                token_usage = params.get("tokenUsage")
                last = token_usage.get("last") if isinstance(token_usage, dict) else None
                if isinstance(last, dict):
                    mapped = {
                        "input_tokens": last.get("inputTokens"),
                        "output_tokens": last.get("outputTokens"),
                        "total_tokens": last.get("totalTokens"),
                    }
                    if all(isinstance(value, int) and value >= 0 for value in mapped.values()):
                        usage = mapped
            elif method == "turn/completed":
                turn = params.get("turn")
                if not isinstance(turn, dict) or turn.get("id") != turn_id:
                    continue
                if turn.get("status") not in {"completed", "complete"}:
                    raise ExperimentError("Codex App Server turn did not complete")
                if not messages:
                    raise ExperimentError("Codex App Server returned no agent message")
                return messages[-1], usage

    @staticmethod
    def _reject_server_request(
        transport: JsonLineProcess,
        payload: dict[str, Any],
    ) -> None:
        request_id = payload.get("id")
        if not isinstance(request_id, int):
            raise ExperimentError("Codex App Server approval request lacks id")
        transport.send(
            {
                "id": request_id,
                "result": {"decision": "decline"},
            }
        )
        raise ExperimentError("Codex App Server requested interactive approval")

    @staticmethod
    def _validate_manager_response(response: str, scope: dict[str, Any]) -> None:
        try:
            payload = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ExperimentError("Manager response was not JSON") from exc
        tasks = payload.get("tasks") if isinstance(payload, dict) else None
        if not isinstance(tasks, list) or len(tasks) != scope["expected_output"]["task_count"]:
            raise ExperimentError("Manager response did not contain exactly two tasks")

    def _mark_stale(self, experiment_id: str, failure: str) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE controlled_experiments
                SET status = 'stale', completed_at = ?, failure = ?
                WHERE id = ? AND status IN ('approved', 'armed')
                """,
                (utc_now(), _bounded_text(failure, 500, "failure"), experiment_id),
            )
        self._event(
            experiment_id,
            "experiment_stale",
            {"failure": _bounded_text(failure, 500, "failure")},
        )

    def _fail(self, experiment_id: str, failure: str) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE controlled_experiments
                SET status = 'failed', completed_at = ?, failure = ?
                WHERE id = ?
                """,
                (utc_now(), _bounded_text(failure, 500, "failure"), experiment_id),
            )
        self._event(
            experiment_id,
            "experiment_failed",
            {"failure": _bounded_text(failure, 500, "failure")},
        )

    def _event(
        self,
        experiment_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO controlled_experiment_events(
                    id, experiment_id, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    experiment_id,
                    event_type,
                    _dump(sanitize_for_storage(payload)),
                    utc_now(),
                ),
            )

    def _evidence(
        self,
        experiment_id: str,
        kind: str,
        status: str,
        evidence: dict[str, Any],
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO controlled_experiment_evidence(
                    id, experiment_id, kind, status, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    experiment_id,
                    kind,
                    status,
                    _dump(sanitize_for_storage(evidence)),
                    utc_now(),
                ),
            )


def _validate_permissions(value: Any) -> dict[str, Any]:
    if value in ({}, None):
        return dict(DEFAULT_PERMISSIONS)
    if not isinstance(value, dict):
        raise ExperimentError("permissions must be an object")
    result = dict(DEFAULT_PERMISSIONS)
    result.update(value)
    if result != DEFAULT_PERMISSIONS:
        raise ExperimentError(
            "Board 14.0/14.1 permissions must remain read-only with zero "
            "files, zero Artifacts, no tools, no workspace writes and no Git"
        )
    return result


def _validate_limits(value: Any) -> dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ExperimentError("limits must be an object")
    unsupported = set(value) - {
        *DEFAULT_LIMITS,
        "max_total_tokens",
        "max_total_cost",
        "cost_currency",
    }
    if unsupported:
        raise ExperimentError(f"unsupported experiment limits: {sorted(unsupported)}")
    result = dict(DEFAULT_LIMITS)
    result.update(value)
    for key in (
        "max_prompt_bytes",
        "max_transport_bytes",
        "max_total_bytes",
        "max_response_bytes",
        "max_calls",
        "max_retries",
        "parallelism",
        "timeout_seconds",
    ):
        number = result[key]
        if not isinstance(number, int) or isinstance(number, bool):
            raise ExperimentError(f"limit {key} must be an integer")
    if not 1 <= result["max_prompt_bytes"] <= 8192:
        raise ExperimentError("max_prompt_bytes must be between 1 and 8192")
    if not 1 <= result["max_transport_bytes"] <= 8192:
        raise ExperimentError("max_transport_bytes must be between 1 and 8192")
    if not 1 <= result["max_total_bytes"] <= 16384:
        raise ExperimentError("max_total_bytes must be between 1 and 16384")
    if not 1 <= result["max_response_bytes"] <= 65536:
        raise ExperimentError("max_response_bytes must be between 1 and 65536")
    if result["max_calls"] != 1:
        raise ExperimentError("Board 14.1 permits exactly one real call")
    if result["max_retries"] != 0:
        raise ExperimentError("Board 14.1 permits no automatic retry")
    if result["parallelism"] != 1:
        raise ExperimentError("Board 14.1 begins sequentially")
    if not 1 <= result["timeout_seconds"] <= 600:
        raise ExperimentError("timeout_seconds must be between 1 and 600")
    max_total_tokens = result.get("max_total_tokens")
    if max_total_tokens is not None and (
        not isinstance(max_total_tokens, int)
        or isinstance(max_total_tokens, bool)
        or max_total_tokens < 1
    ):
        raise ExperimentError("max_total_tokens must be a positive integer")
    max_total_cost = result.get("max_total_cost")
    if max_total_cost is not None:
        try:
            numeric_cost = Decimal(str(max_total_cost))
        except InvalidOperation as exc:
            raise ExperimentError("max_total_cost must be numeric") from exc
        if not numeric_cost.is_finite() or numeric_cost < 0:
            raise ExperimentError("max_total_cost must be finite and non-negative")
        if not str(result.get("cost_currency", "")).strip():
            raise ExperimentError("max_total_cost requires cost_currency")
        result["max_total_cost"] = str(max_total_cost)
    return result


def _validate_transport(
    value: Any,
    *,
    execution_mode: str,
    manager_model_id: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExperimentError("transport must be an object")
    host_type = str(value.get("host_type", ""))
    allowed = {"synthetic_fake"} if execution_mode == "synthetic_fake" else {
        "cli",
        "codex_app_server",
    }
    if host_type not in allowed:
        raise ExperimentError(
            f"{execution_mode} transport host_type must be one of {sorted(allowed)}"
        )
    command = value.get("command")
    if not isinstance(command, list) or not command or not all(
        isinstance(item, str) and item.strip() for item in command
    ):
        raise ExperimentError("transport command must be a non-empty string array")
    sensitive_flags = {
        "--api-key",
        "--authorization",
        "--bearer",
        "--password",
        "--secret",
        "--token",
    }
    for item in command:
        normalized = item.lower()
        if normalized in sensitive_flags or any(
            normalized.startswith(f"{flag}=") for flag in sensitive_flags
        ):
            raise ExperimentError("transport command contains an inline credential")
    working_directory = _required_text(
        value.get("working_directory"),
        "working directory",
    )
    _reject_excluded_text(working_directory, "working directory")
    model_id = _required_text(value.get("model_id"), "transport Model id")
    if model_id != manager_model_id:
        raise ExperimentError("transport Model must match the Manager binding")
    if value.get("sandbox") != "read-only":
        raise ExperimentError("transport sandbox must be read-only")
    if value.get("approval_policy") not in {"never", "reject"}:
        raise ExperimentError(
            "transport approval_policy must reject interactive escalation"
        )
    disabled = value.get("features_disabled", [])
    if not isinstance(disabled, list) or not all(
        isinstance(item, str) and item for item in disabled
    ):
        raise ExperimentError("features_disabled must be a string array")
    if execution_mode == "real_codex":
        required_disabled = {"plugins", "remote_plugin", "apps"}
        if not required_disabled <= set(disabled):
            raise ExperimentError(
                "real Codex preparation must disable plugins, remote_plugin and apps"
            )
        command_items = set(command)
        if not required_disabled <= command_items:
            raise ExperimentError(
                "real Codex command must explicitly disable plugins, "
                "remote_plugin and apps"
            )
    transport = {
        "host_type": host_type,
        "command": command,
        "working_directory": working_directory,
        "model_id": model_id,
        "sandbox": "read-only",
        "approval_policy": value["approval_policy"],
        "features_disabled": sorted(set(disabled)),
    }
    _reject_excluded_text(_dump(transport), "transport metadata")
    return transport


def _required_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExperimentError(f"{label} cannot be empty")
    return text


def _bounded_text(value: Any, limit: int, label: str) -> str:
    text = _required_text(value, label)
    return text[:limit]


def _reject_excluded_text(value: str, label: str) -> None:
    for pattern in EXCLUDED_PATTERNS:
        if pattern.search(value):
            raise ExperimentError(f"{label} contains excluded private context")


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return sha256(_dump(value).encode("utf-8")).hexdigest()
