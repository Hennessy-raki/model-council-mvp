from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from model_council.cli import main
from model_council.config import load_config
from model_council.experiments import ExperimentError, ExperimentService
from model_council.registry import RegistryService
from model_council.store import CouncilStore
from model_council.supervisor import SupervisorService


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = CouncilStore(self.root / "runtime" / "council.db")
        self.registry = RegistryService(self.store)
        self.registry.upsert_provider(
            "local-fixture",
            display_name="Local Fixture",
            kind="local",
        )
        for model_id in ("fake-model", "codex-model"):
            self.registry.upsert_model(
                model_id,
                provider_id="local-fixture",
                display_name=model_id,
            )
        self.registry.upsert_agent(
            "fake-manager",
            adapter_type="mock",
            provider_id="local-fixture",
            model_id="fake-model",
            role="manager",
        )
        self.registry.upsert_agent(
            "codex-manager",
            adapter_type="cli",
            provider_id="local-fixture",
            model_id="codex-model",
            role="manager",
            config={
                "command": [
                    "codex",
                    "exec",
                    "--disable",
                    "plugins",
                    "--disable",
                    "remote_plugin",
                    "--disable",
                    "apps",
                    "--json",
                    "-",
                ],
                "sandbox": "read-only",
                "strict_no_approvals": True,
            },
        )
        for agent_id, role in (
            ("fake-worker-a", "worker-a"),
            ("fake-worker-b", "worker-b"),
            ("fake-reviewer", "reviewer"),
        ):
            self.registry.upsert_agent(
                agent_id,
                adapter_type="mock",
                provider_id="local-fixture",
                model_id="fake-model",
                role=role,
            )
        self.supervisor = SupervisorService(self.store, self.registry)
        self.experiments = ExperimentService(
            self.store,
            self.registry,
            self.supervisor,
        )

    def _fixture_real_spec(self, fixture_name, *, max_total_tokens=2000):
        fixture = (
            Path(__file__).resolve().parent / "fixtures" / fixture_name
        )
        command = [
            sys.executable,
            str(fixture),
            "--disable",
            "plugins",
            "--disable",
            "remote_plugin",
            "--disable",
            "apps",
        ]
        synthetic_cwd = r"C:\model-council-synthetic"
        self.registry.upsert_agent(
            "codex-manager",
            adapter_type="codex_app_server",
            provider_id="local-fixture",
            model_id="codex-model",
            role="manager",
            config={
                "command": command,
                "cwd": synthetic_cwd,
                "sandbox": "read-only",
                "approval_policy": "never",
                "strict_no_approvals": True,
                "invoke_enabled": False,
            },
        )
        snapshot = self._snapshot(
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        spec = self._spec(
            phase="14.1",
            snapshot=snapshot,
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        spec["transport"]["host_type"] = "codex_app_server"
        spec["transport"]["command"] = command
        spec["transport"]["working_directory"] = synthetic_cwd
        spec["limits"]["max_total_tokens"] = max_total_tokens
        return spec

    def _approved_start(self, spec):
        experiment = self.experiments.prepare(spec)
        self.experiments.decide(
            experiment["id"],
            approve=True,
            confirmation=experiment["scope_sha256"],
        )
        self.experiments.arm(experiment["id"])
        start = self.experiments.request_start(experiment["id"])
        self.experiments.decide_start(
            start["id"],
            approve=True,
            confirmation=start["scope_sha256"],
        )
        return experiment, start

    def _checks(self, model_id):
        return {
            "synthetic_checks": {
                "process": {"status": "passed", "details": {"fixture": "local"}},
                "login": {"status": "passed", "details": {"fixture": "local"}},
                "model": {
                    "status": "passed",
                    "details": {"model_id": model_id},
                },
                "permission": {
                    "status": "passed",
                    "details": {"level": "read_only"},
                },
                "version": {
                    "status": "passed",
                    "details": {"version": "fixture-1"},
                },
                "connection": {
                    "status": "passed",
                    "details": {"fixture": "loopback"},
                },
            }
        }

    def _snapshot(self, *, manager_agent, manager_model):
        for role_key, agent_id, model_id, launch_mode, transport in (
            (
                "manager",
                manager_agent,
                manager_model,
                "spawn",
                "cli" if manager_agent == "codex-manager" else "manual",
            ),
            (
                "worker",
                "fake-worker-a",
                "fake-model",
                "attach",
                "acp",
            ),
            (
                "reviewer",
                "fake-reviewer",
                "fake-model",
                "manual",
                "manual",
            ),
        ):
            if launch_mode == "manual":
                transport = "manual"
            self.supervisor.configure_role(
                role_key=role_key,
                agent_id=agent_id,
                model_id=model_id,
                launch_mode=launch_mode,
                transport=transport,
                check_profile=self._checks(model_id),
            )
        self.assertEqual(self.supervisor.check_team()["status"], "ready")
        return self.supervisor.snapshot()

    def _spec(self, *, phase, snapshot, manager_agent, manager_model):
        real = phase == "14.1"
        return {
            "phase": phase,
            "execution_mode": "real_codex" if real else "synthetic_fake",
            "source": "synthetic",
            "team_snapshot_id": snapshot["id"],
            "manager_agent_id": manager_agent,
            "manager_model_id": manager_model,
            "prompt": (
                "Create exactly two independent synthetic tasks for local fake "
                "workers. Return only the required JSON plan."
            ),
            "workers": [
                {
                    "agent_id": "fake-worker-a",
                    "model_id": "fake-model",
                    "role_key": "synthetic_analysis",
                },
                {
                    "agent_id": "fake-worker-b",
                    "model_id": "fake-model",
                    "role_key": "synthetic_risk_review",
                },
            ],
            "transport": {
                "host_type": "cli" if real else "synthetic_fake",
                "command": (
                    [
                        "codex",
                        "exec",
                        "--disable",
                        "plugins",
                        "--disable",
                        "remote_plugin",
                        "--disable",
                        "apps",
                        "--json",
                        "-",
                    ]
                    if real
                    else ["synthetic-fake-manager"]
                ),
                "working_directory": r"C:\model-council-synthetic",
                "model_id": manager_model,
                "sandbox": "read-only",
                "approval_policy": "never" if real else "reject",
                "features_disabled": (
                    ["plugins", "remote_plugin", "apps"] if real else []
                ),
            },
            "permissions": {
                "sandbox": "read-only",
                "tools_enabled": False,
                "workspace_write": False,
                "git_enabled": False,
                "files": 0,
                "artifacts": 0,
            },
            "limits": {
                "max_prompt_bytes": 4096,
                "max_transport_bytes": 4096,
                "max_total_bytes": 8192,
                "max_response_bytes": 16384,
                "max_calls": 1,
                "max_retries": 0,
                "parallelism": 1,
                "timeout_seconds": 120,
                "max_total_tokens": 2000,
                "max_total_cost": "0.25",
                "cost_currency": "USD",
            },
            "expected_output": {"schema": "manager_two_worker_plan_v1"},
        }

    def test_prepare_real_codex_candidate_stops_at_pending_exact_scope(self):
        snapshot = self._snapshot(
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        experiment = self.experiments.prepare(
            self._spec(
                phase="14.1",
                snapshot=snapshot,
                manager_agent="codex-manager",
                manager_model="codex-model",
            )
        )

        self.assertEqual(experiment["status"], "pending")
        self.assertEqual(experiment["execution_mode"], "real_codex")
        self.assertNotIn("prompt", experiment)
        shown = self.experiments.experiment(
            experiment["id"],
            include_prompt=True,
        )
        self.assertIn("exactly two", shown["prompt"])
        self.assertEqual(shown["scope"]["permissions"]["files"], 0)
        self.assertEqual(shown["scope"]["limits"]["max_calls"], 1)
        self.assertFalse(shown["scope"]["permissions"]["tools_enabled"])
        self.assertEqual(
            self.experiments.events(experiment["id"])[0]["payload"][
                "external_invocation"
            ],
            False,
        )

    def test_real_codex_candidate_can_arm_but_cannot_use_fake_runner(self):
        snapshot = self._snapshot(
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        experiment = self.experiments.prepare(
            self._spec(
                phase="14.1",
                snapshot=snapshot,
                manager_agent="codex-manager",
                manager_model="codex-model",
            )
        )
        with self.assertRaises(ExperimentError):
            self.experiments.decide(
                experiment["id"],
                approve=True,
                confirmation="wrong",
            )
        self.experiments.decide(
            experiment["id"],
            approve=True,
            confirmation=experiment["scope_sha256"],
        )
        armed = self.experiments.arm(experiment["id"])
        self.assertEqual(armed["status"], "armed")
        with self.assertRaises(ExperimentError):
            self.experiments.simulate(experiment["id"])
        self.assertEqual(self.experiments.evidence(experiment["id"]), [])

    def test_real_codex_start_approval_requires_exact_second_digest(self):
        snapshot = self._snapshot(
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        experiment = self.experiments.prepare(
            self._spec(
                phase="14.1",
                snapshot=snapshot,
                manager_agent="codex-manager",
                manager_model="codex-model",
            )
        )
        self.experiments.decide(
            experiment["id"],
            approve=True,
            confirmation=experiment["scope_sha256"],
        )
        self.experiments.arm(experiment["id"])
        start = self.experiments.request_start(experiment["id"])
        self.assertEqual(start["status"], "pending")
        self.assertEqual(
            start["scope"]["action"],
            "start_codex_app_server_and_one_turn",
        )
        with self.assertRaises(ExperimentError):
            self.experiments.decide_start(
                start["id"],
                approve=True,
                confirmation="wrong",
            )
        approved = self.experiments.decide_start(
            start["id"],
            approve=True,
            confirmation=start["scope_sha256"],
        )
        self.assertEqual(approved["status"], "approved")
        consumed = self.experiments.consume_start(start["id"])
        self.assertEqual(consumed["status"], "consumed")
        with self.assertRaises(ExperimentError):
            self.experiments.consume_start(start["id"])
        self.assertEqual(
            self.experiments.experiment(experiment["id"])["status"],
            "armed",
        )
        self.assertEqual(self.experiments.evidence(experiment["id"]), [])

    def test_start_approval_requires_armed_experiment_and_fresh_snapshot(self):
        snapshot = self._snapshot(
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        experiment = self.experiments.prepare(
            self._spec(
                phase="14.1",
                snapshot=snapshot,
                manager_agent="codex-manager",
                manager_model="codex-model",
            )
        )
        with self.assertRaises(ExperimentError):
            self.experiments.request_start(experiment["id"])
        self.experiments.decide(
            experiment["id"],
            approve=True,
            confirmation=experiment["scope_sha256"],
        )
        self.experiments.arm(experiment["id"])
        self.supervisor.check_team()
        with self.assertRaises(ExperimentError):
            self.experiments.request_start(experiment["id"])
        self.assertEqual(
            self.experiments.experiment(experiment["id"])["status"],
            "stale",
        )

    def test_consumed_start_runs_only_exact_local_fixture_and_hashes_response(self):
        experiment, start = self._approved_start(
            self._fixture_real_spec("fake_codex_app_server_plan.py")
        )
        completed = self.experiments.execute_start(start["id"])
        self.assertEqual(completed["experiment"]["status"], "completed")
        self.assertEqual(
            self.experiments.start_approval(start["id"])["status"],
            "consumed",
        )
        evidence = completed["evidence"][0]["evidence"]
        self.assertEqual(evidence["process_invocation_count"], 1)
        self.assertEqual(evidence["retry_count"], 0)
        self.assertEqual(evidence["usage"]["total_tokens"], 15)
        self.assertNotIn("tasks", evidence)
        self.assertNotIn("response", evidence)
        self.assertNotIn(
            "Create exactly two",
            json.dumps(completed, sort_keys=True),
        )
        with self.assertRaises(ExperimentError):
            self.experiments.execute_start(start["id"])
        self.assertEqual(
            self.experiments.experiment(experiment["id"])["status"],
            "completed",
        )

    def test_fixture_approval_request_stops_consumed_start(self):
        experiment, start = self._approved_start(
            self._fixture_real_spec("fake_codex_app_server.py")
        )
        with self.assertRaisesRegex(ExperimentError, "interactive approval"):
            self.experiments.execute_start(start["id"])
        self.assertEqual(
            self.experiments.experiment(experiment["id"])["status"],
            "failed",
        )
        self.assertEqual(self.experiments.evidence(experiment["id"]), [])

    def test_fixture_usage_over_limit_fails_without_response_evidence(self):
        experiment, start = self._approved_start(
            self._fixture_real_spec(
                "fake_codex_app_server_plan.py",
                max_total_tokens=14,
            )
        )
        with self.assertRaisesRegex(ExperimentError, "max_total_tokens"):
            self.experiments.execute_start(start["id"])
        self.assertEqual(
            self.experiments.experiment(experiment["id"])["status"],
            "failed",
        )
        self.assertEqual(self.experiments.evidence(experiment["id"]), [])

    def test_board_14_0_simulation_completes_with_zero_external_calls(self):
        snapshot = self._snapshot(
            manager_agent="fake-manager",
            manager_model="fake-model",
        )
        experiment = self.experiments.prepare(
            self._spec(
                phase="14.0",
                snapshot=snapshot,
                manager_agent="fake-manager",
                manager_model="fake-model",
            )
        )
        self.experiments.decide(
            experiment["id"],
            approve=True,
            confirmation=experiment["scope_sha256"],
        )
        self.experiments.arm(experiment["id"])
        completed = self.experiments.simulate(experiment["id"])

        self.assertEqual(completed["experiment"]["status"], "completed")
        evidence = completed["evidence"][0]["evidence"]
        self.assertEqual(evidence["external_call_count"], 0)
        self.assertEqual(evidence["adapter_invocation_count"], 0)
        self.assertEqual(len(evidence["worker_results"]), 2)
        self.assertTrue(all(evidence["assertions"].values()))
        with self.assertRaises(ExperimentError):
            self.experiments.simulate(experiment["id"])

    def test_private_context_and_permission_expansion_are_rejected(self):
        snapshot = self._snapshot(
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        base = self._spec(
            phase="14.1",
            snapshot=snapshot,
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        cases = []
        personal = json.loads(json.dumps(base))
        personal["transport"]["working_directory"] = "\\".join(
            ("C:", "Users", "private-user", "synthetic")
        )
        cases.append(personal)
        secret = json.loads(json.dumps(base))
        secret["prompt"] = "api_key=do-not-store"
        cases.append(secret)
        write = json.loads(json.dumps(base))
        write["permissions"]["workspace_write"] = True
        cases.append(write)
        retry = json.loads(json.dumps(base))
        retry["limits"]["max_retries"] = 1
        cases.append(retry)

        for spec in cases:
            with self.subTest(spec=spec):
                with self.assertRaises(ExperimentError):
                    self.experiments.prepare(spec)

    def test_requires_two_distinct_local_mock_workers(self):
        snapshot = self._snapshot(
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        spec = self._spec(
            phase="14.1",
            snapshot=snapshot,
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        spec["workers"][1]["agent_id"] = "fake-worker-a"
        with self.assertRaises(ExperimentError):
            self.experiments.prepare(spec)

        spec = self._spec(
            phase="14.1",
            snapshot=snapshot,
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        spec["workers"][1] = {
            "agent_id": "codex-manager",
            "model_id": "codex-model",
            "role_key": "not-fake",
        }
        with self.assertRaises(ExperimentError):
            self.experiments.prepare(spec)

    def test_agent_identity_drift_marks_approved_experiment_stale(self):
        snapshot = self._snapshot(
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        experiment = self.experiments.prepare(
            self._spec(
                phase="14.1",
                snapshot=snapshot,
                manager_agent="codex-manager",
                manager_model="codex-model",
            )
        )
        self.experiments.decide(
            experiment["id"],
            approve=True,
            confirmation=experiment["scope_sha256"],
        )
        self.registry.upsert_agent(
            "codex-manager",
            adapter_type="cli",
            provider_id="local-fixture",
            model_id="codex-model",
            role="manager",
            description="Changed after exact approval",
            config={
                "command": [
                    "codex",
                    "exec",
                    "--disable",
                    "plugins",
                    "--disable",
                    "remote_plugin",
                    "--disable",
                    "apps",
                    "--json",
                    "-",
                ],
                "sandbox": "read-only",
            },
        )

        with self.assertRaises(ExperimentError):
            self.experiments.arm(experiment["id"])
        stale = self.experiments.experiment(experiment["id"])
        self.assertEqual(stale["status"], "stale")
        self.assertIn("identity changed", stale["failure"])

    def test_fresh_readiness_evidence_stales_the_bound_team_snapshot(self):
        snapshot = self._snapshot(
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        experiment = self.experiments.prepare(
            self._spec(
                phase="14.1",
                snapshot=snapshot,
                manager_agent="codex-manager",
                manager_model="codex-model",
            )
        )
        self.experiments.decide(
            experiment["id"],
            approve=True,
            confirmation=experiment["scope_sha256"],
        )
        self.supervisor.check_team()

        with self.assertRaises(ExperimentError):
            self.experiments.arm(experiment["id"])
        self.assertEqual(
            self.experiments.experiment(experiment["id"])["status"],
            "stale",
        )

    def test_cli_prepare_and_show_remain_local_and_pending(self):
        root = self.root / "cli"
        root.mkdir()
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "state_dir": "runtime",
                    "manager": "fake-manager",
                    "reviewer": "fake-reviewer",
                    "providers": {
                        "local-fixture": {
                            "display_name": "Local Fixture",
                            "kind": "local",
                        }
                    },
                    "models": {
                        "fake-model": {
                            "provider": "local-fixture",
                            "display_name": "Fake Model",
                        }
                    },
                    "agents": {
                        "fake-manager": {
                            "type": "mock",
                            "provider": "local-fixture",
                            "model": "fake-model",
                            "role": "manager",
                        },
                        "fake-worker-a": {
                            "type": "mock",
                            "provider": "local-fixture",
                            "model": "fake-model",
                            "role": "worker-a",
                        },
                        "fake-worker-b": {
                            "type": "mock",
                            "provider": "local-fixture",
                            "model": "fake-model",
                            "role": "worker-b",
                        },
                        "fake-reviewer": {
                            "type": "mock",
                            "provider": "local-fixture",
                            "model": "fake-model",
                            "role": "reviewer",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        config = load_config(config_path)
        registry = RegistryService(CouncilStore(config.state_dir / "council.db"))
        registry.sync_from_config(config)
        supervisor = SupervisorService(registry.store, registry)
        for role_key, agent_id in (
            ("manager", "fake-manager"),
            ("worker", "fake-worker-a"),
            ("reviewer", "fake-reviewer"),
        ):
            supervisor.configure_role(
                role_key=role_key,
                agent_id=agent_id,
                model_id="fake-model",
                launch_mode="manual",
                transport="manual",
                check_profile=self._checks("fake-model"),
            )
        supervisor.check_team()
        snapshot = supervisor.snapshot()
        spec = self._spec(
            phase="14.0",
            snapshot=snapshot,
            manager_agent="fake-manager",
            manager_model="fake-model",
        )
        spec_path = root / "spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        output = StringIO()
        with redirect_stdout(output):
            main(
                [
                    "experiment",
                    "prepare",
                    "--spec-file",
                    str(spec_path),
                    "--config",
                    str(config_path),
                ]
            )
            main(["experiment", "list", "--config", str(config_path)])
        text = output.getvalue()
        self.assertIn('"status": "pending"', text)
        self.assertNotIn("Create exactly two", text)

    def test_public_board14_candidate_is_disabled_and_synthetic_only(self):
        repository = Path(__file__).resolve().parent.parent
        config = load_config(repository / "config.board14.example.json")
        manager = config.agents["codex_manager"]
        self.assertFalse(manager["invoke_enabled"])
        self.assertTrue(manager["strict_no_approvals"])
        self.assertEqual(manager["sandbox"], "read-only")
        self.assertEqual(manager["outbound_context"]["source"], "synthetic")
        self.assertEqual(manager["outbound_context"]["max_files"], 0)
        self.assertEqual(manager["outbound_context"]["max_artifacts"], 0)
        self.assertIn("plugins", manager["command"])
        self.assertIn("remote_plugin", manager["command"])
        self.assertIn("apps", manager["command"])

    def test_real_candidate_rejects_an_enabled_manager(self):
        command = [
            "codex",
            "exec",
            "--disable",
            "plugins",
            "--disable",
            "remote_plugin",
            "--disable",
            "apps",
            "--json",
            "-",
        ]
        self.registry.upsert_agent(
            "codex-manager",
            adapter_type="cli",
            provider_id="local-fixture",
            model_id="codex-model",
            role="manager",
            config={
                "command": command,
                "sandbox": "read-only",
                "invoke_enabled": True,
            },
        )
        snapshot = self._snapshot(
            manager_agent="codex-manager",
            manager_model="codex-model",
        )
        with self.assertRaises(ExperimentError):
            self.experiments.prepare(
                self._spec(
                    phase="14.1",
                    snapshot=snapshot,
                    manager_agent="codex-manager",
                    manager_model="codex-model",
                )
            )


if __name__ == "__main__":
    unittest.main()
