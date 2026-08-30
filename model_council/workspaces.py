from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from .adapters.cli import CliAdapter
from .store import CouncilStore, utc_now
from .types import AgentRequest, AgentResponse, PermissionStatus


LEASE_STATUSES = {"active", "merged", "discarded", "failed"}
APPROVAL_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "consumed",
    "failed",
    "stale",
}
PERMISSIONS = {"read", "write", "test", "merge"}
APPROVAL_ACTIONS = {"merge", "discard"}
MAX_DIFF_BYTES = 128_000
MAX_TEST_STREAM_BYTES = 64_000
MAX_COMMAND_SECONDS = 3_600
MAX_DISCARD_FILES = 1_000
MAX_DISCARD_HASH_BYTES = 64 * 1024 * 1024
MAX_STATUS_BYTES = 1_000_000
_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_SENSITIVE_FLAGS = (
    "--api-key",
    "--authorization",
    "--bearer",
    "--password",
    "--secret",
    "--token",
)


class WorkspaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class _StreamCapture:
    data: bytes
    text: str
    total_bytes: int
    digest: str
    truncated: bool


@dataclass(frozen=True)
class _CommandResult:
    command: list[str]
    exit_code: int | None
    duration_ms: int
    stdout: _StreamCapture
    stderr: _StreamCapture
    timed_out: bool


class WorkspaceService:
    """Persistent isolated Git worktrees and exact local approval gates."""

    def __init__(self, store: CouncilStore):
        self.store = store
        self.worktree_root = (store.db_path.parent / "worktrees").resolve()
        self.worktree_root.mkdir(parents=True, exist_ok=True)

    def prepare(
        self,
        *,
        repository: str | Path,
        agent_id: str,
        base_ref: str = "HEAD",
    ) -> dict[str, Any]:
        if not agent_id.strip():
            raise ValueError("agent_id cannot be empty")
        self._validate_ref(base_ref)
        repository_root = self._repository_root(repository)
        self._require_clean(repository_root, "target repository")
        target_branch = self._git_text(
            repository_root,
            ["symbolic-ref", "--quiet", "--short", "HEAD"],
            "target repository must be on a branch",
        )
        base_sha = self._git_text(
            repository_root,
            ["rev-parse", "--verify", f"{base_ref}^{{commit}}"],
            f"base ref {base_ref!r} is not a commit",
        )
        lease_id = str(uuid4())
        branch_name = self._branch_name(agent_id, lease_id)
        worktree_path = (self.worktree_root / lease_id).resolve()
        self._require_contained(worktree_path, self.worktree_root)
        self._require_runtime_path_ignored(repository_root, worktree_path)

        command = [
            "git",
            "-C",
            str(repository_root),
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_path),
            base_sha,
        ]
        completed = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            shell=False,
            check=False,
        )
        if completed.returncode != 0:
            raise WorkspaceError(
                "git worktree add failed: "
                f"{completed.stderr.strip()[-2000:]}"
            )

        now = utc_now()
        try:
            with self.store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO worktree_leases(
                        id, repository_root, target_branch, base_ref, base_sha,
                        branch_name, worktree_path, agent_id, status,
                        created_at, updated_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, NULL)
                    """,
                    (
                        lease_id,
                        str(repository_root),
                        target_branch,
                        base_ref,
                        base_sha,
                        branch_name,
                        str(worktree_path),
                        agent_id,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO worktree_permissions(
                        lease_id, read_enabled, write_enabled, test_enabled,
                        merge_enabled, source, updated_at
                    ) VALUES (?, 1, 0, 0, 0, 'default', ?)
                    """,
                    (lease_id, now),
                )
        except Exception:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository_root),
                    "worktree",
                    "remove",
                    "--force",
                    str(worktree_path),
                ],
                capture_output=True,
                shell=False,
                check=False,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository_root),
                    "branch",
                    "-D",
                    branch_name,
                ],
                capture_output=True,
                shell=False,
                check=False,
            )
            raise
        return self.workspace(lease_id)

    def workspaces(
        self,
        *,
        status: str | None = None,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        where = []
        params: list[Any] = []
        if status:
            if status not in LEASE_STATUSES:
                raise ValueError(f"unsupported worktree status {status!r}")
            where.append("l.status = ?")
            params.append(status)
        if agent_id:
            where.append("l.agent_id = ?")
            params.append(agent_id)
        query = self._workspace_query()
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY l.updated_at DESC, l.id DESC"
        with self.store.connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._workspace_row(row) for row in rows]

    def workspace(self, lease_id: str) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                self._workspace_query() + " WHERE l.id = ?",
                (lease_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"worktree lease {lease_id!r} not found")
        return self._workspace_row(row)

    def set_permission(
        self,
        lease_id: str,
        *,
        permission: str,
        enabled: bool,
    ) -> dict[str, Any]:
        if permission not in PERMISSIONS:
            raise ValueError(f"unsupported workspace permission {permission!r}")
        workspace = self._active_workspace(lease_id)
        values = dict(workspace["permissions"])
        values[permission] = bool(enabled)
        if not values["read"] and any(
            values[item] for item in ("write", "test", "merge")
        ):
            raise WorkspaceError(
                "read permission must remain enabled while another permission is enabled"
            )
        if values["merge"] and not (values["write"] and values["test"]):
            raise WorkspaceError(
                "merge permission requires read, write and test permissions"
            )
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                f"""
                UPDATE worktree_permissions
                SET {permission}_enabled = ?, source = 'user', updated_at = ?
                WHERE lease_id = ?
                """,
                (int(enabled), now, lease_id),
            )
            conn.execute(
                "UPDATE worktree_leases SET updated_at = ? WHERE id = ?",
                (now, lease_id),
            )
        return self.workspace(lease_id)

    def authorized_path(
        self,
        lease_id: str,
        *,
        agent_id: str,
        permission: str,
    ) -> Path:
        if permission not in PERMISSIONS:
            raise ValueError(f"unsupported workspace permission {permission!r}")
        workspace = self._active_workspace(lease_id)
        if workspace["agent_id"] != agent_id:
            raise WorkspaceError(
                f"worktree lease {lease_id!r} belongs to another agent"
            )
        self._require_permission(workspace, permission)
        path = Path(workspace["worktree_path"]).resolve(strict=True)
        self._require_contained(path, self.worktree_root)
        return path

    def invoke_cli(
        self,
        lease_id: str,
        adapter: CliAdapter,
        request: AgentRequest,
        *,
        write: bool,
    ) -> AgentResponse:
        permission = "write" if write else "read"
        path = self.authorized_path(
            lease_id,
            agent_id=request.recipient,
            permission=permission,
        )
        observed = adapter.check_permissions()["status"]
        required = (
            PermissionStatus.WORKSPACE_WRITE.value
            if write
            else PermissionStatus.READ_ONLY.value
        )
        if observed != required:
            raise WorkspaceError(
                f"CLI sandbox is {observed!r}; {required!r} is required"
            )
        return adapter.invoke_in_workspace(request, path)

    def checkpoint(
        self,
        lease_id: str,
        *,
        message: str,
    ) -> dict[str, Any]:
        workspace = self._active_workspace(lease_id)
        self._require_permission(workspace, "write")
        clean_message = message.strip()
        if not clean_message or len(clean_message.encode("utf-8")) > 240:
            raise ValueError("checkpoint message must be 1 to 240 UTF-8 bytes")
        path = self._registered_worktree(workspace)
        if not self._status_bytes(path):
            raise WorkspaceError("worktree has no changes to checkpoint")
        started = time.perf_counter()
        commands = [
            ["git", "-C", str(path), "add", "--all"],
            [
                "git",
                "-C",
                str(path),
                "-c",
                "user.name=Model Council",
                "-c",
                "user.email=model-council@users.noreply.github.com",
                "commit",
                "-m",
                clean_message,
            ],
        ]
        stderr_parts = []
        exit_code = 0
        for command in commands:
            completed = subprocess.run(
                command,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                shell=False,
                check=False,
            )
            stderr_parts.append(completed.stderr)
            if completed.returncode != 0:
                exit_code = completed.returncode
                break
        head_sha = self._head_sha(path)
        result = _CommandResult(
            command=commands[-1],
            exit_code=exit_code,
            duration_ms=round((time.perf_counter() - started) * 1000),
            stdout=self._capture_text("", MAX_TEST_STREAM_BYTES),
            stderr=self._capture_text(
                "".join(stderr_parts),
                MAX_TEST_STREAM_BYTES,
            ),
            timed_out=False,
        )
        evidence = self._record_evidence(
            workspace,
            kind="checkpoint",
            status="passed" if exit_code == 0 else "failed",
            result=result,
            metadata={"head_sha": head_sha},
        )
        if exit_code != 0:
            raise WorkspaceError(
                f"checkpoint failed; evidence_id={evidence['id']}"
            )
        return evidence

    def collect_diff(self, lease_id: str) -> dict[str, Any]:
        workspace = self._active_workspace(lease_id)
        self._require_permission(workspace, "read")
        path = self._registered_worktree(workspace)
        head_sha = self._head_sha(path)
        status_bytes = self._status_bytes(path)
        command = [
            "git",
            "-C",
            str(path),
            "diff",
            "--no-ext-diff",
            "--no-color",
            workspace["base_sha"],
            "--",
        ]
        result = self._run_bounded(
            command,
            cwd=path,
            timeout_seconds=120,
            max_stdout_bytes=MAX_DIFF_BYTES,
            max_stderr_bytes=MAX_TEST_STREAM_BYTES,
        )
        evidence = self._record_evidence(
            workspace,
            kind="diff",
            status="passed" if result.exit_code == 0 else "failed",
            result=result,
            metadata={
                "base_sha": workspace["base_sha"],
                "head_sha": head_sha,
                "worktree_clean": not bool(status_bytes),
                "status_sha256": sha256(status_bytes).hexdigest(),
            },
        )
        if result.exit_code != 0:
            raise WorkspaceError(
                f"diff collection failed; evidence_id={evidence['id']}"
            )
        return evidence

    def run_test(
        self,
        lease_id: str,
        *,
        command: list[str],
        timeout_seconds: int = 600,
    ) -> dict[str, Any]:
        workspace = self._active_workspace(lease_id)
        self._require_permission(workspace, "test")
        command = self._validate_command(command)
        if not 1 <= timeout_seconds <= MAX_COMMAND_SECONDS:
            raise ValueError(
                f"timeout_seconds must be between 1 and {MAX_COMMAND_SECONDS}"
            )
        path = self._registered_worktree(workspace)
        head_sha = self._head_sha(path)
        status_sha = sha256(self._status_bytes(path)).hexdigest()
        result = self._run_bounded(
            command,
            cwd=path,
            timeout_seconds=timeout_seconds,
            max_stdout_bytes=MAX_TEST_STREAM_BYTES,
            max_stderr_bytes=MAX_TEST_STREAM_BYTES,
        )
        status = (
            "timed_out"
            if result.timed_out
            else ("passed" if result.exit_code == 0 else "failed")
        )
        return self._record_evidence(
            workspace,
            kind="test",
            status=status,
            result=result,
            metadata={
                "head_sha": head_sha,
                "status_sha256": status_sha,
            },
        )

    def evidence(
        self,
        lease_id: str,
        *,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        self.workspace(lease_id)
        query = "SELECT * FROM worktree_evidence WHERE lease_id = ?"
        params: list[Any] = [lease_id]
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        query += " ORDER BY created_at DESC, id DESC"
        with self.store.connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._evidence_row(row) for row in rows]

    def git_state(self, lease_id: str) -> dict[str, Any]:
        workspace = self._active_workspace(lease_id)
        self._require_permission(workspace, "read")
        path = self._registered_worktree(workspace)
        status_bytes = self._status_bytes(path)
        return {
            "lease_id": lease_id,
            "head_sha": self._head_sha(path),
            "clean": not bool(status_bytes),
            "status_sha256": sha256(status_bytes).hexdigest(),
        }

    def change_inventory(
        self,
        lease_id: str,
        *,
        max_files: int = 1_000,
        max_bytes: int = MAX_STATUS_BYTES,
    ) -> dict[str, Any]:
        if max_files < 1 or max_bytes < 1:
            raise ValueError("change inventory limits must be positive")
        workspace = self._active_workspace(lease_id)
        self._require_permission(workspace, "read")
        path = self._registered_worktree(workspace)
        result = self._run_bounded(
            [
                "git",
                "-C",
                str(path),
                "diff",
                "--name-only",
                "-z",
                workspace["base_sha"],
                "HEAD",
                "--",
            ],
            cwd=path,
            timeout_seconds=120,
            max_stdout_bytes=max_bytes,
            max_stderr_bytes=MAX_TEST_STREAM_BYTES,
        )
        if result.exit_code != 0:
            raise WorkspaceError("could not collect changed-file inventory")
        if result.stdout.truncated:
            raise WorkspaceError(
                f"changed-file inventory exceeds {max_bytes} bytes"
            )
        raw_names = [item for item in result.stdout.data.split(b"\0") if item]
        if len(raw_names) > max_files:
            raise WorkspaceError(
                f"changed-file inventory exceeds {max_files} files"
            )
        names = [os.fsdecode(item) for item in raw_names]
        return {
            "lease_id": lease_id,
            "head_sha": self._head_sha(path),
            "files": names,
            "file_count": len(names),
            "inventory_bytes": result.stdout.total_bytes,
            "inventory_sha256": result.stdout.digest,
        }

    def request_merge(self, lease_id: str) -> dict[str, Any]:
        workspace = self._active_workspace(lease_id)
        self._require_permission(workspace, "merge")
        scope = self._merge_scope(workspace)
        return self._create_approval(workspace, "merge", scope)

    def request_discard(self, lease_id: str) -> dict[str, Any]:
        workspace = self._active_workspace(lease_id)
        self._require_permission(workspace, "write")
        scope = self._discard_scope(workspace)
        return self._create_approval(workspace, "discard", scope)

    def approvals(
        self,
        *,
        status: str | None = None,
        lease_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM worktree_approvals"
        where = []
        params: list[Any] = []
        if status:
            if status not in APPROVAL_STATUSES:
                raise ValueError(f"unsupported workspace approval status {status!r}")
            where.append("status = ?")
            params.append(status)
        if lease_id:
            where.append("lease_id = ?")
            params.append(lease_id)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY requested_at DESC, id DESC"
        with self.store.connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._approval_row(row) for row in rows]

    def approval(self, approval_id: str) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM worktree_approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"workspace approval {approval_id!r} not found")
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
            raise WorkspaceError(
                f"workspace approval {approval_id!r} is not pending"
            )
        if approve and confirmation != approval["scope_sha256"]:
            raise WorkspaceError(
                "approval confirmation must exactly match the displayed scope_sha256"
            )
        status = "approved" if approve else "rejected"
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE worktree_approvals
                SET status = ?, decided_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, utc_now(), approval_id),
            ).rowcount
        if not updated:
            raise WorkspaceError(
                f"workspace approval {approval_id!r} changed before decision"
            )
        return self.approval(approval_id)

    def merge(self, approval_id: str) -> dict[str, Any]:
        approval, workspace = self._require_approved_action(
            approval_id,
            action="merge",
        )
        try:
            current_scope = self._merge_scope(workspace)
            self._require_scope_match(approval, current_scope)
            self._consume_approval(approval_id)
            repository = Path(workspace["repository_root"])
            started = time.perf_counter()
            completed = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "merge",
                    "--ff-only",
                    workspace["branch_name"],
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                shell=False,
                check=False,
            )
            result = _CommandResult(
                command=[
                    "git",
                    "-C",
                    str(repository),
                    "merge",
                    "--ff-only",
                    workspace["branch_name"],
                ],
                exit_code=completed.returncode,
                duration_ms=round((time.perf_counter() - started) * 1000),
                stdout=self._capture_text(
                    completed.stdout,
                    MAX_TEST_STREAM_BYTES,
                ),
                stderr=self._capture_text(
                    completed.stderr,
                    MAX_TEST_STREAM_BYTES,
                ),
                timed_out=False,
            )
            evidence = self._record_evidence(
                workspace,
                kind="merge",
                status="passed" if completed.returncode == 0 else "failed",
                result=result,
                metadata={
                    "approval_id": approval_id,
                    "scope_sha256": approval["scope_sha256"],
                },
            )
            if completed.returncode != 0:
                self._mark_approval_failed(
                    approval_id,
                    f"merge failed; evidence_id={evidence['id']}",
                )
                raise WorkspaceError(
                    f"merge failed; evidence_id={evidence['id']}"
                )
            cleanup_errors = self._cleanup_worktree(
                workspace,
                force=False,
                delete_force=False,
            )
            self._finish_workspace(workspace["id"], "merged")
            payload = self.workspace(workspace["id"])
            payload["cleanup_errors"] = cleanup_errors
            return payload
        except Exception as exc:
            if self.approval(approval_id)["status"] == "approved":
                self._mark_approval_stale(approval_id, str(exc))
            raise

    def discard(self, approval_id: str) -> dict[str, Any]:
        approval, workspace = self._require_approved_action(
            approval_id,
            action="discard",
        )
        try:
            current_scope = self._discard_scope(workspace)
            self._require_scope_match(approval, current_scope)
            self._consume_approval(approval_id)
            cleanup_errors = self._cleanup_worktree(
                workspace,
                force=True,
                delete_force=True,
            )
            if cleanup_errors:
                self._mark_approval_failed(
                    approval_id,
                    "; ".join(cleanup_errors),
                )
                raise WorkspaceError(
                    "discard cleanup failed after approval consumption"
                )
            self._finish_workspace(workspace["id"], "discarded")
            return self.workspace(workspace["id"])
        except Exception as exc:
            if self.approval(approval_id)["status"] == "approved":
                self._mark_approval_stale(approval_id, str(exc))
            raise

    def _merge_scope(self, workspace: dict[str, Any]) -> dict[str, Any]:
        repository = Path(workspace["repository_root"])
        path = self._registered_worktree(workspace)
        self._require_clean(repository, "target repository")
        self._require_clean(path, "Agent worktree")
        target_branch = self._git_text(
            repository,
            ["symbolic-ref", "--quiet", "--short", "HEAD"],
            "target repository must be on its original branch",
        )
        if target_branch != workspace["target_branch"]:
            raise WorkspaceError(
                "target repository branch changed since worktree creation"
            )
        target_sha = self._head_sha(repository)
        source_sha = self._head_sha(path)
        if target_sha != workspace["base_sha"]:
            raise WorkspaceError(
                "target repository HEAD changed; create fresh evidence after "
                "manually reconciling the Agent branch"
            )
        if source_sha == target_sha:
            raise WorkspaceError("Agent branch has no committed change to merge")
        if subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "merge-base",
                "--is-ancestor",
                target_sha,
                source_sha,
            ],
            capture_output=True,
            shell=False,
            check=False,
        ).returncode != 0:
            raise WorkspaceError("Agent branch is not a fast-forward of target HEAD")
        diff_evidence = self._latest_evidence(
            workspace["id"],
            kind="diff",
            status="passed",
        )
        test_evidence = self._latest_evidence(
            workspace["id"],
            kind="test",
            status="passed",
        )
        if not diff_evidence or (
            diff_evidence["metadata"].get("head_sha") != source_sha
            or not diff_evidence["metadata"].get("worktree_clean")
            or diff_evidence["metadata"].get("base_sha") != target_sha
        ):
            raise WorkspaceError(
                "merge requires current clean diff evidence for the exact branch HEAD"
            )
        if not test_evidence or (
            test_evidence["metadata"].get("head_sha") != source_sha
            or test_evidence["metadata"].get("status_sha256")
            != sha256(b"").hexdigest()
        ):
            raise WorkspaceError(
                "merge requires a passing test captured at the exact clean branch HEAD"
            )
        return {
            "action": "merge",
            "lease_id": workspace["id"],
            "agent_id": workspace["agent_id"],
            "target_branch": target_branch,
            "target_sha": target_sha,
            "source_branch": workspace["branch_name"],
            "source_sha": source_sha,
            "diff_evidence_id": diff_evidence["id"],
            "diff_sha256": diff_evidence["stdout_sha256"],
            "test_evidence_id": test_evidence["id"],
            "test_stdout_sha256": test_evidence["stdout_sha256"],
            "test_stderr_sha256": test_evidence["stderr_sha256"],
        }

    def _discard_scope(self, workspace: dict[str, Any]) -> dict[str, Any]:
        path = self._registered_worktree(workspace)
        return {
            "action": "discard",
            "lease_id": workspace["id"],
            "agent_id": workspace["agent_id"],
            "target_branch": workspace["target_branch"],
            "target_sha": self._head_sha(Path(workspace["repository_root"])),
            "source_branch": workspace["branch_name"],
            "source_sha": self._head_sha(path),
            "workspace_state_sha256": self._workspace_state_sha256(path),
        }

    def _create_approval(
        self,
        workspace: dict[str, Any],
        action: str,
        scope: dict[str, Any],
    ) -> dict[str, Any]:
        if action not in APPROVAL_ACTIONS:
            raise ValueError(f"unsupported workspace action {action!r}")
        encoded = self._canonical(scope)
        approval_id = str(uuid4())
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO worktree_approvals(
                    id, lease_id, action, scope_sha256, scope_json, status,
                    requested_at, decided_at, consumed_at, failure
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL, NULL, NULL)
                """,
                (
                    approval_id,
                    workspace["id"],
                    action,
                    sha256(encoded).hexdigest(),
                    encoded.decode("utf-8"),
                    utc_now(),
                ),
            )
        return self.approval(approval_id)

    def _require_approved_action(
        self,
        approval_id: str,
        *,
        action: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        approval = self.approval(approval_id)
        if approval["status"] != "approved" or approval["consumed_at"]:
            raise WorkspaceError(
                f"workspace approval {approval_id!r} is not approved and unused"
            )
        if approval["action"] != action:
            raise WorkspaceError(
                f"workspace approval {approval_id!r} is for "
                f"{approval['action']!r}, not {action!r}"
            )
        return approval, self._active_workspace(approval["lease_id"])

    def _require_scope_match(
        self,
        approval: dict[str, Any],
        current_scope: dict[str, Any],
    ) -> None:
        current_digest = sha256(self._canonical(current_scope)).hexdigest()
        if current_digest != approval["scope_sha256"]:
            raise WorkspaceError(
                "workspace state changed after approval; request a fresh approval"
            )

    def _consume_approval(self, approval_id: str) -> None:
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE worktree_approvals
                SET status = 'consumed', consumed_at = ?
                WHERE id = ? AND status = 'approved' AND consumed_at IS NULL
                """,
                (utc_now(), approval_id),
            ).rowcount
        if not updated:
            raise WorkspaceError(
                f"workspace approval {approval_id!r} was already consumed"
            )

    def _mark_approval_stale(self, approval_id: str, failure: str) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE worktree_approvals
                SET status = 'stale', failure = ?
                WHERE id = ? AND status = 'approved'
                """,
                (failure[:2000], approval_id),
            )

    def _mark_approval_failed(self, approval_id: str, failure: str) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE worktree_approvals
                SET status = 'failed', failure = ?
                WHERE id = ? AND status = 'consumed'
                """,
                (failure[:2000], approval_id),
            )

    def _record_evidence(
        self,
        workspace: dict[str, Any],
        *,
        kind: str,
        status: str,
        result: _CommandResult,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        evidence_id = str(uuid4())
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO worktree_evidence(
                    id, lease_id, kind, status, command_json, exit_code,
                    duration_ms, stdout_text, stderr_text, stdout_bytes,
                    stderr_bytes, stdout_sha256, stderr_sha256, metadata_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    workspace["id"],
                    kind,
                    status,
                    json.dumps(result.command, ensure_ascii=False),
                    result.exit_code,
                    result.duration_ms,
                    result.stdout.text,
                    result.stderr.text,
                    result.stdout.total_bytes,
                    result.stderr.total_bytes,
                    result.stdout.digest,
                    result.stderr.digest,
                    json.dumps(
                        {
                            **metadata,
                            "stdout_truncated": result.stdout.truncated,
                            "stderr_truncated": result.stderr.truncated,
                            "timed_out": result.timed_out,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    utc_now(),
                ),
            )
            conn.execute(
                "UPDATE worktree_leases SET updated_at = ? WHERE id = ?",
                (utc_now(), workspace["id"]),
            )
        return self.evidence(workspace["id"])[0]

    def _latest_evidence(
        self,
        lease_id: str,
        *,
        kind: str,
        status: str,
    ) -> dict[str, Any] | None:
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM worktree_evidence
                WHERE lease_id = ? AND kind = ? AND status = ?
                ORDER BY created_at DESC, id DESC LIMIT 1
                """,
                (lease_id, kind, status),
            ).fetchone()
        return self._evidence_row(row) if row else None

    def _cleanup_worktree(
        self,
        workspace: dict[str, Any],
        *,
        force: bool,
        delete_force: bool,
    ) -> list[str]:
        repository = Path(workspace["repository_root"])
        path = Path(workspace["worktree_path"])
        remove = [
            "git",
            "-C",
            str(repository),
            "worktree",
            "remove",
        ]
        if force:
            remove.append("--force")
        remove.append(str(path))
        delete = [
            "git",
            "-C",
            str(repository),
            "branch",
            "-D" if delete_force else "-d",
            workspace["branch_name"],
        ]
        errors = []
        for command in (remove, delete):
            completed = subprocess.run(
                command,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                shell=False,
                check=False,
            )
            if completed.returncode != 0:
                errors.append(completed.stderr.strip()[-1000:])
        return [item for item in errors if item]

    def _finish_workspace(self, lease_id: str, status: str) -> None:
        if status not in {"merged", "discarded", "failed"}:
            raise ValueError(f"unsupported terminal worktree status {status!r}")
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE worktree_leases
                SET status = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, now, now, lease_id),
            )

    def _active_workspace(self, lease_id: str) -> dict[str, Any]:
        workspace = self.workspace(lease_id)
        if workspace["status"] != "active":
            raise WorkspaceError(
                f"worktree lease {lease_id!r} is {workspace['status']!r}"
            )
        return workspace

    @staticmethod
    def _require_permission(
        workspace: dict[str, Any],
        permission: str,
    ) -> None:
        if not workspace["permissions"][permission]:
            raise WorkspaceError(
                f"worktree lease {workspace['id']!r} lacks {permission} permission"
            )

    def _registered_worktree(self, workspace: dict[str, Any]) -> Path:
        path = Path(workspace["worktree_path"]).resolve(strict=True)
        self._require_contained(path, self.worktree_root)
        actual_root = self._repository_root(path)
        if not self._same_path(actual_root, path):
            raise WorkspaceError("recorded Agent worktree path is not a Git root")
        branch = self._git_text(
            path,
            ["symbolic-ref", "--quiet", "--short", "HEAD"],
            "Agent worktree must remain on its assigned branch",
        )
        if branch != workspace["branch_name"]:
            raise WorkspaceError("Agent worktree branch changed outside Model Council")
        return path

    def _repository_root(self, path: str | Path) -> Path:
        candidate = Path(path).resolve(strict=True)
        root_text = self._git_text(
            candidate,
            ["rev-parse", "--show-toplevel"],
            f"{candidate} is not a Git repository",
        )
        return Path(root_text).resolve(strict=True)

    def _require_runtime_path_ignored(
        self,
        repository: Path,
        worktree_path: Path,
    ) -> None:
        roots = [repository]
        containing = self._containing_repository(self.worktree_root)
        if containing and not any(
            self._same_path(containing, item) for item in roots
        ):
            roots.append(containing)
        for root in roots:
            try:
                worktree_path.relative_to(root)
            except ValueError:
                continue
            completed = subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "check-ignore",
                    "--quiet",
                    "--no-index",
                    "--",
                    str(worktree_path),
                ],
                capture_output=True,
                shell=False,
                check=False,
            )
            if completed.returncode != 0:
                raise WorkspaceError(
                    "worktree runtime path is inside a Git repository but is "
                    "not ignored"
                )

    @staticmethod
    def _containing_repository(path: Path) -> Path | None:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            shell=False,
            check=False,
        )
        if completed.returncode != 0:
            return None
        return Path(completed.stdout.strip()).resolve(strict=True)

    @staticmethod
    def _require_contained(path: Path, root: Path) -> None:
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise WorkspaceError(
                "worktree path escaped the configured runtime root"
            ) from exc

    @staticmethod
    def _same_path(left: Path, right: Path) -> bool:
        return os.path.normcase(str(left.resolve())) == os.path.normcase(
            str(right.resolve())
        )

    @staticmethod
    def _validate_ref(ref: str) -> None:
        if (
            not _SAFE_REF.fullmatch(ref)
            or ".." in ref
            or "@{" in ref
            or "//" in ref
            or ref.endswith(("/", "."))
        ):
            raise ValueError("base_ref contains unsupported Git ref syntax")

    @staticmethod
    def _branch_name(agent_id: str, lease_id: str) -> str:
        del agent_id
        return f"model-council/worktree-{lease_id[:12]}"

    @staticmethod
    def _validate_command(command: list[str]) -> list[str]:
        if not isinstance(command, list) or not command or not all(
            isinstance(item, str) and item for item in command
        ):
            raise ValueError("test command must be a non-empty string array")
        for item in command:
            normalized = item.lower()
            if normalized in _SENSITIVE_FLAGS or any(
                normalized.startswith(f"{flag}=") for flag in _SENSITIVE_FLAGS
            ):
                raise ValueError(
                    "test command must not contain inline credential arguments"
                )
        return list(command)

    @staticmethod
    def _status_bytes(path: Path) -> bytes:
        result = WorkspaceService._run_bounded(
            [
                "git",
                "-C",
                str(path),
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
            ],
            cwd=path,
            timeout_seconds=120,
            max_stdout_bytes=MAX_STATUS_BYTES,
            max_stderr_bytes=MAX_TEST_STREAM_BYTES,
        )
        if result.exit_code != 0:
            raise WorkspaceError("could not inspect Git worktree status")
        if result.stdout.truncated:
            raise WorkspaceError(
                f"Git worktree status exceeds {MAX_STATUS_BYTES} bytes"
            )
        return result.stdout.data

    def _workspace_state_sha256(self, path: Path) -> str:
        digest = sha256()
        status = self._status_bytes(path)
        digest.update(b"status\0")
        digest.update(status)
        tracked = self._run_bounded(
            [
                "git",
                "-C",
                str(path),
                "diff",
                "--binary",
                "--no-ext-diff",
                "HEAD",
                "--",
            ],
            cwd=path,
            timeout_seconds=120,
            max_stdout_bytes=0,
            max_stderr_bytes=MAX_TEST_STREAM_BYTES,
        )
        if tracked.exit_code != 0:
            raise WorkspaceError("could not hash tracked worktree changes")
        digest.update(b"tracked\0")
        digest.update(tracked.stdout.digest.encode("ascii"))
        digest.update(str(tracked.stdout.total_bytes).encode("ascii"))
        untracked = self._run_bounded(
            [
                "git",
                "-C",
                str(path),
                "ls-files",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            cwd=path,
            timeout_seconds=120,
            max_stdout_bytes=MAX_STATUS_BYTES,
            max_stderr_bytes=MAX_TEST_STREAM_BYTES,
        )
        if untracked.exit_code != 0:
            raise WorkspaceError("could not enumerate untracked worktree files")
        if untracked.stdout.truncated:
            raise WorkspaceError(
                f"untracked filename inventory exceeds {MAX_STATUS_BYTES} bytes"
            )
        names = [item for item in untracked.stdout.data.split(b"\0") if item]
        if len(names) > MAX_DISCARD_FILES:
            raise WorkspaceError(
                f"discard approval supports at most {MAX_DISCARD_FILES} "
                "untracked files"
            )
        total_bytes = 0
        for raw_name in sorted(names):
            relative = Path(os.fsdecode(raw_name))
            candidate = (path / relative).resolve(strict=True)
            self._require_contained(candidate, path)
            digest.update(b"untracked\0")
            digest.update(raw_name)
            digest.update(b"\0")
            if candidate.is_symlink():
                target = os.readlink(candidate).encode(
                    "utf-8",
                    errors="surrogatepass",
                )
                total_bytes += len(target)
                digest.update(target)
                continue
            if not candidate.is_file():
                raise WorkspaceError(
                    "discard approval supports only regular files and symlinks"
                )
            with candidate.open("rb") as handle:
                while True:
                    chunk = handle.read(64 * 1024)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_DISCARD_HASH_BYTES:
                        raise WorkspaceError(
                            "discard approval untracked content exceeds "
                            f"{MAX_DISCARD_HASH_BYTES} bytes"
                        )
                    digest.update(chunk)
        return digest.hexdigest()

    def _require_clean(self, path: Path, label: str) -> None:
        if self._status_bytes(path):
            raise WorkspaceError(f"{label} must be clean")

    def _head_sha(self, path: Path) -> str:
        return self._git_text(
            path,
            ["rev-parse", "--verify", "HEAD^{commit}"],
            "Git HEAD is not a commit",
        )

    @staticmethod
    def _git_text(path: Path, args: list[str], error: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(path), *args],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            shell=False,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip()[-1000:]
            raise WorkspaceError(f"{error}: {detail}" if detail else error)
        return completed.stdout.strip()

    @staticmethod
    def _run_bounded(
        command: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
    ) -> _CommandResult:
        started = time.perf_counter()
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        captures: dict[str, _StreamCapture] = {}
        threads = [
            threading.Thread(
                target=WorkspaceService._drain_stream,
                args=(process.stdout, max_stdout_bytes, captures, "stdout"),
                daemon=True,
            ),
            threading.Thread(
                target=WorkspaceService._drain_stream,
                args=(process.stderr, max_stderr_bytes, captures, "stderr"),
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()
        timed_out = False
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            exit_code = process.wait()
        for thread in threads:
            thread.join(timeout=5)
        empty = WorkspaceService._capture_text("", 1)
        return _CommandResult(
            command=list(command),
            exit_code=exit_code,
            duration_ms=round((time.perf_counter() - started) * 1000),
            stdout=captures.get("stdout", empty),
            stderr=captures.get("stderr", empty),
            timed_out=timed_out,
        )

    @staticmethod
    def _drain_stream(
        stream: BinaryIO | None,
        limit: int,
        target: dict[str, _StreamCapture],
        key: str,
    ) -> None:
        digest = sha256()
        total = 0
        retained = bytearray()
        if stream is not None:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                total += len(chunk)
                digest.update(chunk)
                remaining = limit - len(retained)
                if remaining > 0:
                    retained.extend(chunk[:remaining])
            stream.close()
        target[key] = _StreamCapture(
            data=bytes(retained),
            text=bytes(retained).decode("utf-8", errors="replace"),
            total_bytes=total,
            digest=digest.hexdigest(),
            truncated=total > len(retained),
        )

    @staticmethod
    def _capture_text(text: str, limit: int) -> _StreamCapture:
        encoded = text.encode("utf-8")
        return _StreamCapture(
            data=encoded[:limit],
            text=encoded[:limit].decode("utf-8", errors="replace"),
            total_bytes=len(encoded),
            digest=sha256(encoded).hexdigest(),
            truncated=len(encoded) > limit,
        )

    @staticmethod
    def _canonical(value: dict[str, Any]) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _workspace_query() -> str:
        return """
            SELECT l.*, p.read_enabled, p.write_enabled, p.test_enabled,
                   p.merge_enabled, p.source AS permission_source,
                   p.updated_at AS permission_updated_at
            FROM worktree_leases l
            JOIN worktree_permissions p ON p.lease_id = l.id
        """

    @staticmethod
    def _workspace_row(row: Any) -> dict[str, Any]:
        item = dict(row)
        item["permissions"] = {
            "read": bool(item.pop("read_enabled")),
            "write": bool(item.pop("write_enabled")),
            "test": bool(item.pop("test_enabled")),
            "merge": bool(item.pop("merge_enabled")),
            "source": item.pop("permission_source"),
            "updated_at": item.pop("permission_updated_at"),
        }
        return item

    @staticmethod
    def _evidence_row(row: Any) -> dict[str, Any]:
        item = dict(row)
        item["command"] = json.loads(item.pop("command_json"))
        item["metadata"] = json.loads(item.pop("metadata_json"))
        return item

    @staticmethod
    def _approval_row(row: Any) -> dict[str, Any]:
        item = dict(row)
        item["scope"] = json.loads(item.pop("scope_json"))
        return item
