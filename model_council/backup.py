from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from .store import CouncilStore, utc_now


BACKUP_STATUSES = {"complete", "failed"}
RESTORE_APPROVAL_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "consumed",
    "failed",
    "stale",
}
MAX_BACKUP_ARTIFACTS = 10_000
_SAFE_ID = re.compile(r"^[0-9a-f-]{36}$")
_EXCLUDED_LOGICAL_TABLES = {
    "local_backups",
    "backup_restore_approvals",
}


class BackupError(RuntimeError):
    pass


class BackupService:
    """Privacy-safe local SQLite backup and exact, approved restore."""

    def __init__(self, store: CouncilStore):
        self.store = store
        self.state_dir = store.db_path.parent.resolve()
        self.backup_root = (self.state_dir / "backups").resolve()
        self.artifact_root = (self.state_dir / "artifacts").resolve()
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        *,
        include_artifacts: bool = False,
        reason: str = "manual",
    ) -> dict[str, Any]:
        if reason not in {"manual", "pre_restore"}:
            raise ValueError("backup reason must be manual or pre_restore")
        backup_id = str(uuid4())
        backup_dir = (self.backup_root / backup_id).resolve()
        self._require_contained(backup_dir, self.backup_root)
        backup_dir.mkdir(parents=False, exist_ok=False)
        database_path = backup_dir / "council.db"
        now = utc_now()
        try:
            self._sqlite_backup(self.store.db_path, database_path)
            database_sha256 = _file_sha256(database_path)
            artifacts, artifact_issues = (
                self._copy_registered_artifacts(
                    backup_dir,
                    allow_unavailable=reason == "pre_restore",
                )
                if include_artifacts
                else ([], [])
            )
            manifest = {
                "version": 1,
                "id": backup_id,
                "reason": reason,
                "created_at": now,
                "database": {
                    "name": "council.db",
                    "bytes": database_path.stat().st_size,
                    "sha256": database_sha256,
                },
                "include_artifacts": include_artifacts,
                "artifact_count": len(artifacts),
                "artifact_bytes": sum(item["bytes"] for item in artifacts),
                "artifacts": artifacts,
                "artifact_issues": artifact_issues,
                "state_identity_sha256": sha256(
                    str(self.state_dir).encode("utf-8")
                ).hexdigest(),
                "excluded": [
                    "credentials",
                    "environment files",
                    "Git worktrees",
                    "repository files",
                ],
            }
            (backup_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            with self.store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO local_backups(
                        id, status, manifest_json, created_at, updated_at
                    ) VALUES (?, 'complete', ?, ?, ?)
                    """,
                    (
                        backup_id,
                        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                        now,
                        now,
                    ),
                )
            return self.backup(backup_id)
        except Exception:
            shutil.rmtree(backup_dir, ignore_errors=True)
            raise

    def backups(self) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM local_backups ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._backup_row(row) for row in rows]

    def backup(self, backup_id: str) -> dict[str, Any]:
        self._validate_id(backup_id)
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM local_backups WHERE id = ?",
                (backup_id,),
            ).fetchone()
        if row is None:
            raise BackupError(f"backup {backup_id!r} not found")
        result = self._backup_row(row)
        self._validate_backup_files(result["manifest"])
        return result

    def request_restore(self, backup_id: str) -> dict[str, Any]:
        backup = self.backup(backup_id)
        manifest = backup["manifest"]
        scope = self._restore_scope(manifest)
        approval_id = str(uuid4())
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO backup_restore_approvals(
                    id, backup_id, scope_sha256, scope_json, status,
                    requested_at, decided_at, consumed_at, safety_backup_id,
                    failure
                ) VALUES (?, ?, ?, ?, 'pending', ?, NULL, NULL, NULL, NULL)
                """,
                (
                    approval_id,
                    backup_id,
                    _json_sha256(scope),
                    json.dumps(scope, ensure_ascii=False, sort_keys=True),
                    now,
                ),
            )
        return self.approval(approval_id)

    def approvals(self, status: str | None = None) -> list[dict[str, Any]]:
        params: tuple[Any, ...] = ()
        query = "SELECT * FROM backup_restore_approvals"
        if status:
            if status not in RESTORE_APPROVAL_STATUSES:
                raise ValueError(f"unsupported restore approval status {status!r}")
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY requested_at DESC, id DESC"
        with self.store.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._approval_row(row) for row in rows]

    def approval(self, approval_id: str) -> dict[str, Any]:
        self._validate_id(approval_id)
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM backup_restore_approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
        if row is None:
            raise BackupError(f"restore approval {approval_id!r} not found")
        return self._approval_row(row)

    def decide(
        self,
        approval_id: str,
        *,
        approve: bool,
        confirmation: str = "",
    ) -> dict[str, Any]:
        approval = self.approval(approval_id)
        if approval["status"] != "pending":
            raise BackupError(
                f"restore approval {approval_id!r} is not pending"
            )
        if approve and confirmation != approval["scope_sha256"]:
            raise BackupError(
                "restore confirmation must exactly match the displayed "
                "scope_sha256"
            )
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE backup_restore_approvals
                SET status = ?, decided_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (
                    "approved" if approve else "rejected",
                    utc_now(),
                    approval_id,
                ),
            ).rowcount
        if not updated:
            raise BackupError(
                f"restore approval {approval_id!r} changed before decision"
            )
        return self.approval(approval_id)

    def restore(self, approval_id: str) -> dict[str, Any]:
        approval = self.approval(approval_id)
        if (
            approval["status"] != "approved"
            or approval["consumed_at"] is not None
        ):
            raise BackupError(
                f"restore approval {approval_id!r} is not approved and unused"
            )
        backup = self.backup(approval["backup_id"])
        current_scope = self._restore_scope(backup["manifest"])
        if _json_sha256(current_scope) != approval["scope_sha256"]:
            self._mark_approval(
                approval_id,
                status="stale",
                failure="restore scope changed after approval",
            )
            raise BackupError("restore scope changed after approval")

        self._preflight_artifacts(backup["manifest"])
        safety = self.create(
            include_artifacts=True,
            reason="pre_restore",
        )
        if _json_sha256(self._restore_scope(backup["manifest"])) != approval[
            "scope_sha256"
        ]:
            self._mark_approval(
                approval_id,
                status="stale",
                failure="local state changed before restore",
                safety_backup_id=safety["id"],
            )
            raise BackupError("local state changed before restore")

        approval_record = dict(approval)
        target_manifest = dict(backup["manifest"])
        safety_manifest = dict(safety["manifest"])
        try:
            self._restore_artifacts(target_manifest)
            self._restore_database(target_manifest)
            restored_store = CouncilStore(self.store.db_path)
            now = utc_now()
            with restored_store.connect() as conn:
                for item, manifest in (
                    (backup, target_manifest),
                    (safety, safety_manifest),
                ):
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO local_backups(
                            id, status, manifest_json, created_at, updated_at
                        ) VALUES (?, 'complete', ?, ?, ?)
                        """,
                        (
                            item["id"],
                            json.dumps(
                                manifest,
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            item["created_at"],
                            now,
                        ),
                    )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO backup_restore_approvals(
                        id, backup_id, scope_sha256, scope_json, status,
                        requested_at, decided_at, consumed_at,
                        safety_backup_id, failure
                    ) VALUES (?, ?, ?, ?, 'consumed', ?, ?, ?, ?, NULL)
                    """,
                    (
                        approval_record["id"],
                        approval_record["backup_id"],
                        approval_record["scope_sha256"],
                        json.dumps(
                            approval_record["scope"],
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        approval_record["requested_at"],
                        approval_record["decided_at"],
                        now,
                        safety["id"],
                    ),
                )
            self.store = restored_store
            return self.approval(approval_id)
        except Exception as exc:
            try:
                CouncilStore(self.store.db_path)
                self._mark_approval(
                    approval_id,
                    status="failed",
                    failure=type(exc).__name__,
                    safety_backup_id=safety["id"],
                )
            except Exception:
                pass
            raise

    def _restore_scope(self, manifest: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": 1,
            "backup_id": manifest["id"],
            "backup_database_sha256": manifest["database"]["sha256"],
            "backup_database_bytes": manifest["database"]["bytes"],
            "artifact_inventory_sha256": _json_sha256(
                manifest.get("artifacts", [])
            ),
            "artifact_count": manifest.get("artifact_count", 0),
            "current_state_sha256": self._logical_database_sha256(),
            "state_identity_sha256": manifest["state_identity_sha256"],
            "actions": [
                "create pre-restore safety backup",
                "replace local SQLite database",
                "add missing verified Artifact files",
            ],
            "excluded": [
                "Git worktrees",
                "repositories",
                "credentials",
                "environment files",
            ],
        }

    def _copy_registered_artifacts(
        self,
        backup_dir: Path,
        *,
        allow_unavailable: bool,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, path, sha256 FROM artifacts
                ORDER BY created_at, id
                """
            ).fetchall()
        if len(rows) > MAX_BACKUP_ARTIFACTS:
            raise BackupError(
                f"artifact count exceeds backup limit {MAX_BACKUP_ARTIFACTS}"
            )
        items = []
        issues = []
        for row in rows:
            try:
                source = Path(row["path"]).resolve(strict=True)
            except OSError:
                if not allow_unavailable:
                    raise BackupError(
                        f"registered Artifact {row['id']!r} is unavailable"
                    )
                issues.append(
                    {"id": row["id"], "reason": "unavailable"}
                )
                continue
            self._require_contained(source, self.artifact_root)
            relative = source.relative_to(self.artifact_root)
            digest = _file_sha256(source)
            if digest != row["sha256"]:
                if not allow_unavailable:
                    raise BackupError(
                        f"registered Artifact {row['id']!r} hash does not match"
                    )
                issues.append(
                    {"id": row["id"], "reason": "hash_mismatch"}
                )
                continue
            target = (backup_dir / "artifacts" / relative).resolve()
            self._require_contained(target, backup_dir / "artifacts")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            items.append(
                {
                    "id": row["id"],
                    "path": relative.as_posix(),
                    "bytes": source.stat().st_size,
                    "sha256": digest,
                }
            )
        return items, issues

    def _validate_backup_files(self, manifest: dict[str, Any]) -> None:
        backup_dir = self._backup_dir(manifest["id"])
        current_identity = sha256(
            str(self.state_dir).encode("utf-8")
        ).hexdigest()
        if manifest["state_identity_sha256"] != current_identity:
            raise BackupError("backup belongs to a different local state directory")
        manifest_path = backup_dir / "manifest.json"
        if not manifest_path.is_file():
            raise BackupError("backup manifest is missing")
        try:
            disk_manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise BackupError("backup manifest is invalid") from exc
        if _json_sha256(disk_manifest) != _json_sha256(manifest):
            raise BackupError("backup manifest changed")
        database_path = backup_dir / manifest["database"]["name"]
        if not database_path.is_file():
            raise BackupError("backup database is missing")
        if database_path.stat().st_size != manifest["database"]["bytes"]:
            raise BackupError("backup database byte count changed")
        if _file_sha256(database_path) != manifest["database"]["sha256"]:
            raise BackupError("backup database hash changed")
        self._integrity_check(database_path)
        for item in manifest.get("artifacts", []):
            source = (backup_dir / "artifacts" / item["path"]).resolve()
            self._require_contained(source, backup_dir / "artifacts")
            if not source.is_file():
                raise BackupError("backup Artifact is missing")
            if source.stat().st_size != item["bytes"]:
                raise BackupError("backup Artifact byte count changed")
            if _file_sha256(source) != item["sha256"]:
                raise BackupError("backup Artifact hash changed")

    def _preflight_artifacts(self, manifest: dict[str, Any]) -> None:
        self._validate_backup_files(manifest)
        for item in manifest.get("artifacts", []):
            target = (self.artifact_root / item["path"]).resolve()
            self._require_contained(target, self.artifact_root)
            if target.exists() and _file_sha256(target) != item["sha256"]:
                raise BackupError(
                    "existing Artifact conflicts with the approved backup"
                )

    def _restore_artifacts(self, manifest: dict[str, Any]) -> None:
        backup_dir = self._backup_dir(manifest["id"])
        for item in manifest.get("artifacts", []):
            source = (backup_dir / "artifacts" / item["path"]).resolve()
            target = (self.artifact_root / item["path"]).resolve()
            self._require_contained(source, backup_dir / "artifacts")
            self._require_contained(target, self.artifact_root)
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
            shutil.copy2(source, temporary)
            if _file_sha256(temporary) != item["sha256"]:
                temporary.unlink(missing_ok=True)
                raise BackupError("restored Artifact hash verification failed")
            os.replace(temporary, target)

    def _restore_database(self, manifest: dict[str, Any]) -> None:
        backup_database = (
            self._backup_dir(manifest["id"]) / manifest["database"]["name"]
        )
        temporary = self.store.db_path.with_name(
            f".{self.store.db_path.name}.{uuid4().hex}.restore"
        )
        shutil.copy2(backup_database, temporary)
        self._integrity_check(temporary)
        with self.store.connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        for suffix in ("-wal", "-shm"):
            Path(f"{self.store.db_path}{suffix}").unlink(missing_ok=True)
        os.replace(temporary, self.store.db_path)

    def _logical_database_sha256(self) -> str:
        digest = sha256()
        with self.store.connect() as conn:
            tables = [
                str(row["name"])
                for row in conn.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                    """
                ).fetchall()
                if row["name"] not in _EXCLUDED_LOGICAL_TABLES
            ]
            for table in tables:
                digest.update(table.encode("utf-8"))
                columns = [
                    str(row["name"])
                    for row in conn.execute(
                        f'PRAGMA table_info("{table}")'
                    ).fetchall()
                ]
                digest.update(
                    json.dumps(columns, separators=(",", ":")).encode("utf-8")
                )
                rows = conn.execute(
                    f'SELECT * FROM "{table}" ORDER BY rowid'
                ).fetchall()
                for row in rows:
                    digest.update(
                        json.dumps(
                            [row[column] for column in columns],
                            ensure_ascii=False,
                            separators=(",", ":"),
                            default=str,
                        ).encode("utf-8")
                    )
        return digest.hexdigest()

    def _mark_approval(
        self,
        approval_id: str,
        *,
        status: str,
        failure: str,
        safety_backup_id: str | None = None,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE backup_restore_approvals
                SET status = ?, failure = ?, safety_backup_id = ?
                WHERE id = ?
                """,
                (status, failure, safety_backup_id, approval_id),
            )

    def _backup_dir(self, backup_id: str) -> Path:
        self._validate_id(backup_id)
        result = (self.backup_root / backup_id).resolve()
        self._require_contained(result, self.backup_root)
        return result

    @staticmethod
    def _sqlite_backup(source: Path, target: Path) -> None:
        with closing(sqlite3.connect(source)) as source_conn:
            with closing(sqlite3.connect(target)) as target_conn:
                source_conn.backup(target_conn)
        BackupService._integrity_check(target)

    @staticmethod
    def _integrity_check(path: Path) -> None:
        with closing(
            sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        ) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise BackupError("SQLite integrity check failed")

    @staticmethod
    def _require_contained(path: Path, parent: Path) -> None:
        resolved_parent = parent.resolve()
        resolved_path = path.resolve()
        if resolved_path != resolved_parent and resolved_parent not in resolved_path.parents:
            raise BackupError("backup path escapes the local state directory")

    @staticmethod
    def _validate_id(value: str) -> None:
        if not _SAFE_ID.fullmatch(value):
            raise ValueError("backup identifier is invalid")

    @staticmethod
    def _backup_row(row: Any) -> dict[str, Any]:
        result = dict(row)
        result["manifest"] = json.loads(result.pop("manifest_json"))
        return result

    @staticmethod
    def _approval_row(row: Any) -> dict[str, Any]:
        result = dict(row)
        result["scope"] = json.loads(result.pop("scope_json"))
        return result


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
