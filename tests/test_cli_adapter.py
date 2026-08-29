from pathlib import Path
import sys
import unittest

from model_council.adapters.cli import CliAdapter
from model_council.types import AgentCard, AgentRequest


class CliAdapterTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.fixture = self.root / "tests" / "fixtures" / "fake_codex_cli.py"
        self.card = AgentCard(
            name="codex_architect",
            role="Codex architect",
            description="Analyze architecture.",
            capabilities=("architecture",),
            boundaries=("read-only",),
        )

    def test_codex_jsonl_extracts_final_agent_message_and_metadata(self):
        adapter = CliAdapter(
            self.card,
            {
                "command": [sys.executable, str(self.fixture)],
                "output_format": "codex_jsonl",
                "timeout_seconds": 30,
            },
            self.root,
        )
        response = adapter.invoke(
            AgentRequest(
                run_id="run-1",
                task_id="task-1",
                mode="work",
                goal="Review architecture",
                instruction="Return recommendations",
                sender="manager",
                recipient="codex_architect",
            )
        )
        self.assertIn("deterministic boundaries", response.content)
        self.assertEqual(response.metadata["exit_code"], 0)
        self.assertEqual(response.metadata["event_count"], 4)
        self.assertEqual(response.metadata["thread_id"], "thread-test-123")
        self.assertEqual(response.metadata["usage"]["output_tokens"], 35)
        self.assertIn("fixture diagnostic", response.metadata["stderr_tail"])

    def test_codex_jsonl_rejects_missing_agent_message(self):
        with self.assertRaisesRegex(RuntimeError, "no completed agent message"):
            CliAdapter._parse_codex_jsonl(
                '{"type":"thread.started","thread_id":"thread-test"}\n'
            )

    def test_diagnose_resolves_executable_without_running_it(self):
        adapter = CliAdapter(
            self.card,
            {
                "command": [sys.executable, str(self.fixture)],
                "output_format": "codex_jsonl",
            },
            self.root,
        )
        diagnostic = adapter.diagnose()
        self.assertTrue(diagnostic["ok"])
        self.assertTrue(diagnostic["resolved_executable"])


if __name__ == "__main__":
    unittest.main()
