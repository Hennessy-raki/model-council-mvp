from __future__ import annotations

import json
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from .adapters import build_adapters
from .config import CouncilConfig
from .ledger import UsageLedger
from .outbound_context import OutboundContextService
from .registry import RegistryService
from .store import CouncilStore, utc_now
from .types import AgentRequest, RunStatus, TaskStatus


BOARD_11_AGENT_FAMILY = "deepseek_responses"
BOARD_11_ROLE = "synthetic_evaluator"
BOARD_11_CAPABILITY = "objective_evaluation"
BOARD_11_CASE_ID = "exact-token-v1"
BOARD_11_EXPECTED_TEXT = "MC-EVAL-ORBIT-42"
BOARD_11_BASE_URL = "https://api.deepseek.com"
BOARD_11_MODEL = "deepseek-v4-flash"
BOARD_11_API_KEY_ENV = "MODEL_COUNCIL_DEEPSEEK_API_KEY"
BOARD_11_TIMEOUT_SECONDS = 30
BOARD_11_MAX_TOTAL_BYTES = 4096
BOARD_11_MAX_RESPONSE_BYTES = 16384


class EvaluationError(RuntimeError):
    pass


class EvaluationService:
    """One-shot, synthetic objective evaluation for the Board 11 candidate."""

    def __init__(self, config: CouncilConfig, store: CouncilStore | None = None):
        self.config = config
        self.store = store or CouncilStore(config.state_dir / "council.db")
        self.registry = RegistryService(self.store)
        self.registry.sync_from_config(config)
        self.adapters = build_adapters(config, self.store)
        self.ledger = UsageLedger(config, self.store, self.registry)
        self.contexts = OutboundContextService(self.store)

    def prepare(self, agent_id: str) -> dict[str, Any]:
        settings = self._candidate_settings(agent_id)
        adapter = self.adapters[agent_id]
        evaluation_id = str(uuid4())
        run_id = self.store.create_run(
            f"Board 11 synthetic evaluation {BOARD_11_CASE_ID}"
        )
        task_id = self.store.add_task(
            run_id=run_id,
            task_key=BOARD_11_CASE_ID,
            title="Objective synthetic instruction-following evaluation",
            instruction=self._instruction(),
            agent=agent_id,
            depends_on=[],
        )
        request = self._request(
            run_id=run_id,
            task_id=task_id,
            agent_id=agent_id,
        )
        prompt = adapter.render_outbound_prompt(request)
        transport_context = adapter.outbound_transport_context()
        expected_bytes = BOARD_11_EXPECTED_TEXT.encode("utf-8")
        specification = {
            "version": 1,
            "agent_family": BOARD_11_AGENT_FAMILY,
            "agent_id": agent_id,
            "role": BOARD_11_ROLE,
            "case_id": BOARD_11_CASE_ID,
            "declared_capability": BOARD_11_CAPABILITY,
            "endpoint": settings["base_url"],
            "model": settings["model"],
            "api_style": settings["api_style"],
            "credential_env": settings["api_key_env"],
            "invoke_enabled": bool(settings.get("invoke_enabled", False)),
            "expected_sha256": sha256(expected_bytes).hexdigest(),
            "expected_bytes": len(expected_bytes),
            "max_duration_ms": BOARD_11_TIMEOUT_SECONDS * 1000,
            "max_files": 0,
            "max_artifacts": 0,
            "max_artifact_bytes": 0,
            "max_total_bytes": BOARD_11_MAX_TOTAL_BYTES,
            "max_response_bytes": BOARD_11_MAX_RESPONSE_BYTES,
            "comparison_baseline": "deterministic_local_oracle",
        }
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO evaluation_runs(
                    id, run_id, agent_id, agent_family, role, case_id,
                    status, specification_json, created_at, completed_at, error
                ) VALUES (?, ?, ?, ?, ?, ?, 'prepared', ?, ?, NULL, NULL)
                """,
                (
                    evaluation_id,
                    run_id,
                    agent_id,
                    BOARD_11_AGENT_FAMILY,
                    BOARD_11_ROLE,
                    BOARD_11_CASE_ID,
                    json.dumps(specification, ensure_ascii=False, sort_keys=True),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO evaluation_cases(
                    id, evaluation_id, case_id, outbound_manifest_id,
                    expected_sha256, expected_bytes, response_sha256,
                    response_bytes, status, assertions_json, ledger_event_id,
                    failure_class, created_at, completed_at
                ) VALUES (?, ?, ?, NULL, ?, ?, NULL, NULL, 'prepared', '{}',
                    NULL, NULL, ?, NULL)
                """,
                (
                    task_id,
                    evaluation_id,
                    BOARD_11_CASE_ID,
                    specification["expected_sha256"],
                    specification["expected_bytes"],
                    now,
                ),
            )
        manifest = self.contexts.prepare(
            endpoint_id=adapter.endpoint_id,
            agent_id=agent_id,
            request=request,
            prompt=prompt,
            source=adapter.outbound_source,
            policy=adapter.outbound_policy,
            transport_context=transport_context,
        )
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE evaluation_cases
                SET outbound_manifest_id = ?
                WHERE id = ? AND evaluation_id = ?
                """,
                (manifest["id"], task_id, evaluation_id),
            )
        return self.snapshot(evaluation_id)

    def run(self, evaluation_id: str, manifest_id: str) -> dict[str, Any]:
        evaluation, case = self._rows(evaluation_id)
        if evaluation["status"] != "prepared":
            raise EvaluationError(
                f"evaluation {evaluation_id!r} is not prepared"
            )
        if case["outbound_manifest_id"] != manifest_id:
            raise EvaluationError(
                "evaluation run requires its exact prepared outbound manifest"
            )
        manifest = self.contexts.manifest(manifest_id)
        if manifest["status"] != "approved":
            raise EvaluationError(
                f"outbound context manifest {manifest_id!r} is not approved"
            )
        agent_id = str(evaluation["agent_id"])
        settings = self._candidate_settings(agent_id)
        if not bool(settings.get("invoke_enabled", False)):
            raise EvaluationError(
                f"evaluation candidate {agent_id!r} requires invoke_enabled=true"
            )
        request = self._request(
            run_id=str(evaluation["run_id"]),
            task_id=str(case["id"]),
            agent_id=agent_id,
            manifest_id=manifest_id,
        )
        self.store.set_task_status(str(case["id"]), TaskStatus.RUNNING)
        try:
            response = self.ledger.invoke(
                agent_id,
                self.adapters[agent_id],
                request,
            )
        except Exception as exc:
            self._finish_failure(
                evaluation=evaluation,
                case=case,
                failure_class=type(exc).__name__,
            )
            raise

        response_bytes = response.content.encode("utf-8")
        response_sha256 = sha256(response_bytes).hexdigest()
        ledger_id = str(response.metadata["ledger"]["event_id"])
        ledger_event = self._ledger_event(ledger_id)
        assertions = {
            "exact_text": response.content == BOARD_11_EXPECTED_TEXT,
            "exact_sha256": response_sha256 == case["expected_sha256"],
            "exact_bytes": len(response_bytes) == int(case["expected_bytes"]),
            "within_duration_limit": (
                int(ledger_event["duration_ms"])
                <= BOARD_11_TIMEOUT_SECONDS * 1000
            ),
            "zero_files": True,
            "zero_artifacts": not request.artifacts,
            "single_call": self._call_count(str(evaluation["run_id"]), agent_id) == 1,
            "ledger_recorded": True,
        }
        passed = all(assertions.values())
        status = "passed" if passed else "failed"
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE evaluation_cases
                SET response_sha256 = ?, response_bytes = ?, status = ?,
                    assertions_json = ?, ledger_event_id = ?,
                    failure_class = ?, completed_at = ?
                WHERE id = ? AND evaluation_id = ?
                """,
                (
                    response_sha256,
                    len(response_bytes),
                    status,
                    json.dumps(assertions, ensure_ascii=False, sort_keys=True),
                    ledger_id,
                    None if passed else "objective_assertion_failed",
                    now,
                    case["id"],
                    evaluation_id,
                ),
            )
            conn.execute(
                """
                UPDATE evaluation_runs
                SET status = ?, completed_at = ?, error = ?
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    None if passed else "objective_assertion_failed",
                    evaluation_id,
                ),
            )
        self.store.set_task_status(
            str(case["id"]),
            TaskStatus.COMPLETED if passed else TaskStatus.FAILED,
            error=None if passed else "objective_assertion_failed",
        )
        self.store.finish_run(
            str(evaluation["run_id"]),
            RunStatus.COMPLETED if passed else RunStatus.FAILED,
            error=None if passed else "objective_assertion_failed",
        )
        return self.snapshot(evaluation_id)

    def snapshot(self, evaluation_id: str) -> dict[str, Any]:
        evaluation, case = self._rows(evaluation_id)
        result = dict(evaluation)
        result["specification"] = json.loads(result.pop("specification_json"))
        case_result = dict(case)
        case_result["assertions"] = json.loads(
            case_result.pop("assertions_json")
        )
        manifest_id = case_result["outbound_manifest_id"]
        case_result["outbound_context"] = (
            self.contexts.manifest(str(manifest_id))
            if manifest_id
            else None
        )
        result["case"] = case_result
        return result

    def evaluations(
        self,
        *,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        where = []
        params: list[Any] = []
        if agent_id:
            where.append("agent_id = ?")
            params.append(agent_id)
        if status:
            if status not in {"prepared", "passed", "failed"}:
                raise ValueError(f"unsupported evaluation status {status!r}")
            where.append("status = ?")
            params.append(status)
        query = "SELECT id FROM evaluation_runs"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY created_at DESC, id DESC"
        with self.store.connect() as conn:
            ids = [str(row["id"]) for row in conn.execute(query, params)]
        return [self.snapshot(item) for item in ids]

    def _candidate_settings(self, agent_id: str) -> dict[str, Any]:
        candidates = [
            item_id
            for item_id, item in self.config.agents.items()
            if item.get("type") == "openai_compatible"
        ]
        if candidates != [agent_id]:
            raise EvaluationError(
                "Board 11 requires exactly one configured openai_compatible "
                f"candidate; found {candidates!r}"
            )
        settings = self.config.agents[agent_id]
        if str(settings.get("role")) != BOARD_11_ROLE:
            raise EvaluationError(
                f"Board 11 candidate role must be {BOARD_11_ROLE!r}"
            )
        capabilities = {
            str(item) for item in settings.get("capabilities", [])
        }
        if BOARD_11_CAPABILITY not in capabilities:
            raise EvaluationError(
                f"Board 11 candidate requires capability "
                f"{BOARD_11_CAPABILITY!r}"
            )
        if str(settings.get("api_style")) != "responses":
            raise EvaluationError("Board 11 candidate requires api_style=responses")
        base_url = str(settings.get("base_url", "")).rstrip("/")
        if base_url != BOARD_11_BASE_URL and not _is_loopback_url(base_url):
            raise EvaluationError(
                f"Board 11 candidate endpoint must be {BOARD_11_BASE_URL!r} "
                "or a loopback fake server"
            )
        if str(settings.get("model")) != BOARD_11_MODEL:
            raise EvaluationError(
                f"Board 11 candidate model must be {BOARD_11_MODEL!r}"
            )
        if str(settings.get("api_key_env")) != BOARD_11_API_KEY_ENV:
            raise EvaluationError(
                f"Board 11 credential environment variable must be "
                f"{BOARD_11_API_KEY_ENV!r}"
            )
        if int(settings.get("timeout_seconds", 0)) != BOARD_11_TIMEOUT_SECONDS:
            raise EvaluationError(
                f"Board 11 timeout must be {BOARD_11_TIMEOUT_SECONDS} seconds"
            )
        if (
            int(settings.get("max_response_bytes", 0))
            != BOARD_11_MAX_RESPONSE_BYTES
        ):
            raise EvaluationError(
                "Board 11 max_response_bytes must be "
                f"{BOARD_11_MAX_RESPONSE_BYTES}"
            )
        policy = settings.get("outbound_context", {})
        expected_policy = {
            "source": "synthetic",
            "allowed_sources": ["synthetic"],
            "max_files": 0,
            "max_total_bytes": BOARD_11_MAX_TOTAL_BYTES,
            "max_artifacts": 0,
            "max_artifact_bytes": 0,
        }
        for key, expected in expected_policy.items():
            if policy.get(key) != expected:
                raise EvaluationError(
                    f"Board 11 outbound_context.{key} must be {expected!r}"
                )
        return settings

    @staticmethod
    def _instruction() -> str:
        return (
            "Return exactly the following ASCII token and nothing else: "
            f"{BOARD_11_EXPECTED_TEXT}"
        )

    def _request(
        self,
        *,
        run_id: str,
        task_id: str,
        agent_id: str,
        manifest_id: str | None = None,
    ) -> AgentRequest:
        metadata = {}
        if manifest_id:
            metadata["outbound_context_manifest_id"] = manifest_id
        return AgentRequest(
            run_id=run_id,
            task_id=task_id,
            mode="evaluation",
            goal="Complete one project-neutral synthetic instruction check.",
            instruction=self._instruction(),
            sender="local_evaluation_control",
            recipient=agent_id,
            context="No repository, file, Artifact, repair or workspace context.",
            artifacts=[],
            metadata=metadata,
        )

    def _rows(self, evaluation_id: str):
        with self.store.connect() as conn:
            evaluation = conn.execute(
                "SELECT * FROM evaluation_runs WHERE id = ?",
                (evaluation_id,),
            ).fetchone()
            case = conn.execute(
                """
                SELECT * FROM evaluation_cases
                WHERE evaluation_id = ? AND case_id = ?
                """,
                (evaluation_id, BOARD_11_CASE_ID),
            ).fetchone()
        if evaluation is None or case is None:
            raise EvaluationError(f"evaluation {evaluation_id!r} not found")
        return evaluation, case

    def _ledger_event(self, event_id: str):
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM usage_events WHERE id = ?",
                (event_id,),
            ).fetchone()
        if row is None:
            raise EvaluationError(
                f"usage event {event_id!r} was not persisted"
            )
        return row

    def _call_count(self, run_id: str, agent_id: str) -> int:
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM usage_events
                WHERE run_id = ? AND agent_id = ?
                """,
                (run_id, agent_id),
            ).fetchone()
        return int(row["count"])

    def _finish_failure(
        self,
        *,
        evaluation,
        case,
        failure_class: str,
    ) -> None:
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE evaluation_cases
                SET status = 'failed', failure_class = ?, completed_at = ?
                WHERE id = ? AND evaluation_id = ?
                """,
                (failure_class, now, case["id"], evaluation["id"]),
            )
            conn.execute(
                """
                UPDATE evaluation_runs
                SET status = 'failed', completed_at = ?, error = ?
                WHERE id = ?
                """,
                (now, failure_class, evaluation["id"]),
            )
        self.store.set_task_status(
            str(case["id"]),
            TaskStatus.FAILED,
            error=failure_class,
        )
        self.store.finish_run(
            str(evaluation["run_id"]),
            RunStatus.FAILED,
            error=failure_class,
        )


def _is_loopback_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    )
