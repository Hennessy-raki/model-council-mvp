from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from model_council.adapters.mock import MockAdapter
from model_council.manager import Manager
from model_council.types import AgentCard


class ManagerTests(unittest.TestCase):
    def test_mock_manager_creates_valid_plan(self):
        card = AgentCard("manager", "管理员", "plan")
        manager = Manager("manager", MockAdapter(card))
        tasks = manager.plan(
            "run-1",
            "build something",
            [
                {"name": "a", "role": "A"},
                {"name": "b", "role": "B"},
            ],
        )
        self.assertEqual([task.agent for task in tasks], ["a", "b"])
        self.assertEqual(len({task.key for task in tasks}), 2)

    def test_dependency_cycle_is_rejected(self):
        from model_council.types import PlannedTask

        with self.assertRaises(ValueError):
            Manager._validate_acyclic(
                [
                    PlannedTask("a", "a", "a", "x", ("b",)),
                    PlannedTask("b", "b", "b", "x", ("a",)),
                ]
            )


if __name__ == "__main__":
    unittest.main()
