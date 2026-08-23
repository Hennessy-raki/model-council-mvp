from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .types import RunStatus, TaskStatus


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CouncilStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    final_artifact_id TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    task_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    depends_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    output_artifact_id TEXT,
                    error TEXT,
                    UNIQUE(run_id, task_key)
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    task_id TEXT,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    type TEXT NOT NULL,
                    body_json TEXT NOT NULL,
                    artifact_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    task_id TEXT,
                    name TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);
                CREATE INDEX IF NOT EXISTS idx_messages_run ON messages(run_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);
                """
            )

    def create_run(self, goal: str) -> str:
        run_id = str(uuid4())
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO runs(id, goal, status, created_at) VALUES (?, ?, ?, ?)",
                (run_id, goal, RunStatus.RUNNING, utc_now()),
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        status: RunStatus,
        final_artifact_id: str | None = None,
        error: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, completed_at = ?, final_artifact_id = ?, error = ?
                WHERE id = ?
                """,
                (status, utc_now(), final_artifact_id, error, run_id),
            )

    def add_task(
        self,
        run_id: str,
        task_key: str,
        title: str,
        instruction: str,
        agent: str,
        depends_on: list[str],
    ) -> str:
        task_id = str(uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks(
                    id, run_id, task_key, title, instruction, agent, status,
                    depends_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    run_id,
                    task_key,
                    title,
                    instruction,
                    agent,
                    TaskStatus.PENDING,
                    json.dumps(depends_on, ensure_ascii=False),
                    utc_now(),
                ),
            )
        return task_id

    def set_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        output_artifact_id: str | None = None,
        error: str | None = None,
    ) -> None:
        now = utc_now()
        started_at = now if status == TaskStatus.RUNNING else None
        completed_at = now if status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
        } else None
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?,
                    started_at = COALESCE(started_at, ?),
                    completed_at = COALESCE(?, completed_at),
                    output_artifact_id = COALESCE(?, output_artifact_id),
                    error = ?
                WHERE id = ?
                """,
                (status, started_at, completed_at, output_artifact_id, error, task_id),
            )

    def add_message(
        self,
        run_id: str,
        task_id: str | None,
        sender: str,
        recipient: str,
        message_type: str,
        body: dict[str, Any],
        artifact_ids: list[str] | None = None,
    ) -> str:
        message_id = str(uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO messages(
                    id, run_id, task_id, sender, recipient, type,
                    body_json, artifact_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    run_id,
                    task_id,
                    sender,
                    recipient,
                    message_type,
                    json.dumps(body, ensure_ascii=False),
                    json.dumps(artifact_ids or [], ensure_ascii=False),
                    utc_now(),
                ),
            )
        return message_id

    def add_artifact(
        self,
        run_id: str,
        task_id: str | None,
        name: str,
        media_type: str,
        sha256: str,
        path: str,
    ) -> str:
        artifact_id = str(uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts(
                    id, run_id, task_id, name, media_type, sha256, path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, run_id, task_id, name, media_type, sha256, path, utc_now()),
            )
        return artifact_id

    def tasks_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE run_id = ? ORDER BY created_at, task_key",
                (run_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["depends_on"] = json.loads(item.pop("depends_json"))
            result.append(item)
        return result

    def artifacts_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
