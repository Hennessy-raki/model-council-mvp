from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from model_council.cli import main
from model_council.qualification import QualificationPreflightService
from model_council.registry import RegistryService
from model_council.store import CouncilStore
from model_council.supervisor import (
    SubprocessAgentLifecycleFixture,
    SupervisorError,
    SupervisorService,
)


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

    def _qualification(self, agent_id="manager-agent", model_id="manager-model"):
        return QualificationPreflightService().evaluate(
            {
                "agent_id": agent_id,
                "model_id": model_id,
                "provider_id": "local-fake",
                "launch_mode": "spawn",
                "transport": "cli",
                "lifecycle_checks": [
                    "process",
                    "login",
                    "actual_model",
                    "permission",
                    "version",
                    "protocol",
                    "connectivity",
                ],
                "permissions": ["read_only"],
                "context": {
                    "repository_context": False,
                    "private_project_content": False,
                    "worktree": False,
                    "workspace_write": False,
                    "prompt_instance": False,
                    "artifact_body": False,
                },
                "limits": {
                    "max_input_tokens": 100,
                    "max_output_tokens": 100,
                    "max_total_tokens": 200,
                    "max_total_cost": "0.01",
                    "currency": "USD",
                    "max_duration_seconds": 60,
                    "max_attempts": 1,
                    "retry_on_failure": False,
                },
                "approval_ladder": [
                    "preflight_review",
                    "external_scope_approval",
                    "execution_approval",
                ],
                "evidence": {
                    "storage": "runtime_only",
                    "retain_raw_output": False,
                    "retain_stdout": False,
                    "retain_stderr": False,
                    "retain_prompt": False,
                    "retain_response": False,
                },
                "execution_authorized": False,
            }
        )

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

    def test_project_run_approval_binds_goal_and_is_single_use(self):
        service = self._service()
        service.check_team()
        snapshot = service.snapshot()

        approval = service.request_project_run(
            snapshot["id"],
            "Prepare the local synthetic project",
        )
        self.assertEqual(approval["scope"]["action"], "start_project_run")
        self.assertEqual(
            approval["scope"]["goal"],
            "Prepare the local synthetic project",
        )
        with self.assertRaises(SupervisorError):
            service.decide_start(
                approval["id"],
                approve=True,
                confirmation="wrong",
            )
        service.decide_start(
            approval["id"],
            approve=True,
            confirmation=approval["scope_sha256"],
        )
        started = service.start_project_run(
            approval["id"],
            "Prepare the local synthetic project",
        )
        self.assertEqual(started["approval"]["status"], "consumed")
        self.assertEqual(
            started["event"]["event_type"],
            "project_run_start_authorized",
        )
        with self.assertRaises(SupervisorError):
            service.start_project_run(
                approval["id"],
                "Prepare the local synthetic project",
            )

    def test_project_run_approval_rejects_goal_and_team_drift(self):
        service = self._service()
        service.check_team()
        snapshot = service.snapshot()
        approval = service.request_project_run(snapshot["id"], "Frozen goal")
        service.decide_start(
            approval["id"],
            approve=True,
            confirmation=approval["scope_sha256"],
        )
        with self.assertRaises(SupervisorError):
            service.start_project_run(approval["id"], "Edited goal")

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
        with self.assertRaises(SupervisorError):
            service.start_project_run(approval["id"], "Frozen goal")

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

    def test_deterministic_local_agent_lifecycle_is_audited(self):
        service = self._service()
        service.configure_role(
            role_key="manager",
            agent_id="manager-agent",
            model_id="manager-model",
            launch_mode="spawn",
            transport="cli",
            check_profile={
                "fixture": "fake-cli",
                "lifecycle": {
                    "checks": {
                        "actual_model": {
                            "status": "passed",
                            "details": {"model_id": "manager-model"},
                        },
                        "protocol": {
                            "status": "passed",
                            "details": {"protocol": "cli"},
                        },
                    }
                },
            },
        )
        self.assertEqual(
            service.start_agent("manager")["session"]["state"],
            "started",
        )
        self.assertEqual(
            service.connect_agent("manager")["session"]["state"],
            "connected",
        )
        self.assertEqual(
            service.attach_agent("manager")["session"]["state"],
            "attached",
        )
        report = service.check_role("manager")
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["checks"]["actual_model"]["status"], "passed")
        self.assertEqual(report["checks"]["protocol"]["status"], "passed")
        self.assertEqual(
            service.detach_agent("manager")["session"]["state"],
            "detached",
        )
        self.assertEqual(
            service.stop_agent("manager")["session"]["state"],
            "stopped",
        )
        self.assertEqual(len(service.lifecycle_events("manager")), 5)

    def test_lifecycle_failure_and_model_mismatch_fail_closed(self):
        service = self._service()
        service.configure_role(
            role_key="worker",
            agent_id="worker-agent",
            model_id="worker-model",
            launch_mode="spawn",
            transport="cli",
            check_profile={
                "lifecycle": {
                    "operations": {
                        "start": {
                            "status": "failed",
                            "code": "fixture_process_missing",
                        }
                    },
                    "checks": {
                        "actual_model": {
                            "status": "passed",
                            "details": {"model_id": "other-model"},
                        },
                        "protocol": {"status": "passed"},
                    },
                }
            },
        )
        failed = service.start_agent("worker")
        self.assertEqual(failed["session"]["state"], "failed")
        report = service.check_role("worker")
        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(report["checks"]["process"]["status"], "failed")
        self.assertEqual(
            report["checks"]["actual_model"]["code"],
            "bound_model_not_observed",
        )

    def test_lifecycle_evidence_drift_stales_project_run_approval(self):
        service = self._service()
        for role in ("manager", "worker", "reviewer"):
            service.configure_role(
                role_key=role,
                agent_id=f"{role}-agent",
                model_id=f"{role}-model",
                launch_mode="spawn",
                transport="cli",
                check_profile={
                    "lifecycle": {
                        "checks": {
                            "actual_model": {
                                "status": "passed",
                                "details": {"model_id": f"{role}-model"},
                            },
                            "protocol": {"status": "passed"},
                        }
                    }
                },
            )
            service.start_agent(role)
        service.check_team()
        snapshot = service.snapshot()
        approval = service.request_project_run(snapshot["id"], "Frozen lifecycle goal")
        service.decide_start(
            approval["id"],
            approve=True,
            confirmation=approval["scope_sha256"],
        )
        service.stop_agent("worker")
        with self.assertRaises(SupervisorError):
            service.start_project_run(approval["id"], "Frozen lifecycle goal")
        self.assertEqual(service.approval(approval["id"])["status"], "stale")

    def _observation(self, agent_id="manager-agent", model_id="manager-model", measured_at=None):
        """A measured observation for one role.

        Board 30 requires a current observation alongside the declared
        preflight: a scope says what would be observed, and only a measurement
        says what was. Tests that need a ready non-mock role therefore bind both.
        """
        from model_council.observation import ObservationService
        from model_council.store import utc_now

        facts = {
            "process": {"status": "observed", "source": "local_process", "value": "exit_code=0"},
            "version": {"status": "observed", "source": "tool_output", "value": "0.154.0"},
            "permission": {"status": "observed", "source": "tool_output", "value": "read_only"},
            "protocol": {"status": "observed", "source": "tool_output", "value": "jsonl_events"},
            "actual_model": {"status": "unknown", "source": None},
            "connectivity": {"status": "observed", "source": "service_response", "value": "passed"},
            "login": {"status": "not_applicable", "source": None},
        }
        return ObservationService().build(
            {
                "agent_id": agent_id,
                "model_id": model_id,
                "provider_id": "local-fake",
                "measured_at": measured_at or utc_now(),
                "facts": facts,
                "evidence": {"retained": False, "prompt_tokens": 16078},
            }
        )

    def test_non_mock_role_requires_matching_preflight_and_binds_snapshot_provenance(self):
        self.registry.upsert_agent(
            "manager-agent",
            adapter_type="cli",
            provider_id="local-fake",
            model_id="manager-model",
            role="manager",
        )
        service = self._service()
        service.configure_role(
            role_key="manager",
            agent_id="manager-agent",
            model_id="manager-model",
            launch_mode="spawn",
            transport="cli",
            check_profile={"fixture": "fake-cli"},
        )
        self.assertEqual(
            service.check_role("manager")["errors"][0]["code"],
            "qualification_preflight_required",
        )
        preflight = self._qualification()
        bound = service.bind_qualification_preflight("manager", preflight)
        self.assertEqual(bound["status"], "current")
        observation = service.bind_observation_record(
            "manager", self._observation()
        )
        self.assertEqual(observation["integrity_status"], "current")
        self.assertEqual(service.check_role("manager")["status"], "ready")
        service.check_team()
        snapshot = service.snapshot()
        manager_role = next(
            item for item in snapshot["payload"]["roles"] if item["role_key"] == "manager"
        )
        self.assertEqual(
            manager_role["qualification_preflight_sha256"],
            preflight["scope_sha256"],
        )
        # The measured record is bound into the snapshot too, so a later
        # measurement change makes the snapshot stale rather than silently valid.
        self.assertEqual(
            manager_role["observation_record_sha256"],
            observation["record_sha256"],
        )
        self.assertEqual(
            manager_role["observation_measured_at"],
            observation["measured_at"],
        )
        approval = service.request_project_run(snapshot["id"], "Qualified goal")
        manager_scope = next(
            item for item in approval["scope"]["roles"] if item["role_key"] == "manager"
        )
        self.assertEqual(
            manager_scope["qualification_preflight_sha256"],
            preflight["scope_sha256"],
        )

    def test_preflight_digest_and_identity_are_verified_without_echoing_scope(self):
        self.registry.upsert_agent(
            "manager-agent",
            adapter_type="cli",
            provider_id="local-fake",
            model_id="manager-model",
            role="manager",
        )
        service = self._service()
        preflight = self._qualification()
        tampered = dict(preflight)
        tampered["scope_sha256"] = "0" * 64
        with self.assertRaises(SupervisorError):
            service.bind_qualification_preflight("manager", tampered)
        mismatched = self._qualification(model_id="worker-model")
        with self.assertRaises(SupervisorError):
            service.bind_qualification_preflight("manager", mismatched)

    def test_runtime_preflight_scope_tamper_blocks_readiness_and_snapshot(self):
        self.registry.upsert_agent(
            "manager-agent",
            adapter_type="cli",
            provider_id="local-fake",
            model_id="manager-model",
            role="manager",
        )
        service = self._service()
        service.bind_qualification_preflight("manager", self._qualification())
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE supervisor_qualification_preflights
                SET scope_json = ?
                WHERE role_key = 'manager'
                """,
                (json.dumps({"kind": "tampered"}),),
            )
        report = service.check_role("manager")
        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(
            report["errors"][0]["code"],
            "scope_digest_mismatch",
        )
        with self.assertRaises(SupervisorError):
            service.snapshot()

    def test_registry_identity_drift_blocks_current_preflight(self):
        self.registry.upsert_agent(
            "manager-agent",
            adapter_type="cli",
            provider_id="local-fake",
            model_id="manager-model",
            role="manager",
        )
        service = self._service()
        service.bind_qualification_preflight("manager", self._qualification())
        self.registry.upsert_agent(
            "manager-agent",
            adapter_type="cli",
            provider_id="local-fake",
            model_id="worker-model",
            role="manager",
        )
        report = service.check_role("manager")
        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(
            report["errors"][0]["code"],
            "registry_identity_drift",
        )

    def test_changed_preflight_stales_pending_project_approval(self):
        self.registry.upsert_agent(
            "manager-agent",
            adapter_type="cli",
            provider_id="local-fake",
            model_id="manager-model",
            role="manager",
        )
        service = self._service()
        service.bind_qualification_preflight("manager", self._qualification())
        service.bind_observation_record("manager", self._observation())
        service.check_team()
        snapshot = service.snapshot()
        approval = service.request_project_run(snapshot["id"], "Qualified goal")
        service.decide_start(
            approval["id"],
            approve=True,
            confirmation=approval["scope_sha256"],
        )
        # Recompute through the pure service so the supplied digest is valid.
        candidate = {
            **{
                "agent_id": "manager-agent",
                "model_id": "manager-model",
                "provider_id": "local-fake",
                "launch_mode": "spawn",
                "transport": "cli",
                "lifecycle_checks": [
                    "process", "login", "actual_model", "permission",
                    "version", "protocol", "connectivity",
                ],
                "permissions": ["read_only"],
                "context": {
                    "repository_context": False,
                    "private_project_content": False,
                    "worktree": False,
                    "workspace_write": False,
                    "prompt_instance": False,
                    "artifact_body": False,
                },
                "limits": {
                    "max_input_tokens": 100,
                    "max_output_tokens": 100,
                    "max_total_tokens": 200,
                    "max_total_cost": "0.01",
                    "currency": "USD",
                    "max_duration_seconds": 61,
                    "max_attempts": 1,
                    "retry_on_failure": False,
                },
                "approval_ladder": [
                    "preflight_review", "external_scope_approval", "execution_approval",
                ],
                "evidence": {
                    "storage": "runtime_only",
                    "retain_raw_output": False,
                    "retain_stdout": False,
                    "retain_stderr": False,
                    "retain_prompt": False,
                    "retain_response": False,
                },
                "execution_authorized": False,
            }
        }
        service.bind_qualification_preflight(
            "manager",
            QualificationPreflightService().evaluate(candidate),
        )
        self.assertEqual(service.approval(approval["id"])["status"], "stale")

    def test_cli_binds_eligible_preflight_through_supervisor_service(self):
        self.registry.upsert_agent(
            "manager-agent",
            adapter_type="cli",
            provider_id="local-fake",
            model_id="manager-model",
            role="manager",
        )
        service = self._service()
        scope = self._qualification()["normalized_scope"]
        candidate = {
            **scope["identity"],
            **scope["launch"],
            "lifecycle_checks": scope["lifecycle_checks"],
            "permissions": scope["permissions"],
            "context": scope["context_exclusions"],
            "limits": scope["limits"],
            "approval_ladder": scope["approval_ladder"],
            "evidence": scope["evidence_policy"],
            "execution_authorized": False,
        }
        candidate_path = Path(self.temp.name) / "qualification.json"
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        output = StringIO()
        with patch("model_council.cli.load_config", return_value=object()):
            with patch("model_council.cli._load_supervisor", return_value=service):
                with redirect_stdout(output):
                    main(
                        [
                            "supervisor",
                            "qualification-bind",
                            "manager",
                            "--candidate-file",
                            str(candidate_path),
                            "--config",
                            "unused.json",
                        ]
                    )
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["binding"]["status"], "current")

    def test_local_subprocess_fixture_uses_argument_array_and_stops_cleanly(self):
        service = self._service()
        fixture = SubprocessAgentLifecycleFixture(
            default_command=[
                sys.executable,
                str(Path(__file__).parent / "fixtures" / "fake_lifecycle_agent.py"),
            ]
        )
        service.lifecycle = fixture
        service.configure_role(
            role_key="manager",
            agent_id="manager-agent",
            model_id="manager-model",
            launch_mode="spawn",
            transport="cli",
            check_profile={
                "lifecycle": {
                    "checks": {
                        "actual_model": {
                            "status": "passed",
                            "details": {"model_id": "manager-model"},
                        },
                        "protocol": {"status": "passed"},
                    }
                }
            },
        )
        self.assertEqual(service.start_agent("manager")["session"]["state"], "started")
        duplicate = service.start_agent("manager")
        self.assertEqual(duplicate["session"]["state"], "failed")
        self.assertEqual(duplicate["session"]["failure"], "process_already_running")
        self.assertEqual(service.stop_agent("manager")["session"]["state"], "stopped")
        self.assertEqual(service.start_agent("manager")["session"]["state"], "started")
        self.assertEqual(service.connect_agent("manager")["session"]["state"], "connected")
        self.assertEqual(service.attach_agent("manager")["session"]["state"], "attached")
        self.assertEqual(service.detach_agent("manager")["session"]["state"], "detached")
        self.assertEqual(service.stop_agent("manager")["session"]["state"], "stopped")
        self.assertEqual(service.lifecycle_session("manager")["evidence"]["code"], "fixture_process_stopped")

    def test_cli_subprocess_fixture_persists_across_lifecycle_commands(self):
        root = Path(self.temp.name) / "cli-fixture"
        root.mkdir()
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "state_dir": "runtime",
                    "manager": "manager-agent",
                    "reviewer": "reviewer-agent",
                    "providers": {
                        "local-fake": {"kind": "local", "display_name": "Local Fake"}
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
        team_path = root / "team.json"
        team_path.write_text(
            json.dumps(
                {
                    "roles": {
                        role: {
                            "agent_id": f"{role}-agent",
                            "model_id": f"{role}-model",
                            "launch_mode": "spawn",
                            "transport": "cli",
                            "check_profile": {},
                        }
                        for role in ("manager", "worker", "reviewer")
                    }
                }
            ),
            encoding="utf-8",
        )
        main(["supervisor", "wizard", "--team-file", str(team_path), "--config", str(config_path)])
        output = StringIO()
        with redirect_stdout(output):
            main(
                [
                    "supervisor",
                    "lifecycle-sequence",
                    "manager",
                    "--operation",
                    "start",
                    "--operation",
                    "connect",
                    "--operation",
                    "attach",
                    "--operation",
                    "detach",
                    "--operation",
                    "stop",
                    "--config",
                    str(config_path),
                ]
            )
        outputs = json.loads(output.getvalue())
        self.assertEqual(
            [item["session"]["state"] for item in outputs],
            ["started", "connected", "attached", "detached", "stopped"],
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
