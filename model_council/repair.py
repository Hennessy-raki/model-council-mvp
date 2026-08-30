from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .registry import sanitize_for_storage
from .store import CouncilStore, utc_now
from .types import AgentResponse
from .workspaces import MAX_DIFF_BYTES, WorkspaceError, WorkspaceService


SESSION_STATUSES = {
    "waiting_writer",
    "writer_running",
    "waiting_review",
    "reviewer_running",
    "accepted",
    "limit_reached",
    "recovery_required",
    "failed",
    "cancelled",
}
ITERATION_STATUSES = {
    "writer_running",
    "writer_interrupted",
    "evidence_ready",
    "reviewer_running",
    "reviewer_interrupted",
    "repair_requested",
    "accepted",
    "limit_reached",
    "failed",
}
TERMINAL_SESSION_STATUSES = {
    "accepted",
    "limit_reached",
    "failed",
    "cancelled",
}
MAX_REPAIR_ITERATIONS = 20
MAX_REPAIR_SECONDS = 86_400
MAX_REPAIR_FILES = 1_000
MAX_FEEDBACK_BYTES = 64_000
MAX_EVENT_BYTES = 32_000


class RepairError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepairPolicy:
    max_iterations: int = 3
    max_elapsed_seconds: int = 1_800
    max_changed_files: int = 50
    max_diff_bytes: int = MAX_DIFF_BYTES
    max_feedback_bytes: int = 16_000
    max_total_tokens: int | None = None
    max_total_cost: str | None = None
    cost_currency: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.max_iterations <= MAX_REPAIR_ITERATIONS:
            raise ValueError(
                f"max_iterations must be between 1 and {MAX_REPAIR_ITERATIONS}"
            )
        if not 1 <= self.max_elapsed_seconds <= MAX_REPAIR_SECONDS:
            raise ValueError(
                "max_elapsed_seconds must be between 1 and "
                f"{MAX_REPAIR_SECONDS}"
            )
        if not 1 <= self.max_changed_files <= MAX_REPAIR_FILES:
            raise ValueError(
                f"max_changed_files must be between 1 and {MAX_REPAIR_FILES}"
            )
        if not 1 <= self.max_diff_bytes <= MAX_DIFF_BYTES:
            raise ValueError(
                f"max_diff_bytes must be between 1 and {MAX_DIFF_BYTES}"
            )
        if not 1 <= self.max_feedback_bytes <= MAX_FEEDBACK_BYTES:
            raise ValueError(
                f"max_feedback_bytes must be between 1 and {MAX_FEEDBACK_BYTES}"
            )
        if self.max_total_tokens is not None and self.max_total_tokens < 1:
            raise ValueError("max_total_tokens must be positive")
        if self.max_total_cost is None:
            if self.cost_currency is not None:
                raise ValueError(
                    "cost_currency requires max_total_cost"
                )
        else:
            amount = _decimal(self.max_total_cost, "max_total_cost")
            if amount < 0:
                raise ValueError("max_total_cost must be non-negative")
            if not self.cost_currency or not self.cost_currency.strip():
                raise ValueError(
                    "cost_currency is required with max_total_cost"
                )

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_elapsed_seconds": self.max_elapsed_seconds,
            "max_changed_files": self.max_changed_files,
            "max_diff_bytes": self.max_diff_bytes,
            "max_feedback_bytes": self.max_feedback_bytes,
            "max_total_tokens": self.max_total_tokens,
            "max_total_cost": self.max_total_cost,
            "cost_currency": self.cost_currency,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RepairPolicy:
        return cls(**value)


WriterCallback = Callable[[dict[str, Any]], Any]
ReviewerCallback = Callable[[dict[str, Any]], Any]


class RepairService:
    """Bounded, persistent reviewer-writer iterations over a Board 9 lease."""

    def __init__(
        self,
        store: CouncilStore,
        workspaces: WorkspaceService | None = None,
    ):
        self.store = store
        self.workspaces = workspaces or WorkspaceService(store)

    def start(
        self,
        *,
        lease_id: str,
        writer_agent_id: str,
        reviewer_agent_id: str,
        goal: str,
        test_command: list[str],
        policy: RepairPolicy | None = None,
    ) -> dict[str, Any]:
        clean_goal = goal.strip()
        if not clean_goal:
            raise ValueError("repair goal cannot be empty")
        if not writer_agent_id.strip() or not reviewer_agent_id.strip():
            raise ValueError("writer and reviewer agent IDs cannot be empty")
        if writer_agent_id == reviewer_agent_id:
            raise ValueError("writer and reviewer must be distinct Agents")
        workspace = self.workspaces.workspace(lease_id)
        if workspace["status"] != "active":
            raise RepairError("repair session requires an active worktree lease")
        if workspace["agent_id"] != writer_agent_id:
            raise RepairError("repair writer must own the worktree lease")
        for permission in ("read", "write", "test"):
            if not workspace["permissions"][permission]:
                raise RepairError(
                    f"repair session requires {permission} permission"
                )
        state = self.workspaces.git_state(lease_id)
        if not state["clean"]:
            raise RepairError("repair session must start from a clean worktree")
        command = self.workspaces._validate_command(test_command)
        active = self.sessions(lease_id=lease_id, active_only=True)
        if active:
            raise RepairError(
                f"worktree lease already has active repair session {active[0]['id']}"
            )
        session_id = str(uuid4())
        now = utc_now()
        policy = policy or RepairPolicy()
        empty_digest = sha256(b"").hexdigest()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO repair_sessions(
                    id, lease_id, writer_agent_id, reviewer_agent_id, goal,
                    status, policy_json, test_command_json, iteration_count,
                    total_tokens, total_tokens_known, total_cost,
                    total_cost_known, cost_currency, accepted_head_sha,
                    last_feedback_text, last_feedback_sha256, created_at,
                    updated_at, completed_at, error
                ) VALUES (
                    ?, ?, ?, ?, ?, 'waiting_writer', ?, ?, 0,
                    0, 1, '0', 1, ?, NULL, '', ?, ?, ?, NULL, NULL
                )
                """,
                (
                    session_id,
                    lease_id,
                    writer_agent_id,
                    reviewer_agent_id,
                    clean_goal,
                    _raw_json(policy.as_dict()),
                    _raw_json(command),
                    policy.cost_currency,
                    empty_digest,
                    now,
                    now,
                ),
            )
        self._event(
            session_id,
            None,
            "session_started",
            {
                "lease_id": lease_id,
                "writer_agent_id": writer_agent_id,
                "reviewer_agent_id": reviewer_agent_id,
                "policy": policy.as_dict(),
                "initial_head_sha": state["head_sha"],
            },
        )
        return self.session(session_id)

    def sessions(
        self,
        *,
        status: str | None = None,
        lease_id: str | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        where = []
        params: list[Any] = []
        if status:
            if status not in SESSION_STATUSES:
                raise ValueError(f"unsupported repair status {status!r}")
            where.append("status = ?")
            params.append(status)
        if lease_id:
            where.append("lease_id = ?")
            params.append(lease_id)
        if active_only:
            placeholders = ", ".join(
                "?" for _ in TERMINAL_SESSION_STATUSES
            )
            where.append(f"status NOT IN ({placeholders})")
            params.extend(sorted(TERMINAL_SESSION_STATUSES))
        query = "SELECT * FROM repair_sessions"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY updated_at DESC, id DESC"
        with self.store.connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._session_row(row) for row in rows]

    def session(self, session_id: str) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM repair_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"repair session {session_id!r} not found")
        return self._session_row(row)

    def iterations(self, session_id: str) -> list[dict[str, Any]]:
        self.session(session_id)
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM repair_iterations
                WHERE session_id = ?
                ORDER BY iteration_number, id
                """,
                (session_id,),
            ).fetchall()
        return [self._iteration_row(row) for row in rows]

    def events(self, session_id: str) -> list[dict[str, Any]]:
        self.session(session_id)
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM repair_events
                WHERE session_id = ?
                ORDER BY created_at, id
                """,
                (session_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def snapshot(self, session_id: str) -> dict[str, Any]:
        return {
            "session": self.session(session_id),
            "iterations": self.iterations(session_id),
            "events": self.events(session_id),
        }

    def begin_iteration(self, session_id: str) -> dict[str, Any]:
        session = self.session(session_id)
        if session["status"] != "waiting_writer":
            raise RepairError(
                f"repair session is {session['status']!r}, not waiting_writer"
            )
        reason = self._preflight_call(session)
        if reason:
            self._limit_session(session_id, reason)
            return self.session(session_id)
        policy = RepairPolicy.from_dict(session["policy"])
        if session["iteration_count"] >= policy.max_iterations:
            self._limit_session(session_id, "maximum iteration count reached")
            return self.session(session_id)
        state = self.workspaces.git_state(session["lease_id"])
        if not state["clean"]:
            raise RepairError(
                "worktree became dirty before writer iteration; inspect and "
                "restore a clean checkpoint before retrying"
            )
        number = session["iteration_count"] + 1
        iteration_id = str(uuid4())
        now = utc_now()
        empty_digest = sha256(b"").hexdigest()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO repair_iterations(
                    id, session_id, iteration_number, status,
                    source_head_sha, checkpoint_head_sha,
                    writer_output_sha256, writer_output_bytes,
                    writer_metadata_json, test_evidence_id,
                    diff_evidence_id, changed_files_json,
                    changed_file_count, reviewer_decision,
                    reviewer_feedback_text, reviewer_feedback_sha256,
                    reviewer_metadata_json, writer_started_at,
                    evidence_captured_at, review_started_at, reviewed_at, error
                ) VALUES (
                    ?, ?, ?, 'writer_running', ?, NULL, NULL, NULL,
                    '{}', NULL, NULL, '[]', NULL, NULL, '', ?, '{}',
                    ?, NULL, NULL, NULL, NULL
                )
                """,
                (
                    iteration_id,
                    session_id,
                    number,
                    state["head_sha"],
                    empty_digest,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE repair_sessions
                SET status = 'writer_running', iteration_count = ?,
                    updated_at = ?, error = NULL
                WHERE id = ?
                """,
                (number, now, session_id),
            )
        self._event(
            session_id,
            iteration_id,
            "writer_started",
            {
                "iteration_number": number,
                "source_head_sha": state["head_sha"],
            },
        )
        return self._latest_iteration(session_id)

    def writer_context(self, session_id: str) -> dict[str, Any]:
        session = self.session(session_id)
        if session["status"] != "writer_running":
            raise RepairError("writer context requires writer_running state")
        iteration = self._latest_iteration(session_id)
        path = self.workspaces.authorized_path(
            session["lease_id"],
            agent_id=session["writer_agent_id"],
            permission="write",
        )
        return {
            "session_id": session_id,
            "iteration_id": iteration["id"],
            "iteration_number": iteration["iteration_number"],
            "goal": session["goal"],
            "feedback": session["last_feedback_text"],
            "worktree_path": str(path),
            "policy": session["policy"],
        }

    def capture_iteration(
        self,
        session_id: str,
        *,
        writer_result: Any = None,
        recovered: bool = False,
    ) -> dict[str, Any]:
        session = self.session(session_id)
        if session["status"] != "writer_running":
            raise RepairError("capture requires writer_running state")
        iteration = self._latest_iteration(session_id)
        if iteration["status"] not in {"writer_running", "writer_interrupted"}:
            raise RepairError("latest iteration is not awaiting writer capture")
        try:
            before = self.workspaces.git_state(session["lease_id"])
            if not before["clean"]:
                checkpoint = self.workspaces.checkpoint(
                    session["lease_id"],
                    message=(
                        "Repair iteration "
                        f"{iteration['iteration_number']} checkpoint"
                    ),
                )
                checkpoint_head = str(checkpoint["metadata"]["head_sha"])
            elif before["head_sha"] != iteration["source_head_sha"]:
                checkpoint_head = str(before["head_sha"])
            else:
                raise RepairError("writer iteration produced no Git change")
            after = self.workspaces.git_state(session["lease_id"])
            if not after["clean"] or after["head_sha"] != checkpoint_head:
                raise RepairError("writer checkpoint did not produce a clean state")
            test = self.workspaces.run_test(
                session["lease_id"],
                command=session["test_command"],
                timeout_seconds=min(
                    600,
                    RepairPolicy.from_dict(
                        session["policy"]
                    ).max_elapsed_seconds,
                ),
            )
            diff = self.workspaces.collect_diff(session["lease_id"])
            inventory = self.workspaces.change_inventory(
                session["lease_id"],
                max_files=1_000_000,
            )
        except Exception as exc:
            self._require_recovery(
                session_id,
                iteration["id"],
                f"capture failed: {type(exc).__name__}: {str(exc)[:1000]}",
            )
            raise

        content, metadata = _normalize_response(writer_result)
        policy = RepairPolicy.from_dict(session["policy"])
        limit_reason = None
        if inventory["file_count"] > policy.max_changed_files:
            limit_reason = (
                f"changed file count {inventory['file_count']} exceeds "
                f"{policy.max_changed_files}"
            )
        elif diff["stdout_bytes"] > policy.max_diff_bytes:
            limit_reason = (
                f"diff size {diff['stdout_bytes']} exceeds "
                f"{policy.max_diff_bytes} bytes"
            )
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE repair_iterations
                SET status = 'failed', error = 'cancelled by local operator'
                WHERE session_id = ?
                  AND status IN (
                    'writer_running', 'writer_interrupted',
                    'evidence_ready', 'reviewer_running',
                    'reviewer_interrupted'
                  )
                """,
                (session_id,),
            )
            conn.execute(
                """
                UPDATE repair_iterations
                SET status = ?, checkpoint_head_sha = ?,
                    writer_output_sha256 = ?, writer_output_bytes = ?,
                    writer_metadata_json = ?, test_evidence_id = ?,
                    diff_evidence_id = ?, changed_files_json = ?,
                    changed_file_count = ?, evidence_captured_at = ?,
                    error = ?
                WHERE id = ?
                """,
                (
                    "limit_reached" if limit_reason else "evidence_ready",
                    checkpoint_head,
                    sha256(content.encode("utf-8")).hexdigest(),
                    len(content.encode("utf-8")),
                    _dump(metadata),
                    test["id"],
                    diff["id"],
                    _raw_json(inventory["files"]),
                    inventory["file_count"],
                    now,
                    limit_reason,
                    iteration["id"],
                ),
            )
            conn.execute(
                """
                UPDATE repair_sessions
                SET status = ?, updated_at = ?, error = ?
                WHERE id = ?
                """,
                (
                    "limit_reached" if limit_reason else "waiting_review",
                    now,
                    limit_reason,
                    session_id,
                ),
            )
        self._apply_usage(session_id, metadata)
        self._event(
            session_id,
            iteration["id"],
            "evidence_captured",
            {
                "checkpoint_head_sha": checkpoint_head,
                "test_evidence_id": test["id"],
                "test_status": test["status"],
                "diff_evidence_id": diff["id"],
                "diff_bytes": diff["stdout_bytes"],
                "changed_file_count": inventory["file_count"],
                "recovered": recovered,
                "limit_reason": limit_reason,
            },
        )
        if limit_reason:
            self._finish_if_terminal(session_id)
        return self.snapshot(session_id)

    def begin_review(self, session_id: str) -> dict[str, Any]:
        session = self.session(session_id)
        if session["status"] != "waiting_review":
            raise RepairError("review requires waiting_review state")
        reason = self._preflight_call(session)
        if reason:
            self._limit_session(session_id, reason)
            return self.snapshot(session_id)
        iteration = self._latest_iteration(session_id)
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE repair_iterations
                SET status = 'reviewer_running', review_started_at = ?
                WHERE id = ? AND status = 'evidence_ready'
                """,
                (now, iteration["id"]),
            )
            conn.execute(
                """
                UPDATE repair_sessions
                SET status = 'reviewer_running', updated_at = ?
                WHERE id = ?
                """,
                (now, session_id),
            )
        self._event(
            session_id,
            iteration["id"],
            "reviewer_started",
            {"iteration_number": iteration["iteration_number"]},
        )
        return self.review_bundle(session_id)

    def review_bundle(self, session_id: str) -> dict[str, Any]:
        session = self.session(session_id)
        if session["status"] not in {"waiting_review", "reviewer_running"}:
            raise RepairError("review bundle requires review state")
        iteration = self._latest_iteration(session_id)
        test = self._evidence(iteration["test_evidence_id"])
        diff = self._evidence(iteration["diff_evidence_id"])
        return {
            "session_id": session_id,
            "iteration_id": iteration["id"],
            "iteration_number": iteration["iteration_number"],
            "goal": session["goal"],
            "prior_feedback": session["last_feedback_text"],
            "checkpoint_head_sha": iteration["checkpoint_head_sha"],
            "changed_files": iteration["changed_files"],
            "test": {
                "status": test["status"],
                "exit_code": test["exit_code"],
                "stdout_text": test["stdout_text"],
                "stderr_text": test["stderr_text"],
                "stdout_sha256": test["stdout_sha256"],
                "stderr_sha256": test["stderr_sha256"],
            },
            "diff": {
                "stdout_text": diff["stdout_text"],
                "stdout_bytes": diff["stdout_bytes"],
                "stdout_sha256": diff["stdout_sha256"],
                "truncated": diff["metadata"]["stdout_truncated"],
            },
            "policy": session["policy"],
        }

    def submit_review(
        self,
        session_id: str,
        *,
        decision: str,
        feedback: str,
        reviewer_result: Any = None,
    ) -> dict[str, Any]:
        session = self.session(session_id)
        if decision not in {"accept", "repair"}:
            raise ValueError("review decision must be accept or repair")
        content, metadata = _normalize_response(reviewer_result)
        clean_feedback = feedback.strip()
        if content and not clean_feedback:
            clean_feedback = content.strip()
        policy = RepairPolicy.from_dict(session["policy"])
        feedback_bytes = clean_feedback.encode("utf-8")
        if len(feedback_bytes) > policy.max_feedback_bytes:
            raise RepairError(
                f"review feedback exceeds {policy.max_feedback_bytes} bytes"
            )
        if session["status"] == "waiting_review":
            self.begin_review(session_id)
            session = self.session(session_id)
        if session["status"] != "reviewer_running":
            return self.snapshot(session_id)
        iteration = self._latest_iteration(session_id)
        test = self._evidence(iteration["test_evidence_id"])
        self._apply_usage(session_id, metadata)
        if decision == "accept" and test["status"] != "passed":
            self._reset_review_after_invalid_decision(
                session_id,
                iteration["id"],
                "reviewer cannot accept an iteration with failing tests",
            )
            raise RepairError(
                "reviewer cannot accept an iteration with failing tests"
            )
        session = self.session(session_id)
        budget_reason = self._budget_violation(session, for_next_call=False)
        now = utc_now()
        if decision == "accept":
            iteration_status = "accepted"
            session_status = "accepted"
            accepted_head = iteration["checkpoint_head_sha"]
            error = None
        elif session["iteration_count"] >= policy.max_iterations:
            iteration_status = "limit_reached"
            session_status = "limit_reached"
            accepted_head = None
            error = "maximum iteration count reached after reviewer requested repair"
        elif budget_reason:
            iteration_status = "limit_reached"
            session_status = "limit_reached"
            accepted_head = None
            error = budget_reason
        else:
            iteration_status = "repair_requested"
            session_status = "waiting_writer"
            accepted_head = None
            error = None
        feedback_digest = sha256(feedback_bytes).hexdigest()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE repair_iterations
                SET status = ?, reviewer_decision = ?,
                    reviewer_feedback_text = ?,
                    reviewer_feedback_sha256 = ?,
                    reviewer_metadata_json = ?, reviewed_at = ?, error = ?
                WHERE id = ?
                """,
                (
                    iteration_status,
                    decision,
                    clean_feedback,
                    feedback_digest,
                    _dump(metadata),
                    now,
                    error,
                    iteration["id"],
                ),
            )
            conn.execute(
                """
                UPDATE repair_sessions
                SET status = ?, accepted_head_sha = ?,
                    last_feedback_text = ?, last_feedback_sha256 = ?,
                    updated_at = ?, completed_at = ?, error = ?
                WHERE id = ?
                """,
                (
                    session_status,
                    accepted_head,
                    clean_feedback,
                    feedback_digest,
                    now,
                    now if session_status in TERMINAL_SESSION_STATUSES else None,
                    error,
                    session_id,
                ),
            )
        self._event(
            session_id,
            iteration["id"],
            "review_recorded",
            {
                "decision": decision,
                "feedback_sha256": feedback_digest,
                "feedback_bytes": len(feedback_bytes),
                "next_status": session_status,
                "error": error,
            },
        )
        return self.snapshot(session_id)

    def run_local_until_terminal(
        self,
        session_id: str,
        *,
        writer: WriterCallback,
        reviewer: ReviewerCallback,
    ) -> dict[str, Any]:
        """Drive injected local callbacks; no Adapter or network is invoked."""
        while True:
            session = self.session(session_id)
            if session["status"] in TERMINAL_SESSION_STATUSES:
                return self.snapshot(session_id)
            if session["status"] == "waiting_writer":
                iteration = self.begin_iteration(session_id)
                if "iteration_number" not in iteration:
                    return self.snapshot(session_id)
                try:
                    writer_result = writer(self.writer_context(session_id))
                except Exception as exc:
                    self._interrupt(
                        session_id,
                        iteration["id"],
                        phase="writer",
                        exc=exc,
                    )
                    return self.snapshot(session_id)
                try:
                    self.capture_iteration(
                        session_id,
                        writer_result=writer_result,
                    )
                except Exception:
                    return self.snapshot(session_id)
                continue
            if session["status"] == "waiting_review":
                bundle = self.begin_review(session_id)
                if self.session(session_id)["status"] != "reviewer_running":
                    return self.snapshot(session_id)
                try:
                    review_result = reviewer(bundle)
                    decision, feedback, metadata = _normalize_review(
                        review_result
                    )
                except Exception as exc:
                    self._interrupt(
                        session_id,
                        self._latest_iteration(session_id)["id"],
                        phase="reviewer",
                        exc=exc,
                    )
                    return self.snapshot(session_id)
                self.submit_review(
                    session_id,
                    decision=decision,
                    feedback=feedback,
                    reviewer_result={"metadata": metadata},
                )
                continue
            return self.snapshot(session_id)

    def recover(
        self,
        session_id: str,
        *,
        action: str = "inspect",
    ) -> dict[str, Any]:
        if action not in {"inspect", "retry", "capture", "fail"}:
            raise ValueError(
                "recovery action must be inspect, retry, capture or fail"
            )
        session = self.session(session_id)
        if session["status"] not in {
            "writer_running",
            "reviewer_running",
            "recovery_required",
        }:
            raise RepairError(
                f"repair session {session_id!r} does not require recovery"
            )
        iteration = self._latest_iteration(session_id)
        writer_phase = iteration["status"] in {
            "writer_running",
            "writer_interrupted",
        }
        reviewer_phase = iteration["status"] in {
            "reviewer_running",
            "reviewer_interrupted",
        }
        state = self.workspaces.git_state(session["lease_id"])
        can_retry = (
            writer_phase
            and state["clean"]
            and state["head_sha"] == iteration["source_head_sha"]
        ) or reviewer_phase
        can_capture = writer_phase and (
            not state["clean"]
            or state["head_sha"] != iteration["source_head_sha"]
        )
        inspection = {
            "session_id": session_id,
            "phase": "writer" if writer_phase else "reviewer",
            "worktree_state": state,
            "can_retry": can_retry,
            "can_capture": can_capture,
            "can_fail": True,
        }
        if action == "inspect":
            return inspection
        if action == "retry":
            if not can_retry:
                raise RepairError(
                    "retry is allowed only before writer changes or for "
                    "captured reviewer evidence"
                )
            now = utc_now()
            with self.store.connect() as conn:
                if writer_phase:
                    conn.execute(
                        """
                        UPDATE repair_iterations
                        SET status = 'failed', error = ? WHERE id = ?
                        """,
                        ("interrupted writer attempt released for retry", iteration["id"]),
                    )
                    next_status = "waiting_writer"
                else:
                    conn.execute(
                        """
                        UPDATE repair_iterations
                        SET status = 'evidence_ready', error = NULL
                        WHERE id = ?
                        """,
                        (iteration["id"],),
                    )
                    next_status = "waiting_review"
                conn.execute(
                    """
                    UPDATE repair_sessions
                    SET status = ?, updated_at = ?, error = NULL WHERE id = ?
                    """,
                    (next_status, now, session_id),
                )
            self._event(
                session_id,
                iteration["id"],
                "recovery_retry",
                {"next_status": next_status},
            )
            return self.snapshot(session_id)
        if action == "capture":
            if not can_capture:
                raise RepairError(
                    "capture recovery requires writer changes to preserve"
                )
            with self.store.connect() as conn:
                conn.execute(
                    """
                    UPDATE repair_iterations
                    SET status = 'writer_running', error = NULL WHERE id = ?
                    """,
                    (iteration["id"],),
                )
                conn.execute(
                    """
                    UPDATE repair_sessions
                    SET status = 'writer_running', updated_at = ?, error = NULL
                    WHERE id = ?
                    """,
                    (utc_now(), session_id),
                )
            return self.capture_iteration(
                session_id,
                recovered=True,
            )
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE repair_iterations
                SET status = 'failed', error = ? WHERE id = ?
                """,
                ("operator terminated interrupted iteration", iteration["id"]),
            )
            conn.execute(
                """
                UPDATE repair_sessions
                SET status = 'failed', updated_at = ?, completed_at = ?,
                    error = ?
                WHERE id = ?
                """,
                (
                    now,
                    now,
                    "operator terminated interrupted repair session",
                    session_id,
                ),
            )
        self._event(
            session_id,
            iteration["id"],
            "recovery_failed",
            {},
        )
        return self.snapshot(session_id)

    def cancel(self, session_id: str) -> dict[str, Any]:
        session = self.session(session_id)
        if session["status"] in TERMINAL_SESSION_STATUSES:
            raise RepairError("terminal repair session cannot be cancelled")
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE repair_sessions
                SET status = 'cancelled', updated_at = ?, completed_at = ?,
                    error = 'cancelled by local operator'
                WHERE id = ?
                """,
                (now, now, session_id),
            )
        self._event(session_id, None, "session_cancelled", {})
        return self.snapshot(session_id)

    def request_merge(self, session_id: str) -> dict[str, Any]:
        session = self.session(session_id)
        if session["status"] != "accepted":
            raise RepairError("merge approval requires an accepted repair session")
        state = self.workspaces.git_state(session["lease_id"])
        if (
            not state["clean"]
            or state["head_sha"] != session["accepted_head_sha"]
        ):
            raise RepairError(
                "accepted worktree changed; a new repair review is required"
            )
        approval = self.workspaces.request_merge(session["lease_id"])
        self._event(
            session_id,
            None,
            "merge_approval_requested",
            {
                "approval_id": approval["id"],
                "scope_sha256": approval["scope_sha256"],
            },
        )
        return approval

    def _preflight_call(self, session: dict[str, Any]) -> str | None:
        policy = RepairPolicy.from_dict(session["policy"])
        elapsed = (
            datetime.fromisoformat(utc_now())
            - datetime.fromisoformat(session["created_at"])
        ).total_seconds()
        if elapsed >= policy.max_elapsed_seconds:
            return (
                f"elapsed time {round(elapsed)} seconds reached "
                f"{policy.max_elapsed_seconds}"
            )
        return self._budget_violation(session, for_next_call=True)

    @staticmethod
    def _budget_violation(
        session: dict[str, Any],
        *,
        for_next_call: bool,
    ) -> str | None:
        policy = RepairPolicy.from_dict(session["policy"])
        if policy.max_total_tokens is not None:
            if not session["total_tokens_known"]:
                return "token usage is unavailable under a hard repair budget"
            if (
                session["total_tokens"] >= policy.max_total_tokens
                if for_next_call
                else session["total_tokens"] > policy.max_total_tokens
            ):
                return (
                    f"token usage {session['total_tokens']} reached repair "
                    f"budget {policy.max_total_tokens}"
                )
        if policy.max_total_cost is not None:
            if not session["total_cost_known"]:
                return "cost is unavailable under a hard repair budget"
            observed = Decimal(session["total_cost"])
            limit = Decimal(policy.max_total_cost)
            if observed >= limit if for_next_call else observed > limit:
                return (
                    f"cost {observed} reached repair budget {limit} "
                    f"{policy.cost_currency}"
                )
        return None

    def _apply_usage(
        self,
        session_id: str,
        metadata: dict[str, Any],
    ) -> None:
        session = self.session(session_id)
        tokens, cost, currency = _usage(metadata)
        tokens_known = bool(session["total_tokens_known"])
        total_tokens = int(session["total_tokens"])
        if tokens is None:
            tokens_known = False
        elif tokens_known:
            total_tokens += tokens
        cost_known = bool(session["total_cost_known"])
        total_cost = Decimal(session["total_cost"])
        if cost is None:
            cost_known = False
        elif cost_known:
            expected = session["cost_currency"]
            if expected and currency != expected:
                cost_known = False
            else:
                total_cost += cost
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE repair_sessions
                SET total_tokens = ?, total_tokens_known = ?,
                    total_cost = ?, total_cost_known = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    total_tokens,
                    int(tokens_known),
                    str(total_cost),
                    int(cost_known),
                    utc_now(),
                    session_id,
                ),
            )

    def _interrupt(
        self,
        session_id: str,
        iteration_id: str,
        *,
        phase: str,
        exc: Exception,
    ) -> None:
        error = f"{type(exc).__name__}: {str(exc)[:1000]}"
        iteration_status = (
            "writer_interrupted"
            if phase == "writer"
            else "reviewer_interrupted"
        )
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE repair_iterations
                SET status = ?, error = ? WHERE id = ?
                """,
                (iteration_status, error, iteration_id),
            )
            conn.execute(
                """
                UPDATE repair_sessions
                SET status = 'recovery_required', updated_at = ?, error = ?
                WHERE id = ?
                """,
                (utc_now(), error, session_id),
            )
        self._event(
            session_id,
            iteration_id,
            f"{phase}_interrupted",
            {"error_type": type(exc).__name__},
        )

    def _require_recovery(
        self,
        session_id: str,
        iteration_id: str | None,
        error: str,
    ) -> None:
        with self.store.connect() as conn:
            if iteration_id:
                conn.execute(
                    """
                    UPDATE repair_iterations
                    SET status = 'writer_interrupted', error = ?
                    WHERE id = ?
                    """,
                    (error[:2000], iteration_id),
                )
            conn.execute(
                """
                UPDATE repair_sessions
                SET status = 'recovery_required', updated_at = ?, error = ?
                WHERE id = ?
                """,
                (utc_now(), error[:2000], session_id),
            )
        self._event(
            session_id,
            iteration_id,
            "recovery_required",
            {"reason": error[:1000]},
        )

    def _reset_review_after_invalid_decision(
        self,
        session_id: str,
        iteration_id: str,
        error: str,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE repair_iterations
                SET status = 'evidence_ready', error = ? WHERE id = ?
                """,
                (error, iteration_id),
            )
            conn.execute(
                """
                UPDATE repair_sessions
                SET status = 'waiting_review', updated_at = ?, error = ?
                WHERE id = ?
                """,
                (utc_now(), error, session_id),
            )

    def _limit_session(self, session_id: str, reason: str) -> None:
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE repair_sessions
                SET status = 'limit_reached', updated_at = ?,
                    completed_at = ?, error = ?
                WHERE id = ?
                """,
                (now, now, reason[:2000], session_id),
            )
        self._event(
            session_id,
            None,
            "limit_reached",
            {"reason": reason[:1000]},
        )

    def _finish_if_terminal(self, session_id: str) -> None:
        session = self.session(session_id)
        if session["status"] in TERMINAL_SESSION_STATUSES:
            with self.store.connect() as conn:
                conn.execute(
                    """
                    UPDATE repair_sessions
                    SET completed_at = COALESCE(completed_at, ?)
                    WHERE id = ?
                    """,
                    (utc_now(), session_id),
                )

    def _event(
        self,
        session_id: str,
        iteration_id: str | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        encoded = _dump(payload).encode("utf-8")
        if len(encoded) > MAX_EVENT_BYTES:
            safe_payload = {
                "truncated": True,
                "bytes": len(encoded),
                "sha256": sha256(encoded).hexdigest(),
            }
        else:
            safe_payload = sanitize_for_storage(payload)
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO repair_events(
                    id, session_id, iteration_id, event_type,
                    payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    session_id,
                    iteration_id,
                    event_type,
                    _dump(safe_payload),
                    utc_now(),
                ),
            )

    def _evidence(self, evidence_id: str | None) -> dict[str, Any]:
        if not evidence_id:
            raise RepairError("repair iteration is missing evidence")
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM worktree_evidence WHERE id = ?",
                (evidence_id,),
            ).fetchone()
        if row is None:
            raise RepairError(f"worktree evidence {evidence_id!r} not found")
        item = dict(row)
        item["command"] = json.loads(item.pop("command_json"))
        item["metadata"] = json.loads(item.pop("metadata_json"))
        return item

    def _latest_iteration(self, session_id: str) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM repair_iterations
                WHERE session_id = ?
                ORDER BY iteration_number DESC, id DESC LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            raise RepairError("repair session has no iteration")
        return self._iteration_row(row)

    @staticmethod
    def _session_row(row: Any) -> dict[str, Any]:
        item = dict(row)
        item["policy"] = json.loads(item.pop("policy_json"))
        item["test_command"] = json.loads(item.pop("test_command_json"))
        item["total_tokens_known"] = bool(item["total_tokens_known"])
        item["total_cost_known"] = bool(item["total_cost_known"])
        return item

    @staticmethod
    def _iteration_row(row: Any) -> dict[str, Any]:
        item = dict(row)
        item["writer_metadata"] = json.loads(
            item.pop("writer_metadata_json")
        )
        item["changed_files"] = json.loads(item.pop("changed_files_json"))
        item["reviewer_metadata"] = json.loads(
            item.pop("reviewer_metadata_json")
        )
        return item


def _normalize_response(value: Any) -> tuple[str, dict[str, Any]]:
    if value is None:
        return "", {}
    if isinstance(value, AgentResponse):
        return value.content, dict(value.metadata)
    if isinstance(value, dict):
        content = str(value.get("content", ""))
        metadata = value.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("response metadata must be an object")
        return content, dict(metadata)
    if isinstance(value, str):
        return value, {}
    raise ValueError("repair callback response must be text, object or AgentResponse")


def _normalize_review(value: Any) -> tuple[str, str, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if isinstance(value, AgentResponse):
        metadata = dict(value.metadata)
        raw: Any = value.content
    else:
        raw = value
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("reviewer response must be a JSON object") from exc
    else:
        payload = raw
    if not isinstance(payload, dict):
        raise ValueError("reviewer response must be an object")
    decision = str(payload.get("decision", "")).strip()
    feedback = str(payload.get("feedback", "")).strip()
    nested_metadata = payload.get("metadata", {})
    if not isinstance(nested_metadata, dict):
        raise ValueError("reviewer metadata must be an object")
    metadata.update(nested_metadata)
    if decision not in {"accept", "repair"}:
        raise ValueError("reviewer decision must be accept or repair")
    return decision, feedback, metadata


def _usage(
    metadata: dict[str, Any],
) -> tuple[int | None, Decimal | None, str | None]:
    usage = metadata.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    total = usage.get("total_tokens")
    if total is None:
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
            total = input_tokens + output_tokens
    tokens = (
        total
        if isinstance(total, int)
        and not isinstance(total, bool)
        and total >= 0
        else None
    )
    raw_cost = metadata.get("cost_amount", usage.get("cost_amount"))
    if raw_cost is None:
        cost = None
    else:
        try:
            cost = Decimal(str(raw_cost))
        except InvalidOperation:
            cost = None
        else:
            if not cost.is_finite() or cost < 0:
                cost = None
    currency_value = metadata.get(
        "cost_currency",
        usage.get("cost_currency"),
    )
    currency = str(currency_value) if currency_value else None
    return tokens, cost, currency


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be finite")
    return result


def _dump(value: Any) -> str:
    return json.dumps(
        sanitize_for_storage(value),
        ensure_ascii=False,
        sort_keys=True,
    )


def _raw_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    )
