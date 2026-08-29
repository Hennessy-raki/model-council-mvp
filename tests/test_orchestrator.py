from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout
from io import StringIO
import json
import unittest

from model_council.cli import main
from model_council.config import load_config
from model_council.orchestrator import Orchestrator


class OrchestratorTests(unittest.TestCase):
    def test_full_mock_workflow(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "state_dir": "runtime",
                        "manager": "manager",
                        "reviewer": "reviewer",
                        "providers": {
                            "provider-a": {
                                "kind": "mock",
                                "display_name": "Provider A",
                            }
                        },
                        "models": {
                            "model-a": {
                                "provider": "provider-a",
                                "display_name": "Model A",
                            }
                        },
                        "agents": {
                            "manager": {
                                "type": "mock",
                                "provider": "provider-a",
                                "model": "model-a",
                                "role": "manager",
                            },
                            "worker_a": {
                                "type": "mock",
                                "provider": "provider-a",
                                "model": "model-a",
                                "role": "worker a",
                            },
                            "worker_b": {
                                "type": "mock",
                                "provider": "provider-a",
                                "model": "model-a",
                                "role": "worker b",
                            },
                            "reviewer": {
                                "type": "mock",
                                "provider": "provider-a",
                                "model": "model-a",
                                "role": "reviewer",
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            orchestrator = Orchestrator(load_config(config_path))
            result = orchestrator.run("test goal")
            run = orchestrator.store.get_run(result.run_id)
            tasks = orchestrator.store.tasks_for_run(result.run_id)
            messages = orchestrator.store.messages_for_run(result.run_id)
            self.assertEqual(run["status"], "completed")
            self.assertEqual(len(tasks), 3)
            self.assertEqual(len(messages), 8)
            self.assertIn(
                "task_result",
                {message["type"] for message in messages},
            )
            self.assertTrue(
                all(isinstance(message["body"], dict) for message in messages)
            )
            self.assertTrue(Path(result.final_artifact.path).exists())
            self.assertIn("Model Council", result.final_text)
            detailed = orchestrator.store.artifacts_for_run(
                result.run_id,
                display_mode="detailed",
            )
            final = next(item for item in detailed if item["id"] == result.final_artifact.id)
            review = next(
                item for item in detailed if item["name"] == "independent-review.md"
            )
            self.assertEqual(final["provenance"]["producer"]["agent_id"], "manager")
            self.assertEqual(
                final["provenance"]["producer"]["provider_id"],
                "provider-a",
            )
            self.assertEqual(final["provenance"]["producer"]["model_id"], "model-a")
            self.assertEqual(
                final["provenance"]["final_integrators"][0]["agent_id"],
                "manager",
            )
            self.assertEqual(
                final["provenance"]["reviewers"][0]["agent_id"],
                "reviewer",
            )
            self.assertEqual(review["provenance"]["producer"]["agent_id"], "reviewer")
            self.assertEqual(review["provenance"]["reviewers"][0]["agent_id"], "reviewer")
            self.assertGreaterEqual(len(final["provenance"]["contributors"]), 3)
            routing = orchestrator.router.decisions(result.run_id)
            self.assertEqual(
                {item["role_key"] for item in routing},
                {
                    "decision_manager",
                    "agent:worker_a",
                    "agent:worker_b",
                    "independent_reviewer",
                },
            )
            self.assertTrue(
                all(item["status"] == "resolved" for item in routing)
            )

            compact = orchestrator.store.artifacts_for_run(
                result.run_id,
                display_mode="compact",
            )
            self.assertIn("contributor_count", compact[-1]["provenance"])
            hidden = orchestrator.store.artifacts_for_run(
                result.run_id,
                display_mode="hidden",
            )
            self.assertTrue(all("provenance" not in item for item in hidden))
            self.assertEqual(
                orchestrator.store.provenance_for_artifact(result.final_artifact.id)[
                    "producer"
                ]["agent_id"],
                "manager",
            )

            orchestrator.registry.set_setting(
                "artifact_provenance_display",
                "hidden",
            )
            output = StringIO()
            with redirect_stdout(output):
                main(
                    [
                        "status",
                        result.run_id,
                        "--config",
                        str(config_path),
                    ]
                )
            status_payload = json.loads(output.getvalue())
            self.assertTrue(
                all(
                    "provenance" not in item
                    for item in status_payload["artifacts"]
                )
            )
            self.assertEqual(
                len(status_payload["routing"]),
                len(routing),
            )


if __name__ == "__main__":
    unittest.main()
