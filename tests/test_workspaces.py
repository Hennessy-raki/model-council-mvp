from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from model_council.adapters.cli import CliAdapter
from model_council.store import CouncilStore
from model_council.types import AgentCard, AgentRequest
from model_council.workspaces import WorkspaceError, WorkspaceService


def git(path: Path, *args: str) -> str:
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
        raise AssertionError(completed.stderr)
    return completed.stdout.strip()


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.fixture = (
            self.project_root / "tests" / "fixtures" / "fake_codex_cli.py"
        )

    def _repository(self, root: Path) -> Path:
        repository = root / "synthetic-repository"
        repository.mkdir()
        git(repository, "init", "-b", "main")
        git(repository, "config", "user.name", "Synthetic Tester")
        git(
            repository,
            "config",
            "user.email",
            "model-council@users.noreply.github.com",
        )
        (repository / ".gitignore").write_text(
            "runtime/\n",
            encoding="utf-8",
        )
        (repository / "example.txt").write_text("base\n", encoding="utf-8")
        git(repository, "add", "--all")
        git(repository, "commit", "-m", "synthetic baseline")
        return repository

    def _service(self, repository: Path) -> WorkspaceService:
        return WorkspaceService(
            CouncilStore(repository / "runtime" / "council.db")
        )

    @staticmethod
    def _grant_all(service: WorkspaceService, lease_id: str) -> None:
        service.set_permission(
            lease_id,
            permission="write",
            enabled=True,
        )
        service.set_permission(
            lease_id,
            permission="test",
            enabled=True,
        )
        service.set_permission(
            lease_id,
            permission="merge",
            enabled=True,
        )

    def test_prepare_is_read_only_and_adapter_binding_checks_sandbox(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            service = self._service(repository)
            lease = service.prepare(
                repository=repository,
                agent_id="writer",
            )

            self.assertEqual(
                lease["permissions"],
                {
                    "read": True,
                    "write": False,
                    "test": False,
                    "merge": False,
                    "source": "default",
                    "updated_at": lease["permissions"]["updated_at"],
                },
            )
            self.assertTrue(Path(lease["worktree_path"]).is_dir())
            self.assertTrue(
                lease["branch_name"].startswith("model-council/worktree-")
            )
            self.assertNotIn("writer", lease["branch_name"])
            self.assertTrue(
                Path(lease["worktree_path"]).is_relative_to(
                    repository / "runtime" / "worktrees"
                )
            )
            request = AgentRequest(
                run_id="synthetic-run",
                task_id="synthetic-task",
                mode="work",
                goal="Read a synthetic project",
                instruction="Return a fixture response",
                sender="manager",
                recipient="writer",
            )
            read_only = CliAdapter(
                AgentCard("writer", "writer", "synthetic"),
                {
                    "command": [
                        sys.executable,
                        str(self.fixture),
                        "--sandbox",
                        "read-only",
                    ],
                    "output_format": "codex_jsonl",
                },
                repository,
            )
            response = service.invoke_cli(
                lease["id"],
                read_only,
                request,
                write=False,
            )
            self.assertIn("deterministic boundaries", response.content)
            with self.assertRaisesRegex(WorkspaceError, "lacks write"):
                service.invoke_cli(
                    lease["id"],
                    read_only,
                    request,
                    write=True,
                )

            service.set_permission(
                lease["id"],
                permission="write",
                enabled=True,
            )
            workspace_write = CliAdapter(
                AgentCard("writer", "writer", "synthetic"),
                {
                    "command": [
                        sys.executable,
                        str(self.fixture),
                        "--sandbox",
                        "workspace-write",
                    ],
                    "output_format": "codex_jsonl",
                },
                repository,
            )
            response = service.invoke_cli(
                lease["id"],
                workspace_write,
                request,
                write=True,
            )
            self.assertIn("deterministic boundaries", response.content)
            with self.assertRaisesRegex(WorkspaceError, "belongs to another"):
                service.authorized_path(
                    lease["id"],
                    agent_id="another-agent",
                    permission="read",
                )

    def test_bounded_test_diff_checkpoint_and_single_use_merge(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            service = self._service(repository)
            lease = service.prepare(
                repository=repository,
                agent_id="writer",
            )
            self._grant_all(service, lease["id"])
            worktree = Path(lease["worktree_path"])
            (worktree / "example.txt").write_text(
                "base\nagent change\n",
                encoding="utf-8",
            )
            checkpoint = service.checkpoint(
                lease["id"],
                message="Apply synthetic Agent change",
            )
            self.assertEqual(checkpoint["status"], "passed")
            test = service.run_test(
                lease["id"],
                command=[
                    sys.executable,
                    "-c",
                    "print('x' * 70000)",
                ],
                timeout_seconds=30,
            )
            self.assertEqual(test["status"], "passed")
            self.assertTrue(test["metadata"]["stdout_truncated"])
            self.assertGreater(test["stdout_bytes"], len(test["stdout_text"]))
            diff = service.collect_diff(lease["id"])
            self.assertIn("agent change", diff["stdout_text"])
            approval = service.request_merge(lease["id"])
            with self.assertRaisesRegex(WorkspaceError, "exactly match"):
                service.decide(
                    approval["id"],
                    approve=True,
                    confirmation="wrong",
                )
            service.decide(
                approval["id"],
                approve=True,
                confirmation=approval["scope_sha256"],
            )
            merged = service.merge(approval["id"])
            self.assertEqual(merged["status"], "merged")
            self.assertEqual(
                (repository / "example.txt").read_text(encoding="utf-8"),
                "base\nagent change\n",
            )
            self.assertFalse(worktree.exists())
            with self.assertRaisesRegex(WorkspaceError, "not approved and unused"):
                service.merge(approval["id"])

    def test_merge_requires_current_clean_test_and_diff_evidence(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            service = self._service(repository)
            lease = service.prepare(
                repository=repository,
                agent_id="writer",
            )
            self._grant_all(service, lease["id"])
            worktree = Path(lease["worktree_path"])
            (worktree / "example.txt").write_text("changed\n", encoding="utf-8")
            service.checkpoint(lease["id"], message="Synthetic change")
            with self.assertRaisesRegex(WorkspaceError, "diff evidence"):
                service.request_merge(lease["id"])
            service.collect_diff(lease["id"])
            with self.assertRaisesRegex(WorkspaceError, "passing test"):
                service.request_merge(lease["id"])
            failed = service.run_test(
                lease["id"],
                command=[sys.executable, "-c", "raise SystemExit(3)"],
            )
            self.assertEqual(failed["status"], "failed")
            with self.assertRaisesRegex(WorkspaceError, "passing test"):
                service.request_merge(lease["id"])
            service.run_test(
                lease["id"],
                command=[sys.executable, "-c", "print('passed')"],
            )
            approval = service.request_merge(lease["id"])
            service.decide(
                approval["id"],
                approve=True,
                confirmation=approval["scope_sha256"],
            )
            (worktree / "late.txt").write_text("scope drift\n", encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceError, "must be clean"):
                service.merge(approval["id"])
            self.assertEqual(
                service.approval(approval["id"])["status"],
                "stale",
            )

    def test_discard_requires_exact_approval_and_detects_scope_drift(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            service = self._service(repository)
            lease = service.prepare(
                repository=repository,
                agent_id="writer",
            )
            service.set_permission(
                lease["id"],
                permission="write",
                enabled=True,
            )
            worktree = Path(lease["worktree_path"])
            (worktree / "private-note.txt").write_text(
                "synthetic only\n",
                encoding="utf-8",
            )
            approval = service.request_discard(lease["id"])
            service.decide(
                approval["id"],
                approve=True,
                confirmation=approval["scope_sha256"],
            )
            (worktree / "private-note.txt").write_text(
                "changed after approval\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(WorkspaceError, "state changed"):
                service.discard(approval["id"])
            self.assertEqual(
                service.approval(approval["id"])["status"],
                "stale",
            )
            fresh = service.request_discard(lease["id"])
            service.decide(
                fresh["id"],
                approve=True,
                confirmation=fresh["scope_sha256"],
            )
            discarded = service.discard(fresh["id"])
            self.assertEqual(discarded["status"], "discarded")
            self.assertFalse(worktree.exists())

    def test_permission_dependencies_and_command_validation(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            service = self._service(repository)
            lease = service.prepare(
                repository=repository,
                agent_id="writer",
            )
            with self.assertRaisesRegex(WorkspaceError, "requires read, write"):
                service.set_permission(
                    lease["id"],
                    permission="merge",
                    enabled=True,
                )
            with self.assertRaisesRegex(WorkspaceError, "lacks test"):
                service.run_test(
                    lease["id"],
                    command=[sys.executable, "-c", "print('no')"],
                )
            service.set_permission(
                lease["id"],
                permission="test",
                enabled=True,
            )
            with self.assertRaisesRegex(ValueError, "credential"):
                service.run_test(
                    lease["id"],
                    command=["tool", "--token=not-allowed"],
                )
            with self.assertRaisesRegex(ValueError, "Git ref syntax"):
                service.prepare(
                    repository=repository,
                    agent_id="writer",
                    base_ref="--help",
                )

    def test_workspace_cli_operates_on_synthetic_repository(self):
        from contextlib import redirect_stdout
        from io import StringIO

        from model_council.cli import main

        with TemporaryDirectory() as temp:
            root = Path(temp)
            repository = self._repository(root)
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "state_dir": str(repository / "runtime"),
                        "manager": "manager",
                        "agents": {"manager": {"type": "mock"}},
                    }
                ),
                encoding="utf-8",
            )
            output = StringIO()
            with redirect_stdout(output):
                main(
                    [
                        "workspace",
                        "prepare",
                        str(repository),
                        "writer",
                        "--config",
                        str(config),
                    ]
                )
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["agent_id"], "writer")
            self.assertTrue(payload["permissions"]["read"])
            self.assertFalse(payload["permissions"]["write"])

    def test_runtime_root_must_be_ignored_by_its_containing_repository(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            repository = self._repository(root)
            control = root / "public-control-repository"
            control.mkdir()
            git(control, "init", "-b", "main")
            git(control, "config", "user.name", "Synthetic Tester")
            git(
                control,
                "config",
                "user.email",
                "model-council@users.noreply.github.com",
            )
            (control / "README.md").write_text("control\n", encoding="utf-8")
            git(control, "add", "--all")
            git(control, "commit", "-m", "control baseline")
            service = WorkspaceService(
                CouncilStore(control / "state" / "council.db")
            )
            with self.assertRaisesRegex(WorkspaceError, "not ignored"):
                service.prepare(
                    repository=repository,
                    agent_id="writer",
                )

            (control / ".gitignore").write_text("state/\n", encoding="utf-8")
            lease = service.prepare(
                repository=repository,
                agent_id="writer",
            )
            service.set_permission(
                lease["id"],
                permission="write",
                enabled=True,
            )
            approval = service.request_discard(lease["id"])
            service.decide(
                approval["id"],
                approve=True,
                confirmation=approval["scope_sha256"],
            )
            self.assertEqual(
                service.discard(approval["id"])["status"],
                "discarded",
            )


if __name__ == "__main__":
    unittest.main()
