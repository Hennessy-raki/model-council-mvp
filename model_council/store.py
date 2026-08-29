from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .types import (
    ArtifactIdentity,
    ProvenanceDisplayMode,
    RunStatus,
    TaskStatus,
)


ARTIFACT_RELATIONSHIPS = {
    "producer",
    "contributor",
    "reviewer",
    "final_integrator",
}


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
                    producer_agent_id TEXT,
                    producer_provider_id TEXT,
                    producer_model_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifact_attributions (
                    id TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    relationship TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    provider_id TEXT,
                    model_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS providers (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    config_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL REFERENCES providers(id),
                    display_name TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_profiles (
                    id TEXT PRIMARY KEY,
                    adapter_type TEXT NOT NULL,
                    provider_id TEXT REFERENCES providers(id),
                    model_id TEXT REFERENCES models(id),
                    role TEXT NOT NULL,
                    description TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    boundaries_json TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS role_assignments (
                    role_key TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    agent_id TEXT REFERENCES agent_profiles(id),
                    model_id TEXT REFERENCES models(id),
                    locked INTEGER NOT NULL,
                    constraints_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_discovery (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    display_name TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    adapter_type TEXT NOT NULL,
                    executable_status TEXT NOT NULL,
                    authentication_status TEXT NOT NULL,
                    permission_status TEXT NOT NULL,
                    connectivity_status TEXT NOT NULL,
                    resolved_executable TEXT,
                    models_json TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);
                CREATE INDEX IF NOT EXISTS idx_messages_run ON messages(run_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);
                CREATE INDEX IF NOT EXISTS idx_artifact_attributions_artifact
                    ON artifact_attributions(artifact_id);
                CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider_id);
                CREATE INDEX IF NOT EXISTS idx_agents_provider ON agent_profiles(provider_id);
                CREATE INDEX IF NOT EXISTS idx_agents_model ON agent_profiles(model_id);
                CREATE INDEX IF NOT EXISTS idx_discovery_agent
                    ON agent_discovery(agent_id);
                """
            )
            self._ensure_column(conn, "artifacts", "producer_agent_id", "TEXT")
            self._ensure_column(conn, "artifacts", "producer_provider_id", "TEXT")
            self._ensure_column(conn, "artifacts", "producer_model_id", "TEXT")

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

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
        producer: ArtifactIdentity | None = None,
        attributions: list[tuple[str, ArtifactIdentity]] | None = None,
    ) -> str:
        artifact_id = str(uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts(
                    id, run_id, task_id, name, media_type, sha256, path,
                    producer_agent_id, producer_provider_id, producer_model_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    run_id,
                    task_id,
                    name,
                    media_type,
                    sha256,
                    path,
                    producer.agent_id if producer else None,
                    producer.provider_id if producer else None,
                    producer.model_id if producer else None,
                    utc_now(),
                ),
            )
            all_attributions = list(attributions or [])
            if producer:
                all_attributions.insert(0, ("producer", producer))
            self._add_artifact_attributions(conn, artifact_id, all_attributions)
        return artifact_id

    def _add_artifact_attributions(
        self,
        conn: sqlite3.Connection,
        artifact_id: str,
        attributions: list[tuple[str, ArtifactIdentity]],
    ) -> None:
        seen: set[tuple[str, str, str | None, str | None]] = set()
        for relationship, identity in attributions:
            if relationship not in ARTIFACT_RELATIONSHIPS:
                raise ValueError(f"unsupported artifact relationship {relationship!r}")
            key = (
                relationship,
                identity.agent_id,
                identity.provider_id,
                identity.model_id,
            )
            if key in seen:
                continue
            seen.add(key)
            conn.execute(
                """
                INSERT INTO artifact_attributions(
                    id, artifact_id, relationship, agent_id, provider_id,
                    model_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    artifact_id,
                    relationship,
                    identity.agent_id,
                    identity.provider_id,
                    identity.model_id,
                    utc_now(),
                ),
            )

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

    def artifacts_for_run(
        self,
        run_id: str,
        display_mode: str | ProvenanceDisplayMode = ProvenanceDisplayMode.DETAILED,
    ) -> list[dict[str, Any]]:
        mode = ProvenanceDisplayMode(display_mode)
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if mode != ProvenanceDisplayMode.HIDDEN:
                provenance = self.provenance_for_artifact(item["id"])
                item["provenance"] = (
                    provenance
                    if mode == ProvenanceDisplayMode.DETAILED
                    else self._compact_provenance(provenance)
                )
            result.append(item)
        return result

    def provenance_for_artifact(self, artifact_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            artifact = conn.execute(
                """
                SELECT producer_agent_id, producer_provider_id, producer_model_id
                FROM artifacts WHERE id = ?
                """,
                (artifact_id,),
            ).fetchone()
            if artifact is None:
                raise ValueError(f"artifact {artifact_id!r} not found")
            rows = conn.execute(
                """
                SELECT relationship, agent_id, provider_id, model_id
                FROM artifact_attributions
                WHERE artifact_id = ?
                ORDER BY created_at, id
                """,
                (artifact_id,),
            ).fetchall()
        groups: dict[str, list[dict[str, str | None]]] = {
            "contributors": [],
            "reviewers": [],
            "final_integrators": [],
        }
        for row in rows:
            identity = self._identity_payload(row)
            if row["relationship"] == "contributor":
                groups["contributors"].append(identity)
            elif row["relationship"] == "reviewer":
                groups["reviewers"].append(identity)
            elif row["relationship"] == "final_integrator":
                groups["final_integrators"].append(identity)
        producer = self._identity_payload(
            {
                "agent_id": artifact["producer_agent_id"],
                "provider_id": artifact["producer_provider_id"],
                "model_id": artifact["producer_model_id"],
            }
        )
        return {
            "producer": producer if producer["agent_id"] else None,
            **groups,
        }

    def contributor_identities(
        self,
        artifact_ids: list[str],
    ) -> list[ArtifactIdentity]:
        if not artifact_ids:
            return []
        placeholders = ", ".join("?" for _ in artifact_ids)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT agent_id, provider_id, model_id
                FROM artifact_attributions
                WHERE artifact_id IN ({placeholders})
                ORDER BY created_at, id
                """,
                artifact_ids,
            ).fetchall()
        result: list[ArtifactIdentity] = []
        seen: set[tuple[str, str | None, str | None]] = set()
        for row in rows:
            key = (row["agent_id"], row["provider_id"], row["model_id"])
            if key not in seen:
                seen.add(key)
                result.append(ArtifactIdentity(*key))
        return result

    def identity_for_agent(self, agent_id: str) -> ArtifactIdentity:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, provider_id, model_id
                FROM agent_profiles WHERE id = ?
                """,
                (agent_id,),
            ).fetchone()
        if row is None:
            return ArtifactIdentity(agent_id=agent_id)
        return ArtifactIdentity(
            agent_id=row["id"],
            provider_id=row["provider_id"],
            model_id=row["model_id"],
        )

    @staticmethod
    def _identity_payload(row: Any) -> dict[str, str | None]:
        return {
            "agent_id": row["agent_id"],
            "provider_id": row["provider_id"],
            "model_id": row["model_id"],
        }

    @staticmethod
    def _compact_provenance(provenance: dict[str, Any]) -> dict[str, Any]:
        return {
            "producer": provenance["producer"],
            "contributor_count": len(provenance["contributors"]),
            "reviewed": bool(provenance["reviewers"]),
            "final_integrated": bool(provenance["final_integrators"]),
        }

    def messages_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["body"] = json.loads(item.pop("body_json"))
            item["artifact_ids"] = json.loads(item.pop("artifact_ids_json"))
            result.append(item)
        return result

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
