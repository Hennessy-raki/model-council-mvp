from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import sys
import unittest

from model_council.adapters import build_adapters
from model_council.adapters.mock import MockAdapter
from model_council.adapters.openai_compatible import OpenAICompatibleAdapter
from model_council.cli import main
from model_council.config import load_config
from model_council.discovery import (
    DiscoveryService,
    LocalAgentTarget,
)
from model_council.orchestrator import Orchestrator
from model_council.registry import RegistryService
from model_council.store import CouncilStore
from model_council.types import AgentCard


class RecordingMockAdapter(MockAdapter):
    def __init__(self, card, settings):
        super().__init__(card, settings)
        self.probe_calls = 0

    def connectivity_probe(self):
        self.probe_calls += 1
        return super().connectivity_probe()


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class DiscoveryTests(unittest.TestCase):
    def _write_config(
        self,
        root: Path,
        *,
        auto_discovery: bool = False,
    ) -> Path:
        fixture = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "fake_discovery_cli.py"
        )
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "state_dir": "runtime",
                    "manager": "manager",
                    "providers": {
                        "provider-a": {
                            "kind": "local",
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
                            "role": "Manager",
                        },
                        "cli-agent": {
                            "type": "cli",
                            "provider": "provider-a",
                            "model": "model-a",
                            "role": "CLI Agent",
                            "command": [
                                sys.executable,
                                str(fixture),
                                "--sandbox",
                                "read-only",
                            ],
                            "auth_check_command": [
                                sys.executable,
                                "-c",
                                "raise SystemExit(0)",
                            ],
                            "model_discovery_command": [
                                sys.executable,
                                "-c",
                                (
                                    "import json; print(json.dumps({'data': "
                                    "[{'id': 'model-x'}, {'id': 'model-x'}, "
                                    "{'id': 'model-y'}]}))"
                                ),
                            ],
                            "output_format": "codex_jsonl",
                        },
                    },
                    "settings": {
                        "auto_discovery_on_start": auto_discovery,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return config_path

    def _service(
        self,
        config_path: Path,
        known_targets: tuple[LocalAgentTarget, ...] = (),
    ) -> tuple[DiscoveryService, RegistryService]:
        config = load_config(config_path)
        store = CouncilStore(config.state_dir / "council.db")
        registry = RegistryService(store)
        registry.sync_from_config(config)
        adapters = build_adapters(config)
        recording = RecordingMockAdapter(
            config.card("manager"),
            config.agents["manager"],
        )
        adapters["manager"] = recording
        service = DiscoveryService(
            config=config,
            registry=registry,
            adapters=adapters,
            known_targets=known_targets,
        )
        return service, registry

    def test_scan_separates_status_and_does_not_probe(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = self._write_config(root)
            known_targets = (
                LocalAgentTarget("python", "Python CLI", (sys.executable,)),
                LocalAgentTarget(
                    "missing",
                    "Missing CLI",
                    ("model-council-command-that-does-not-exist",),
                ),
            )
            service, registry = self._service(config_path, known_targets)
            records = {item["id"]: item for item in service.scan()}

            cli = records["configured:cli-agent"]
            self.assertEqual(cli["executable_status"], "available")
            self.assertEqual(cli["authentication_status"], "verified")
            self.assertEqual(cli["permission_status"], "read_only")
            self.assertEqual(cli["connectivity_status"], "not_checked")
            self.assertTrue(cli["capabilities"]["model_discovery"])
            self.assertEqual(
                records["known:python"]["executable_status"],
                "available",
            )
            self.assertEqual(
                records["known:missing"]["executable_status"],
                "missing",
            )
            self.assertEqual(
                service.adapters["manager"].probe_calls,
                0,
            )
            agents = {
                item["id"]: item for item in registry.snapshot()["agents"]
            }
            self.assertEqual(agents["local-python"]["source"], "discovery")

    def test_model_discovery_uses_adapter_capability(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(Path(temp))
            service, registry = self._service(config_path)
            service.scan()

            models = service.discover_models("cli-agent")

            self.assertEqual(
                [item["id"] for item in models],
                ["model-x", "model-y"],
            )
            record = registry.discovery_record("configured:cli-agent")
            self.assertEqual(record["models"], models)

    def test_connectivity_probe_is_explicit_and_project_neutral(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(Path(temp))
            service, registry = self._service(config_path)
            service.scan()
            self.assertEqual(
                registry.discovery_record("configured:cli-agent")[
                    "connectivity_status"
                ],
                "not_checked",
            )

            result = service.probe("cli-agent")

            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["details"]["isolated_workspace"])
            self.assertEqual(
                registry.discovery_record("configured:cli-agent")[
                    "connectivity_status"
                ],
                "passed",
            )

    def test_manual_gui_registration_is_user_owned(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(Path(temp))
            service, registry = self._service(config_path)

            record = service.register_gui(
                agent_id="desktop-agent",
                display_name="Desktop Agent",
                provider_id="provider-a",
                model_id="model-a",
                capabilities=["review"],
                boundaries=["manual handoff"],
            )
            registry.sync_from_config(load_config(config_path))
            snapshot = registry.snapshot()
            agent = next(
                item
                for item in snapshot["agents"]
                if item["id"] == "desktop-agent"
            )

            self.assertEqual(record["target_kind"], "manual_gui")
            self.assertEqual(agent["adapter_type"], "gui")
            self.assertEqual(agent["source"], "user")
            self.assertEqual(agent["model_id"], "model-a")

    def test_discovery_cli_scan_outputs_persisted_records(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(Path(temp))
            output = StringIO()
            with redirect_stdout(output):
                main(
                    [
                        "discovery",
                        "scan",
                        "--config",
                        str(config_path),
                    ]
                )
            payload = json.loads(output.getvalue())
            configured = {
                item["agent_id"]: item
                for item in payload
                if item["target_kind"] == "configured_agent"
            }
            self.assertIn("manager", configured)
            self.assertIn("cli-agent", configured)

    def test_auto_discovery_setting_runs_local_scan_on_startup(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(
                Path(temp),
                auto_discovery=True,
            )
            orchestrator = Orchestrator(load_config(config_path))
            records = orchestrator.registry.discovery_records()
            self.assertTrue(
                any(item["id"] == "configured:manager" for item in records)
            )
            self.assertTrue(
                all(
                    item["connectivity_status"] == "not_checked"
                    for item in records
                )
            )

    def test_openai_compatible_model_discovery_uses_models_endpoint(self):
        adapter = OpenAICompatibleAdapter(
            AgentCard(
                name="api-agent",
                role="API Agent",
                description="Test",
            ),
            {
                "base_url": "https://provider.example/v1",
                "model": "configured-model",
                "api_key_env": "DISCOVERY_TEST_API_KEY",
            },
        )
        response = FakeHttpResponse(
            {
                "data": [
                    {"id": "model-a"},
                    {"id": "model-a"},
                    {"id": "model-b"},
                ]
            }
        )
        with patch.dict(
            os.environ,
            {"DISCOVERY_TEST_API_KEY": "test-only-value"},
        ):
            with patch(
                "model_council.adapters.openai_compatible.urlopen",
                return_value=response,
            ) as mocked:
                models = adapter.discover_models()

        self.assertEqual(
            [item["id"] for item in models],
            ["model-a", "model-b"],
        )
        request = mocked.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://provider.example/v1/models",
        )


if __name__ == "__main__":
    unittest.main()
