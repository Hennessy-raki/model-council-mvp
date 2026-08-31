from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from model_council.cli import main
from model_council.registry import RegistryService
from model_council.store import CouncilStore
from model_council.supervisor import SupervisorError, SupervisorService


class ScriptedInspector:
    """Local fake CLI/ACP/A2A/MCP/HTTP readiness fixture."""

    def __init__(self, checks_by_role):
        self.checks_by_role = checks_by_role
        self.calls = []

    def inspect(self, binding):
        self.calls.append(
            (binding["role_key"], binding["launch_mode"], binding["transport"])
        )
        return self.checks_by_role[binding["role_key"]]


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CouncilStore(Path(self.temp.name) / "runtime" / "council.db")
        self.registry = RegistryService(self.store)
        self.registry.upsert_provider(
            "local-fake",
            display_name="Local Fake Provider",
            kind="local",
        )
        for role in ("manager", "worker", "reviewer"):
            self.registry.upsert_model(
                f"{role}-model",
                provider_id="local-fake",
                display_name=f"{role.title()} Model",
            )
            self.registry.upsert_agent(
                f"{role}-agent",
                adapter_type="mock",
                provider_id="local-fake",
                model_id=f"{role}-model",
                role=role,
            )

    def _passed_checks(self, model_id):
        return {
            "process": {"status": "passed", "details": {"fixture": "local"}},
            "login": {"status": "passed", "details": {"fixture": "local"}},
            "model": {"status": "passed", "details": {"model_id": model_id}},
            "permission": {
                "status": "passed",
                "details": {"permission": "read_only"},
            },
            "version": {"status": "passed", "details": {"version": "fake-1"}},
            "connection": {
                "status": "passed",
                "details": {"endpoint": "loopback-fixture"},
            },
        }

    def _service(self, overrides=None):
        checks = {
            role: self._passed_checks(f"{role}-model")
            for role in ("manager", "worker", "reviewer")
        }
        for role, values in (overrides or {}).items():
            checks[role].update(values)
        self.inspector = ScriptedInspector(checks)
        service = SupervisorService(
            self.store,
            self.registry,
            inspector=self.inspector,
        )
        service.configure_role(
            role_key="manager",
            agent_id="manager-agent",
            model_id="manager-model",
            launch_mode="spawn",
            transport="cli",
            check_profile={"fixture": "fake-cli"},
        )
        service.configure_role(
            role_key="worker",
            agent_id="worker-agent",
            model_id="worker-model",
            launch_mode="attach_or_spawn",
            transport="acp",
            check_profile={"fixture": "fake-acp"},
        )
        service.configure_role(
            role_key="reviewer",
            agent_id="reviewer-agent",
            model_id="reviewer-model",
            launch_mode="remote",
            transport="a2a",
            check_profile={"fixture": "fake-a2a"},
        )
        return service

    def test_ready_snapshot_notifies_manager_and_exact_approval_authorizes_start(self):
        service = self._service()

        team = service.check_team()
        self.assertEqual(team["status"], "ready")
        self.assertEqual(
            self.inspector.calls,
            [
                ("manager", "spawn", "cli"),
                ("worker", "attach_or_spawn", "acp"),
                ("reviewer", "remote", "a2a"),
            ],
        )
        snapshot = service.snapshot()
        self.assertEqual(len(snapshot["payload"]["roles"]), 3)
        self.assertEqual(service.events()[0]["event_type"], "team_ready")

        approval = service.request_start(snapshot["id"])
        with self.assertRaises(SupervisorError):
            service.decide_start(
                approval["id"],
                approve=True,
                confirmation="incorrect",
            )
        approved = service.decide_start(
            approval["id"],
            approve=True,
            confirmation=approval["scope_sha256"],
        )
        self.assertEqual(approved["status"], "approved")
        started = service.start(approval["id"])
        self.assertEqual(started["approval"]["status"], "consumed")
        self.assertEqual(started["event"]["event_type"], "task_start_authorized")
        self.assertEqual(
            [event["event_type"] for event in service.events()],
            ["team_ready", "task_start_requested", "task_start_authorized"],
        )

    def test_unmachine_verifiable_check_requires_confirmation_before_snapshot(self):
        service = self._service(
            {
                "reviewer": {
                    "connection": {
                        "status": "user_confirmation_required",
                        "code": "gui_only_local_session",
                        "details": {"fixture": "fake-mcp"},
                    }
                }
            }
        )

        team = service.check_team()
        self.assertEqual(team["status"], "user_confirmation_required")
        reviewer = team["agents"][2]
        self.assertEqual(
            reviewer["checks"]["connection"]["status"],
            "user_confirmation_required",
        )
        self.assertIn("Review the local connection evidence", reviewer["errors"][0]["suggestion"])
        with self.assertRaises(SupervisorError):
            service.snapshot()

        confirmations = service.confirm(
            role_key="reviewer",
            check_names=["connection"],
            note="Reviewed only against the local fake MCP fixture.",
        )
        self.assertEqual(confirmations[0]["check_name"], "connection")
        self.assertEqual(service.check_team()["status"], "ready")
        self.assertIsNotNone(service.snapshot()["snapshot_sha256"])

    def test_failed_agent_check_has_local_remediation_and_blocks_snapshot(self):
        service = self._service(
            {
                "worker": {
                    "process": {
                        "status": "failed",
                        "code": "fake_acp_process_missing",
                        "details": {"fixture": "fake-acp"},
                    }
                }
            }
        )

        report = service.check_role("worker")
        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(report["errors"][0]["check"], "process")
        self.assertIn("Start or attach", report["errors"][0]["suggestion"])
        self.assertEqual(service.check_team()["status"], "not_ready")
        with self.assertRaises(SupervisorError):
            service.snapshot()

    def test_configuration_drift_stales_an_approved_start_request(self):
        service = self._service()
        service.check_team()
        snapshot = service.snapshot()
        approval = service.request_start(snapshot["id"])
        service.decide_start(
            approval["id"],
            approve=True,
            confirmation=approval["scope_sha256"],
        )

        service.configure_role(
            role_key="worker",
            agent_id="worker-agent",
            model_id="worker-model",
            launch_mode="spawn",
            transport="mcp",
            check_profile={"fixture": "fake-mcp"},
        )

        stale = service.approval(approval["id"])
        self.assertEqual(stale["status"], "stale")
        self.assertIn("configuration changed", stale["failure"])
        with self.assertRaises(SupervisorError):
            service.start(approval["id"])

    def test_model_mismatch_is_not_ready(self):
        service = self._service(
            {
                "manager": {
                    "model": {
                        "status": "passed",
                        "details": {"model_id": "other-fake-model"},
                    }
                }
            }
        )

        report = service.check_role("manager")
        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(
            report["checks"]["model"]["code"],
            "bound_model_not_observed",
        )

    def test_all_launch_modes_and_first_stage_transports_validate(self):
        service = self._service()
        combinations = (
            ("spawn", "cli"),
            ("attach", "acp"),
            ("attach_or_spawn", "a2a"),
            ("remote", "mcp"),
            ("remote", "http"),
            ("manual", "manual"),
        )
        for launch_mode, transport in combinations:
            binding = service.configure_role(
                role_key="manager",
                agent_id="manager-agent",
                model_id="manager-model",
                launch_mode=launch_mode,
                transport=transport,
                check_profile={"fixture": f"fake-{transport}"},
            )
            self.assertEqual(binding["launch_mode"], launch_mode)
            self.assertEqual(binding["transport"], transport)
        with self.assertRaises(SupervisorError):
            service.configure_role(
                role_key="manager",
                agent_id="manager-agent",
                model_id="manager-model",
                launch_mode="remote",
                transport="manual",
                check_profile={},
            )

    def test_cli_wizard_and_static_local_check_do_not_invoke_any_adapter(self):
        root = Path(self.temp.name) / "cli"
        root.mkdir()
        config_path = root / "config.json"
        team_path = root / "team.json"
        config_path.write_text(
            json.dumps(
                {
                    "state_dir": "runtime",
                    "manager": "manager-agent",
                    "reviewer": "reviewer-agent",
                    "providers": {
                        "local-fake": {
                            "display_name": "Local Fake Provider",
                            "kind": "local",
                        }
                    },
                    "models": {
                        f"{role}-model": {
                            "provider": "local-fake",
                            "display_name": f"{role.title()} Model",
                        }
                        for role in ("manager", "worker", "reviewer")
                    },
                    "agents": {
                        f"{role}-agent": {
                            "type": "mock",
                            "provider": "local-fake",
                            "model": f"{role}-model",
                            "role": role,
                        }
                        for role in ("manager", "worker", "reviewer")
                    },
                }
            ),
            encoding="utf-8",
        )
        team_path.write_text(
            json.dumps(
                {
                    "roles": {
                        role: {
                            "agent_id": f"{role}-agent",
                            "model_id": f"{role}-model",
                            "launch_mode": (
                                "manual" if role == "reviewer" else "spawn"
                            ),
                            "transport": (
                                "manual" if role == "reviewer" else "http"
                            ),
                            "check_profile": {
                                "synthetic_checks": self._passed_checks(
                                    f"{role}-model"
                                )
                            },
                        }
                        for role in ("manager", "worker", "reviewer")
                    }
                }
            ),
            encoding="utf-8",
        )

        output = StringIO()
        with redirect_stdout(output):
            main(
                [
                    "supervisor",
                    "wizard",
                    "--team-file",
                    str(team_path),
                    "--config",
                    str(config_path),
                ]
            )
            main(["supervisor", "check", "--config", str(config_path)])
        self.assertIn('"status": "ready"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
