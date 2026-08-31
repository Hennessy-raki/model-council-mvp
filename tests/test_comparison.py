from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from model_council.comparison import RunComparisonService
from model_council.config import load_config
from model_council.ledger import UsageLedger
from model_council.registry import RegistryService
from model_council.routing import RoutingService
from model_council.store import CouncilStore
from model_council.types import RunStatus, TaskStatus


class ComparisonTests(unittest.TestCase):
    def _service(self, root: Path):
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "project_name": "compare-test",
                    "state_dir": "runtime",
                    "manager": "manager",
                    "agents": {
                        "manager": {
                            "type": "mock",
                            "role": "manager",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        config = load_config(config_path)
        store = CouncilStore(config.state_dir / "council.db")
        registry = RegistryService(store)
        registry.sync_from_config(config)
        ledger = UsageLedger(config, store, registry)
        routing = RoutingService(
            config=config,
            store=store,
            registry=registry,
            adapters={},
        )
        return store, RunComparisonService(store, ledger, routing)

    @staticmethod
    def _run(store: CouncilStore, goal: str, tasks: int):
        run_id = store.create_run(goal)
        for index in range(tasks):
            task_id = store.add_task(
                run_id,
                f"task-{index}",
                f"Task {index}",
                "Synthetic",
                "manager",
                [],
            )
            store.set_task_status(task_id, TaskStatus.COMPLETED)
        store.finish_run(run_id, RunStatus.COMPLETED)
        return run_id

    def test_pairwise_comparison_reports_exact_counts_and_unknown_cost(self):
        with TemporaryDirectory() as temp:
            store, comparison = self._service(Path(temp))
            left_id = self._run(store, "left", 1)
            right_id = self._run(store, "right", 3)

            result = comparison.compare(left_id, right_id)

            self.assertEqual(result["left"]["task_count"], 1)
            self.assertEqual(result["right"]["task_count"], 3)
            self.assertEqual(result["delta"]["task_count"], 2)
            self.assertTrue(result["delta"]["costs"]["known"])
            self.assertEqual(result["delta"]["costs"]["values"], {})

    def test_evaluation_status_is_linked_to_its_run(self):
        with TemporaryDirectory() as temp:
            store, comparison = self._service(Path(temp))
            run_id = self._run(store, "evaluation", 0)
            with store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO evaluation_runs(
                        id, run_id, agent_id, agent_family, role, case_id,
                        status, specification_json, created_at,
                        completed_at, error
                    ) VALUES (
                        'eval-1', ?, 'agent', 'family', 'role', 'case',
                        'failed', '{}', '2026-08-31T00:00:00+00:00',
                        '2026-08-31T00:00:01+00:00', 'objective'
                    )
                    """,
                    (run_id,),
                )
            summary = comparison.summarize(run_id)
            self.assertEqual(summary["evaluations"][0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
