from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from model_council.authorization import (
    CONTEXT_EXCLUSIONS,
    CONTEXT_INCLUSIONS,
    STATUS_ELIGIBLE_FOR_REVIEW,
    STATUS_USER_CONFIRMATION_REQUIRED,
    AuthorizationPackageService,
)
from model_council.cli import main
from model_council.registry import RegistryService
from model_council.store import CouncilStore
from model_council.supervisor import SupervisorError, SupervisorService


ROLE = "manager"
ROLES = ("manager", "worker", "reviewer")
FACT_KINDS = (
    "process",
    "login",
    "actual_model",
    "permission",
    "version",
    "protocol",
    "connectivity",
)
READINESS_CHECKS = (
    "process",
    "login",
    "model",
    "permission",
    "version",
    "connection",
)
# The `model` entry is role-specific and is added per role; everything else is
# identical for every member.
READINESS_CHECKS_BASE = {
    "process": {"status": "passed", "details": {"fixture": "local"}},
    "login": {"status": "passed", "details": {"fixture": "local"}},
    "permission": {"status": "passed", "details": {"permission": "read_only"}},
    "version": {"status": "passed", "details": {"version": "fake-1"}},
    "connection": {
        "status": "passed",
        "details": {"endpoint": "loopback-fixture"},
    },
}


def authorization_candidate(agent_id="manager-agent", model_id="manager-model"):
    return {
        "agent_id": agent_id,
        "model_id": model_id,
        "provider_id": "local-fake",
        "launch_mode": "spawn",
        "transport": "cli",
        "permissions": ["read_only"],
        "tools": ["none"],
        "context": {
            "include": list(CONTEXT_INCLUSIONS),
            "exclude": list(CONTEXT_EXCLUSIONS),
            "files": 0,
            "artifacts": 0,
        },
        "working_directory": {
            "category": "synthetic_workspace",
            "env_var": "MODEL_COUNCIL_SYNTHETIC_CWD",
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
            "timeout_action": "stop",
        },
        "approval_ladder": ["authorization_review", "execution_approval"],
        "single_use": {
            "consume_once": True,
            "reusable": False,
            "replay_forbidden": True,
        },
        "execution_authorized": False,
    }


class ScriptedInspector:
    def __init__(self, checks_by_role):
        self.checks_by_role = checks_by_role

    def inspect(self, binding):
        return self.checks_by_role[binding["role_key"]]


class AuthorizationBindingTests(unittest.TestCase):
    """Service-level coverage for binding an authorization package."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = CouncilStore(self.root / "runtime" / "council.db")
        self.registry = RegistryService(self.store)
        self.registry.upsert_provider(
            "local-fake",
            display_name="Local Fake Provider",
            kind="local",
        )
        for role in ROLES:
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
        self.service = AuthorizationPackageService()

    def _passed_checks(self, role):
        return {
            "process": {"status": "passed", "details": {"fixture": "local"}},
            "login": {"status": "passed", "details": {"fixture": "local"}},
            "model": {
                "status": "passed",
                "details": {"model_id": f"{role}-model"},
            },
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

    def _service(self):
        inspector = ScriptedInspector(
            {role: self._passed_checks(role) for role in ROLES}
        )
        supervisor = SupervisorService(
            self.store,
            self.registry,
            inspector=inspector,
        )
        for role in ROLES:
            supervisor.configure_role(
                role_key=role,
                agent_id=f"{role}-agent",
                model_id=f"{role}-model",
                launch_mode="spawn",
                transport="cli",
                check_profile={"fixture": "fake-cli"},
            )
        return supervisor

    def _ready_service(self):
        """A service whose team has already been checked and snapshotted."""
        supervisor = self._service()
        supervisor.check_team()
        supervisor.snapshot()
        return supervisor

    @staticmethod
    def _observations(state="observed"):
        return {kind: {"state": state} for kind in FACT_KINDS}

    def _built(self, **kwargs):
        return self.service.build(authorization_candidate(**kwargs))

    # ------------------------------------------------------------- binding

    def test_binding_requires_a_team_snapshot(self):
        supervisor = self._service()
        built = self.service.build(authorization_candidate())
        with self.assertRaises(SupervisorError):
            supervisor.bind_authorization_package(ROLE, built)

    def test_binding_stores_the_package_and_stays_read_only(self):
        supervisor = self._ready_service()
        snapshot_id = supervisor.latest_snapshot()["id"]
        built = self.service.build(
            authorization_candidate(),
            observations=self._observations(),
        )
        self.assertEqual(built["status"], STATUS_ELIGIBLE_FOR_REVIEW)

        bound = supervisor.bind_authorization_package(ROLE, built)

        self.assertEqual(bound["package_sha256"], built["package_sha256"])
        self.assertEqual(bound["captured_team_snapshot_id"], snapshot_id)
        self.assertEqual(bound["integrity_status"], "current")
        self.assertEqual(bound["snapshot_status"], "current")
        self.assertEqual(bound["package_status"], STATUS_ELIGIBLE_FOR_REVIEW)
        self.assertFalse(bound["execution_authorized"])
        self.assertIsNone(bound["captured_approval_id"])
        self.assertEqual(supervisor.approvals(), [])

        listed = supervisor.authorization_packages()
        self.assertEqual(len(listed), 1)
        self.assertFalse(listed[0]["execution_authorized"])

    def test_incomplete_evidence_binding_stays_user_confirmation_required(self):
        supervisor = self._ready_service()
        built = self.service.build(authorization_candidate())
        self.assertEqual(built["status"], STATUS_USER_CONFIRMATION_REQUIRED)

        bound = supervisor.bind_authorization_package(ROLE, built)

        self.assertEqual(
            bound["package_status"],
            STATUS_USER_CONFIRMATION_REQUIRED,
        )
        self.assertTrue(bound["user_confirmation_required"])
        self.assertEqual(
            sorted(bound["missing_observations"]),
            sorted(FACT_KINDS),
        )
        self.assertEqual(bound["integrity_status"], "current")

    def test_drifted_bound_facts_make_the_package_stale(self):
        supervisor = self._ready_service()
        built = self.service.build(
            authorization_candidate(),
            observations=self._observations(),
        )
        supervisor.bind_authorization_package(ROLE, built)

        drifted = {
            "declared": {},
            "observed": {
                kind: {"state": "observed"} for kind in FACT_KINDS
            },
            "confirmed": {},
        }
        drifted["observed"]["actual_model"] = {"model_id": "other-model"}
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE supervisor_authorization_packages
                SET facts_json = ?
                WHERE role_key = ?
                """,
                (json.dumps(drifted), ROLE),
            )

        read_back = supervisor.authorization_package(ROLE)
        self.assertEqual(read_back["integrity_status"], "stale")
        self.assertEqual(read_back["integrity_code"], "bound_facts_drifted")

    def test_tampered_package_digest_is_invalid(self):
        supervisor = self._ready_service()
        built = self.service.build(authorization_candidate())
        supervisor.bind_authorization_package(ROLE, built)

        tampered = json.loads(json.dumps(built["package"]))
        tampered["permissions"] = ["read_only", "workspace_write"]
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE supervisor_authorization_packages
                SET package_json = ?
                WHERE role_key = ?
                """,
                (json.dumps(tampered), ROLE),
            )

        read_back = supervisor.authorization_package(ROLE)
        self.assertEqual(read_back["integrity_status"], "invalid")
        self.assertEqual(read_back["integrity_code"], "package_digest_mismatch")

    def test_binding_rejects_a_mismatched_identity(self):
        supervisor = self._ready_service()
        built = self.service.build(
            authorization_candidate(
                agent_id="worker-agent",
                model_id="worker-model",
            )
        )
        with self.assertRaises(SupervisorError):
            supervisor.bind_authorization_package(ROLE, built)

    def test_binding_rejects_a_package_claiming_execution_authority(self):
        supervisor = self._ready_service()
        built = self.service.build(authorization_candidate())
        forged = dict(built)
        forged["execution_authorized"] = True
        with self.assertRaises(SupervisorError):
            supervisor.bind_authorization_package(ROLE, forged)

    def test_binding_rejects_facts_that_do_not_reproduce_the_digest(self):
        supervisor = self._ready_service()
        built = self.service.build(authorization_candidate())
        forged = dict(built)
        forged["facts"] = {
            "declared": {},
            "observed": {
                kind: {"state": "observed"} for kind in FACT_KINDS
            },
            "confirmed": {},
        }
        with self.assertRaises(SupervisorError):
            supervisor.bind_authorization_package(ROLE, forged)

    def test_binding_rejects_an_unbuilt_result(self):
        supervisor = self._ready_service()
        blocked = self.service.build({"agent_id": "x"})
        with self.assertRaises(SupervisorError):
            supervisor.bind_authorization_package(ROLE, blocked)

    def test_new_snapshot_supersedes_the_captured_binding(self):
        supervisor = self._ready_service()
        built = self.service.build(authorization_candidate())
        supervisor.bind_authorization_package(ROLE, built)
        supervisor.snapshot()

        read_back = supervisor.authorization_package(ROLE)
        self.assertEqual(read_back["snapshot_status"], "superseded")


class AuthorizationProjectionTests(unittest.TestCase):
    """CLI read-only projections for the bound package."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "runtime"
        self.state.mkdir(parents=True, exist_ok=True)
        self.config_path = self.root / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "state_dir": str(self.state),
                    "manager": "manager-agent",
                    "reviewer": "reviewer-agent",
                    "providers": {
                        "local-fake": {
                            "kind": "local",
                            "display_name": "Local Fake",
                        }
                    },
                    "models": {
                        f"{role}-model": {
                            "provider": "local-fake",
                            "display_name": f"{role.title()} Model",
                        }
                        for role in ROLES
                    },
                    "agents": {
                        f"{role}-agent": {
                            "type": "mock",
                            "provider": "local-fake",
                            "model": f"{role}-model",
                            "role": role,
                        }
                        for role in ROLES
                    },
                }
            ),
            encoding="utf-8",
        )
        self.store = CouncilStore(self.state / "council.db")
        self.registry = RegistryService(self.store)
        self.registry.upsert_provider(
            "local-fake",
            display_name="Local Fake Provider",
            kind="local",
        )
        for role in ROLES:
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
        self.service = AuthorizationPackageService()

    def _capture(self, argv) -> dict:
        output = StringIO()
        with redirect_stdout(output):
            main(argv)
        return json.loads(output.getvalue())

    def _prepare_bound_package(self):
        """Build readiness from the stored profile, exactly as the CLI does.

        The CLI loads a Supervisor without an inspector, so readiness comes from
        `check_profile["synthetic_checks"]` through `StaticReadinessInspector`.
        The profile is supplied first and the real inspector is then used, which
        keeps both projection tests and the CLI on one code path.
        """
        profile = {
            "synthetic_checks": {
                "process": {"status": "passed", "details": {"fixture": "local"}},
                "login": {"status": "passed", "details": {"fixture": "local"}},
                "model": {
                    "status": "passed",
                    "details": {"model_id": f"{ROLE}-model"},
                },
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
        }
        supervisor = SupervisorService(self.store, self.registry)
        for role in ROLES:
            supervisor.configure_role(
                role_key=role,
                agent_id=f"{role}-agent",
                model_id=f"{role}-model",
                launch_mode="spawn",
                transport="cli",
                check_profile={
                    "synthetic_checks": {
                        **READINESS_CHECKS_BASE,
                        "model": {
                            "status": "passed",
                            "details": {"model_id": f"{role}-model"},
                        },
                    }
                },
            )
        supervisor.check_team()
        supervisor.snapshot()
        built = self.service.build(
            authorization_candidate(),
            observations={
                kind: {"state": "observed"} for kind in FACT_KINDS
            },
        )
        supervisor.bind_authorization_package(ROLE, built)
        return built

    def test_authorization_show_is_empty_before_binding(self):
        shown = self._capture(
            ["supervisor", "authorization-show", "--config", str(self.config_path)]
        )
        self.assertEqual(shown["authorization_packages"], [])

    def test_authorization_show_projects_the_bound_package(self):
        built = self._prepare_bound_package()

        shown = self._capture(
            ["supervisor", "authorization-show", "--config", str(self.config_path)]
        )
        self.assertEqual(len(shown["authorization_packages"]), 1)
        entry = shown["authorization_packages"][0]
        self.assertEqual(entry["role_key"], ROLE)
        self.assertEqual(entry["integrity_status"], "current")
        self.assertEqual(entry["package_status"], STATUS_ELIGIBLE_FOR_REVIEW)
        self.assertEqual(entry["package_sha256"], built["package_sha256"])
        self.assertFalse(entry["execution_authorized"])

        single = self._capture(
            [
                "supervisor",
                "authorization-show",
                "--role",
                ROLE,
                "--config",
                str(self.config_path),
            ]
        )
        self.assertEqual(single["role_key"], ROLE)

    def test_supervisor_show_includes_the_authorization_projection(self):
        self._prepare_bound_package()
        full = self._capture(
            ["supervisor", "show", "--config", str(self.config_path)]
        )
        self.assertEqual(len(full["authorization_packages"]), 1)


if __name__ == "__main__":
    unittest.main()
