from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

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
                        "agents": {
                            "manager": {
                                "type": "mock",
                                "role": "manager",
                            },
                            "worker_a": {
                                "type": "mock",
                                "role": "worker a",
                            },
                            "worker_b": {
                                "type": "mock",
                                "role": "worker b",
                            },
                            "reviewer": {
                                "type": "mock",
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
            self.assertEqual(run["status"], "completed")
            self.assertEqual(len(tasks), 3)
            self.assertTrue(Path(result.final_artifact.path).exists())
            self.assertIn("Model Council", result.final_text)


if __name__ == "__main__":
    unittest.main()
