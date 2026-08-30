from __future__ import annotations

import subprocess
import sys
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from model_council.repair import RepairError, RepairPolicy, RepairService
from model_council.cli import main
from model_council.store import CouncilStore
from model_council.workspaces import WorkspaceService


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


class RepairTests(unittest.TestCase):
    def _repository(self, root: Path) -> Path:
        repository = root / "synthetic-repair-repository"
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
        (repository / "result.txt").write_text(
            "initial\n",
            encoding="utf-8",
        )
        git(repository, "add", "--all")
        git(repository, "commit", "-m", "synthetic repair baseline")
        return repository

    def _services(
        self,
        repository: Path,
    ) -> tuple[WorkspaceService, RepairService, dict]:
        store = CouncilStore(repository / "runtime" / "council.db")
        workspaces = WorkspaceService(store)
        lease = workspaces.prepare(
            repository=repository,
            agent_id="writer",
        )
        for permission in ("write", "test", "merge"):
            workspaces.set_permission(
                lease["id"],
                permission=permission,
                enabled=True,
            )
        return workspaces, RepairService(store, workspaces), lease

    @staticmethod
    def _test_command(expected: str = "good\n") -> list[str]:
        script = (
            "import pathlib,sys;"
            f"sys.exit(0 if pathlib.Path('result.txt').read_text() == {expected!r} "
            "else 1)"
        )
        return [sys.executable, "-c", script]

    @staticmethod
    def _usage(tokens: int) -> dict:
        return {
            "metadata": {
                "usage": {"total_tokens": tokens},
                "cost_amount": "0",
                "cost_currency": "USD",
            }
        }

    def test_two_iteration_repair_accepts_and_requests_exact_merge(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            workspaces, repairs, lease = self._services(repository)
            session = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Produce the accepted synthetic result",
                test_command=self._test_command(),
                policy=RepairPolicy(
                    max_iterations=3,
                    max_total_tokens=100,
                    max_total_cost="1",
                    cost_currency="USD",
                ),
            )
            writer_calls = []
            reviewer_calls = []

            def writer(context):
                writer_calls.append(context["iteration_number"])
                value = "bad\n" if context["iteration_number"] == 1 else "good\n"
                Path(context["worktree_path"], "result.txt").write_text(
                    value,
                    encoding="utf-8",
                )
                return {
                    "content": f"writer iteration {context['iteration_number']}",
                    **self._usage(10),
                }

            def reviewer(bundle):
                reviewer_calls.append(bundle["iteration_number"])
                if bundle["test"]["status"] == "passed":
                    return {
                        "decision": "accept",
                        "feedback": "Synthetic evidence accepted.",
                        **self._usage(5),
                    }
                return {
                    "decision": "repair",
                    "feedback": "Make result.txt equal the tested value.",
                    **self._usage(5),
                }

            snapshot = repairs.run_local_until_terminal(
                session["id"],
                writer=writer,
                reviewer=reviewer,
            )
            self.assertEqual(snapshot["session"]["status"], "accepted")
            self.assertEqual(snapshot["session"]["iteration_count"], 2)
            self.assertEqual(snapshot["session"]["total_tokens"], 30)
            self.assertTrue(snapshot["session"]["total_tokens_known"])
            self.assertEqual(writer_calls, [1, 2])
            self.assertEqual(reviewer_calls, [1, 2])
            self.assertEqual(
                [item["status"] for item in snapshot["iterations"]],
                ["repair_requested", "accepted"],
            )

            approval = repairs.request_merge(session["id"])
            workspaces.decide(
                approval["id"],
                approve=True,
                confirmation=approval["scope_sha256"],
            )
            merged = workspaces.merge(approval["id"])
            self.assertEqual(merged["status"], "merged")
            self.assertEqual(
                (repository / "result.txt").read_text(encoding="utf-8"),
                "good\n",
            )

    def test_iteration_limit_stops_without_automatic_merge_or_discard(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            workspaces, repairs, lease = self._services(repository)
            session = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Exercise the iteration bound",
                test_command=[sys.executable, "-c", "raise SystemExit(0)"],
                policy=RepairPolicy(max_iterations=2),
            )
            calls = []

            def writer(context):
                calls.append(context["iteration_number"])
                Path(context["worktree_path"], "result.txt").write_text(
                    f"iteration {context['iteration_number']}\n",
                    encoding="utf-8",
                )
                return self._usage(1)

            snapshot = repairs.run_local_until_terminal(
                session["id"],
                writer=writer,
                reviewer=lambda bundle: {
                    "decision": "repair",
                    "feedback": "Another bounded iteration is required.",
                    **self._usage(1),
                },
            )
            self.assertEqual(snapshot["session"]["status"], "limit_reached")
            self.assertEqual(snapshot["session"]["iteration_count"], 2)
            self.assertEqual(calls, [1, 2])
            self.assertEqual(
                workspaces.workspace(lease["id"])["status"],
                "active",
            )
            self.assertEqual(
                workspaces.approvals(lease_id=lease["id"]),
                [],
            )

    def test_changed_file_limit_stops_before_reviewer(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            _, repairs, lease = self._services(repository)
            session = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Exercise changed-file limits",
                test_command=[sys.executable, "-c", "raise SystemExit(0)"],
                policy=RepairPolicy(max_changed_files=1),
            )
            reviewer_called = False

            def writer(context):
                root = Path(context["worktree_path"])
                (root / "one.txt").write_text("one\n", encoding="utf-8")
                (root / "two.txt").write_text("two\n", encoding="utf-8")
                return self._usage(1)

            def reviewer(bundle):
                nonlocal reviewer_called
                reviewer_called = True
                return {"decision": "accept", "feedback": ""}

            snapshot = repairs.run_local_until_terminal(
                session["id"],
                writer=writer,
                reviewer=reviewer,
            )
            self.assertEqual(snapshot["session"]["status"], "limit_reached")
            self.assertFalse(reviewer_called)
            self.assertEqual(
                snapshot["iterations"][0]["changed_file_count"],
                2,
            )

    def test_unknown_usage_blocks_followup_under_hard_token_budget(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            _, repairs, lease = self._services(repository)
            session = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Exercise conservative token budgeting",
                test_command=[sys.executable, "-c", "raise SystemExit(0)"],
                policy=RepairPolicy(max_total_tokens=100),
            )
            reviewer_called = False

            def writer(context):
                Path(context["worktree_path"], "result.txt").write_text(
                    "changed\n",
                    encoding="utf-8",
                )
                return {"content": "usage intentionally unavailable"}

            def reviewer(bundle):
                nonlocal reviewer_called
                reviewer_called = True
                return {"decision": "accept", "feedback": ""}

            snapshot = repairs.run_local_until_terminal(
                session["id"],
                writer=writer,
                reviewer=reviewer,
            )
            self.assertEqual(snapshot["session"]["status"], "limit_reached")
            self.assertFalse(snapshot["session"]["total_tokens_known"])
            self.assertFalse(reviewer_called)
            self.assertIn("unavailable", snapshot["session"]["error"])

    def test_missing_currency_blocks_followup_under_hard_cost_budget(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            _, repairs, lease = self._services(repository)
            session = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Exercise conservative cost budgeting",
                test_command=[sys.executable, "-c", "raise SystemExit(0)"],
                policy=RepairPolicy(
                    max_total_cost="1",
                    cost_currency="USD",
                ),
            )
            reviewer_called = False

            def writer(context):
                Path(context["worktree_path"], "result.txt").write_text(
                    "changed\n",
                    encoding="utf-8",
                )
                return {
                    "metadata": {
                        "usage": {"total_tokens": 1},
                        "cost_amount": "0.1",
                    }
                }

            def reviewer(bundle):
                nonlocal reviewer_called
                reviewer_called = True
                return {"decision": "accept", "feedback": ""}

            snapshot = repairs.run_local_until_terminal(
                session["id"],
                writer=writer,
                reviewer=reviewer,
            )
            self.assertEqual(snapshot["session"]["status"], "limit_reached")
            self.assertFalse(snapshot["session"]["total_cost_known"])
            self.assertFalse(reviewer_called)
            self.assertIn("cost is unavailable", snapshot["session"]["error"])

    def test_dirty_writer_interruption_can_be_explicitly_captured(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            _, repairs, lease = self._services(repository)
            session = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Recover a synthetic interrupted writer",
                test_command=self._test_command(),
            )
            repairs.begin_iteration(session["id"])
            context = repairs.writer_context(session["id"])
            Path(context["worktree_path"], "result.txt").write_text(
                "good\n",
                encoding="utf-8",
            )

            inspection = repairs.recover(session["id"], action="inspect")
            self.assertEqual(inspection["phase"], "writer")
            self.assertTrue(inspection["can_capture"])
            self.assertFalse(inspection["can_retry"])
            snapshot = repairs.recover(session["id"], action="capture")
            self.assertEqual(snapshot["session"]["status"], "waiting_review")
            accepted = repairs.submit_review(
                session["id"],
                decision="accept",
                feedback="Recovered evidence accepted.",
                reviewer_result=self._usage(1),
            )
            self.assertEqual(accepted["session"]["status"], "accepted")

    def test_reviewer_interruption_reuses_captured_evidence(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            _, repairs, lease = self._services(repository)
            session = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Recover a synthetic reviewer interruption",
                test_command=self._test_command(),
            )

            def writer(context):
                Path(context["worktree_path"], "result.txt").write_text(
                    "good\n",
                    encoding="utf-8",
                )
                return self._usage(1)

            snapshot = repairs.run_local_until_terminal(
                session["id"],
                writer=writer,
                reviewer=lambda bundle: (_ for _ in ()).throw(
                    RuntimeError("synthetic reviewer interruption")
                ),
            )
            self.assertEqual(
                snapshot["session"]["status"],
                "recovery_required",
            )
            inspection = repairs.recover(session["id"], action="inspect")
            self.assertEqual(inspection["phase"], "reviewer")
            self.assertTrue(inspection["can_retry"])
            recovered = repairs.recover(session["id"], action="retry")
            self.assertEqual(
                recovered["session"]["status"],
                "waiting_review",
            )
            accepted = repairs.submit_review(
                session["id"],
                decision="accept",
                feedback="Retry accepted existing evidence.",
                reviewer_result=self._usage(1),
            )
            self.assertEqual(accepted["session"]["status"], "accepted")

    def test_writer_interruption_before_changes_can_retry_safely(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            _, repairs, lease = self._services(repository)
            session = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Retry a writer that failed before changing files",
                test_command=self._test_command(),
                policy=RepairPolicy(max_iterations=3),
            )
            interrupted = repairs.run_local_until_terminal(
                session["id"],
                writer=lambda context: (_ for _ in ()).throw(
                    RuntimeError("synthetic writer interruption")
                ),
                reviewer=lambda bundle: {
                    "decision": "accept",
                    "feedback": "",
                },
            )
            self.assertEqual(
                interrupted["session"]["status"],
                "recovery_required",
            )
            inspection = repairs.recover(session["id"], action="inspect")
            self.assertTrue(inspection["can_retry"])
            repairs.recover(session["id"], action="retry")

            def writer(context):
                Path(context["worktree_path"], "result.txt").write_text(
                    "good\n",
                    encoding="utf-8",
                )
                return self._usage(1)

            accepted = repairs.run_local_until_terminal(
                session["id"],
                writer=writer,
                reviewer=lambda bundle: {
                    "decision": "accept",
                    "feedback": "Safe retry accepted.",
                    **self._usage(1),
                },
            )
            self.assertEqual(accepted["session"]["status"], "accepted")
            self.assertEqual(accepted["session"]["iteration_count"], 2)

    def test_reviewer_cannot_accept_failing_tests(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            _, repairs, lease = self._services(repository)
            session = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Reject unsupported acceptance",
                test_command=self._test_command(),
                policy=RepairPolicy(max_iterations=2),
            )
            repairs.begin_iteration(session["id"])
            context = repairs.writer_context(session["id"])
            Path(context["worktree_path"], "result.txt").write_text(
                "bad\n",
                encoding="utf-8",
            )
            repairs.capture_iteration(
                session["id"],
                writer_result=self._usage(1),
            )
            with self.assertRaisesRegex(RepairError, "failing tests"):
                repairs.submit_review(
                    session["id"],
                    decision="accept",
                    feedback="Incorrect acceptance.",
                    reviewer_result=self._usage(1),
                )
            self.assertEqual(
                repairs.session(session["id"])["status"],
                "waiting_review",
            )
            repaired = repairs.submit_review(
                session["id"],
                decision="repair",
                feedback="Fix the failing synthetic test.",
                reviewer_result=self._usage(1),
            )
            self.assertEqual(
                repaired["session"]["status"],
                "waiting_writer",
            )

    def test_elapsed_and_feedback_limits_are_deterministic(self):
        with TemporaryDirectory() as temp:
            repository = self._repository(Path(temp))
            _, repairs, lease = self._services(repository)
            elapsed = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Exercise elapsed-time policy",
                test_command=self._test_command(),
                policy=RepairPolicy(max_elapsed_seconds=1),
            )
            with repairs.store.connect() as conn:
                conn.execute(
                    """
                    UPDATE repair_sessions
                    SET created_at = '2000-01-01T00:00:00+00:00'
                    WHERE id = ?
                    """,
                    (elapsed["id"],),
                )
            limited = repairs.begin_iteration(elapsed["id"])
            self.assertEqual(limited["status"], "limit_reached")
            self.assertIn("elapsed time", limited["error"])

            bounded = repairs.start(
                lease_id=lease["id"],
                writer_agent_id="writer",
                reviewer_agent_id="reviewer",
                goal="Exercise feedback policy",
                test_command=self._test_command(),
                policy=RepairPolicy(max_feedback_bytes=8),
            )
            repairs.begin_iteration(bounded["id"])
            context = repairs.writer_context(bounded["id"])
            Path(context["worktree_path"], "result.txt").write_text(
                "good\n",
                encoding="utf-8",
            )
            repairs.capture_iteration(
                bounded["id"],
                writer_result=self._usage(1),
            )
            with self.assertRaisesRegex(RepairError, "feedback exceeds"):
                repairs.submit_review(
                    bounded["id"],
                    decision="repair",
                    feedback="123456789",
                    reviewer_result=self._usage(1),
                )
            self.assertEqual(
                repairs.session(bounded["id"])["status"],
                "waiting_review",
            )

    def test_cli_manual_repair_cycle_uses_persisted_state(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            repository = self._repository(root)
            workspaces, _, lease = self._services(repository)
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
                        "repair",
                        "start",
                        lease["id"],
                        "Complete a synthetic manual repair",
                        "--reviewer",
                        "reviewer",
                        "--test-command-json",
                        json.dumps(self._test_command()),
                        "--config",
                        str(config),
                    ]
                )
            session = json.loads(output.getvalue())
            output = StringIO()
            with redirect_stdout(output):
                main(
                    [
                        "repair",
                        "begin",
                        session["id"],
                        "--config",
                        str(config),
                    ]
                )
            begun = json.loads(output.getvalue())
            Path(
                begun["writer_context"]["worktree_path"],
                "result.txt",
            ).write_text("good\n", encoding="utf-8")
            with redirect_stdout(StringIO()):
                main(
                    [
                        "repair",
                        "capture",
                        session["id"],
                        "--config",
                        str(config),
                    ]
                )
            output = StringIO()
            with redirect_stdout(output):
                main(
                    [
                        "repair",
                        "review",
                        session["id"],
                        "--decision",
                        "accept",
                        "--feedback",
                        "Manual synthetic evidence accepted.",
                        "--config",
                        str(config),
                    ]
                )
            accepted = json.loads(output.getvalue())
            self.assertEqual(accepted["session"]["status"], "accepted")
            self.assertEqual(
                workspaces.workspace(lease["id"])["status"],
                "active",
            )


if __name__ == "__main__":
    unittest.main()
