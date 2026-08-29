from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from model_council.config import load_config
from model_council.registry import RegistryService
from model_council.store import CouncilStore


class RegistryTests(unittest.TestCase):
    def _write_config(self, root: Path) -> Path:
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "state_dir": "runtime",
                    "manager": "manager",
                    "reviewer": "reviewer",
                    "providers": {
                        "provider-a": {
                            "kind": "api",
                            "display_name": "Provider A",
                            "api_key": "must-not-be-persisted",
                            "api_key_env": "PROVIDER_A_API_KEY",
                        }
                    },
                    "models": {
                        "model-a": {
                            "provider": "provider-a",
                            "display_name": "Model A",
                            "capabilities": ["planning", "coding"],
                        }
                    },
                    "agents": {
                        "manager": {
                            "type": "mock",
                            "provider": "provider-a",
                            "model": "model-a",
                            "role": "Manager",
                        },
                        "worker": {
                            "type": "mock",
                            "provider": "provider-a",
                            "model": "model-a",
                            "role": "Worker",
                        },
                        "reviewer": {
                            "type": "mock",
                            "provider": "provider-a",
                            "model": "model-a",
                            "role": "Reviewer",
                        },
                    },
                    "role_assignments": {
                        "detail_executor": {
                            "mode": "manual",
                            "agent": "worker",
                            "model": "model-a",
                        }
                    },
                    "settings": {
                        "locale": "zh-CN",
                        "nested": {"access_token": "must-not-be-persisted"},
                        "artifact_provenance_display": "compact",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return config_path

    def test_sync_builds_registry_and_redacts_sensitive_values(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = load_config(self._write_config(root))
            store = CouncilStore(config.state_dir / "council.db")
            registry = RegistryService(store)
            counts = registry.sync_from_config(config)
            snapshot = registry.snapshot()

            self.assertEqual(counts["providers"], 1)
            self.assertEqual(counts["models"], 1)
            self.assertEqual(counts["agents"], 3)
            self.assertEqual(counts["roles"], 3)
            self.assertEqual(
                snapshot["providers"][0]["config"]["api_key"],
                "[REDACTED]",
            )
            self.assertEqual(
                snapshot["providers"][0]["config"]["api_key_env"],
                "PROVIDER_A_API_KEY",
            )
            self.assertEqual(
                snapshot["settings"]["nested"]["value"]["access_token"],
                "[REDACTED]",
            )
            self.assertEqual(
                {item["role_key"] for item in snapshot["roles"]},
                {
                    "decision_manager",
                    "detail_executor",
                    "independent_reviewer",
                },
            )

    def test_user_overrides_survive_config_resynchronization(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = load_config(self._write_config(root))
            registry = RegistryService(
                CouncilStore(config.state_dir / "council.db")
            )
            registry.sync_from_config(config)
            registry.assign_role(
                "detail_executor",
                mode="hybrid",
                agent_id="worker",
                model_id="model-a",
                locked=True,
                constraints={"max_cost": 2.5},
            )
            registry.set_setting("locale", "en-US")

            registry.sync_from_config(config)
            snapshot = registry.snapshot()
            role = next(
                item
                for item in snapshot["roles"]
                if item["role_key"] == "detail_executor"
            )
            self.assertEqual(role["mode"], "hybrid")
            self.assertTrue(role["locked"])
            self.assertEqual(role["constraints"]["max_cost"], 2.5)
            self.assertEqual(role["source"], "user")
            self.assertEqual(snapshot["settings"]["locale"]["value"], "en-US")
            self.assertEqual(snapshot["settings"]["locale"]["source"], "user")

    def test_manual_assignment_requires_known_agent(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = load_config(self._write_config(root))
            registry = RegistryService(
                CouncilStore(config.state_dir / "council.db")
            )
            registry.sync_from_config(config)
            with self.assertRaisesRegex(ValueError, "unknown agent"):
                registry.assign_role(
                    "detail_executor",
                    mode="manual",
                    agent_id="missing-agent",
                )

    def test_user_provenance_display_override_survives_seed_sync(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = load_config(self._write_config(root))
            registry = RegistryService(
                CouncilStore(config.state_dir / "council.db")
            )
            registry.sync_from_config(config)
            self.assertEqual(registry.provenance_display_mode(), "compact")
            registry.set_setting("artifact_provenance_display", "hidden")
            registry.sync_from_config(config)
            self.assertEqual(registry.provenance_display_mode(), "hidden")
            snapshot = registry.snapshot()
            self.assertEqual(
                snapshot["settings"]["artifact_provenance_display"]["source"],
                "user",
            )

    def test_provenance_display_rejects_unknown_mode(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = load_config(self._write_config(root))
            registry = RegistryService(
                CouncilStore(config.state_dir / "council.db")
            )
            registry.sync_from_config(config)
            with self.assertRaisesRegex(ValueError, "artifact_provenance_display"):
                registry.set_setting("artifact_provenance_display", "expanded")


if __name__ == "__main__":
    unittest.main()
