from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from model_council.observation import (
    OBSERVATION_KIND,
    ObservationError,
    ObservationService,
)
from model_council.registry import RegistryService
from model_council.store import CouncilStore, utc_now
from model_council.supervisor import SupervisorError, SupervisorService


ROLES = ("manager", "worker", "reviewer")
PROVIDER = "local-fake"


def measured_at(offset_seconds: int = 0):
    """An ISO timestamp offset from now, or a literal value passed through.

    A non-integer is returned unchanged so a test can submit a malformed
    timestamp without the helper raising first and hiding the validation.
    """
    if not isinstance(offset_seconds, int) or isinstance(offset_seconds, bool):
        return offset_seconds
    moment = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return moment.isoformat(timespec="seconds")


def observed_facts(**overrides):
    facts = {
        "process": {"status": "observed", "source": "local_process", "value": "exit=0"},
        "version": {"status": "observed", "source": "tool_output", "value": "0.154.0"},
        "permission": {"status": "observed", "source": "tool_output", "value": "read_only"},
        "protocol": {"status": "observed", "source": "tool_output", "value": "jsonl"},
        "connectivity": {"status": "observed", "source": "service_response", "value": "passed"},
        "actual_model": {"status": "unknown", "source": None},
        "login": {"status": "not_applicable", "source": None},
    }
    facts.update(overrides)
    return facts


def submission(**overrides):
    value = {
        "agent_id": "manager-agent",
        "model_id": "manager-model",
        "provider_id": PROVIDER,
        "measured_at": measured_at(),
        "facts": observed_facts(),
        "evidence": {"retained": False, "prompt_tokens": 16078},
    }
    value.update(overrides)
    return value


class ObservationRecordTests(unittest.TestCase):
    def setUp(self):
        self.service = ObservationService()

    def test_record_is_deterministic_and_verifiable(self):
        first = self.service.build(submission())
        second = self.service.build(submission())
        self.assertEqual(first["record"], second["record"])
        self.assertEqual(first["record_sha256"], second["record_sha256"])
        self.assertTrue(
            self.service.verify(first["record"], first["record_sha256"])
        )
        self.assertFalse(self.service.verify(first["record"], "0" * 64))
        self.assertEqual(first["record"]["kind"], OBSERVATION_KIND)

    def test_summary_separates_observed_unknown_and_not_applicable(self):
        result = self.service.build(submission())
        summary = result["summary"]
        self.assertIn("process", summary["observed"])
        self.assertIn("actual_model", summary["unknown"])
        self.assertIn("login", summary["not_applicable"])
        # A record with no observation at all is incomplete, not recorded.
        empty = self.service.build(
            submission(
                facts={
                    name: {"status": "unknown", "source": None}
                    for name in observed_facts()
                }
            )
        )
        self.assertEqual(empty["status"], "incomplete")

    def test_a_measurement_time_is_required(self):
        for value in (None, "", "yesterday", 17):
            with self.subTest(value=value):
                result = self.service.build(submission(measured_at=value))
                self.assertEqual(result["status"], "blocked")
                self.assertIn(
                    "explicit_measurement_time_required",
                    {item["code"] for item in result["blockers"]},
                )

    def test_a_shape_valid_but_impossible_moment_is_refused(self):
        # The outline matches and the date does not exist, so a shape check
        # alone would accept it and the error would surface only when ageing.
        result = self.service.build(
            submission(measured_at="2026-13-45T99:99:99Z")
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "measurement_time_not_a_real_moment",
            {item["code"] for item in result["blockers"]},
        )

    def test_an_observed_fact_must_say_how_it_was_obtained(self):
        facts = observed_facts()
        facts["version"] = {"status": "observed", "value": "0.154.0"}
        result = self.service.build(submission(facts=facts))
        self.assertIn(
            "observation_source_required",
            {item["code"] for item in result["blockers"]},
        )

    def test_an_observed_fact_must_carry_a_value(self):
        facts = observed_facts()
        facts["version"] = {"status": "observed", "source": "tool_output"}
        result = self.service.build(submission(facts=facts))
        self.assertIn(
            "observed_value_required",
            {item["code"] for item in result["blockers"]},
        )

    def test_an_unknown_fact_needs_no_source(self):
        facts = observed_facts()
        facts["actual_model"] = {"status": "unknown"}
        result = self.service.build(submission(facts=facts))
        self.assertEqual(result["status"], "recorded")

    def test_unknown_fact_names_are_rejected(self):
        facts = observed_facts()
        facts["made_up"] = {"status": "observed", "source": "tool_output", "value": "x"}
        result = self.service.build(submission(facts=facts))
        self.assertIn(
            "unsupported_fact_name",
            {item["code"] for item in result["blockers"]},
        )

    def test_sensitive_material_is_rejected(self):
        for field, value in (
            ("agent_id", "sk-" + "a" * 24),
            ("model_id", "runtime-board14/state"),
            ("provider_id", "c:" + "\\Users" + "\\alice"),
        ):
            with self.subTest(field=field):
                result = self.service.build(submission(**{field: value}))
                self.assertEqual(result["status"], "blocked")

    def test_prompt_tokens_survive_sensitive_key_filtering(self):
        result = self.service.build(
            submission(evidence={"retained": False, "prompt_tokens": 16078})
        )
        self.assertEqual(result["record"]["evidence"]["prompt_tokens"], 16078)

    def test_an_unknown_evidence_field_is_rejected(self):
        result = self.service.build(
            submission(evidence={"something_new": 1})
        )
        self.assertIn(
            "unsupported_evidence_field",
            {item["code"] for item in result["blockers"]},
        )

    def test_non_object_submission_raises(self):
        with self.assertRaises(ObservationError):
            self.service.build(["not", "an", "object"])


class StalenessTests(unittest.TestCase):
    def setUp(self):
        self.service = ObservationService()

    def test_a_fresh_record_is_not_stale(self):
        record = self.service.build(submission())["record"]
        self.assertIsNone(self.service.stale_reason(record, measured_at()))

    def test_an_expired_record_is_stale(self):
        # The default lifetime is seven days, so the measurement has to be older
        # than that. A few hours is not old enough and must stay current.
        record = self.service.build(
            submission(measured_at=measured_at(-8 * 24 * 3600))
        )["record"]
        self.assertEqual(
            self.service.stale_reason(record, measured_at()),
            "measurement_expired",
        )

    def test_a_record_within_its_lifetime_is_not_stale(self):
        record = self.service.build(
            submission(measured_at=measured_at(-1000))
        )["record"]
        self.assertIsNone(self.service.stale_reason(record, measured_at()))

    def test_an_explicit_lifetime_is_honoured(self):
        record = self.service.build(
            submission(measured_at=measured_at(-100)),
            max_age_seconds=60,
        )["record"]
        self.assertEqual(
            self.service.stale_reason(record, measured_at()),
            "measurement_expired",
        )
        longer = self.service.build(
            submission(measured_at=measured_at(-100)),
            max_age_seconds=10000,
        )["record"]
        self.assertIsNone(self.service.stale_reason(longer, measured_at()))

    def test_a_record_without_a_measurement_time_cannot_be_aged(self):
        record = self.service.build(submission())["record"]
        record.pop("measured_at", None)
        self.assertEqual(
            self.service.stale_reason(record, measured_at()),
            "measurement_time_missing",
        )

    def test_a_record_without_a_lifetime_is_refused(self):
        record = self.service.build(submission())["record"]
        record["max_age_seconds"] = 0
        self.assertEqual(
            self.service.stale_reason(record, measured_at()),
            "age_limit_missing",
        )

    def test_a_future_measurement_is_refused(self):
        record = self.service.build(
            submission(measured_at=measured_at(3600))
        )["record"]
        self.assertEqual(
            self.service.stale_reason(record, measured_at()),
            "measurement_in_the_future",
        )

    def test_an_unreadable_time_is_refused_rather_than_assumed_fresh(self):
        record = self.service.build(submission())["record"]
        record["measured_at"] = "not a timestamp"
        self.assertEqual(
            self.service.stale_reason(record, measured_at()),
            "measurement_time_unreadable",
        )


class ObservationBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CouncilStore(Path(self.temp.name) / "council.db")
        self.registry = RegistryService(self.store)
        self.registry.upsert_provider(
            PROVIDER, display_name="Local Fake", kind="local"
        )
        for role in ROLES:
            self.registry.upsert_model(
                f"{role}-model", provider_id=PROVIDER, display_name=role.title()
            )
        self.service = ObservationService()

    def _ready_supervisor(self, cli_manager=False, check_profile=None, check=True):
        """A supervisor whose team is checked.

        ``cli_manager`` makes the manager a non-mock Agent before the readiness
        check runs, so the stored report matches the binding that the
        qualification requirement is evaluated against. Swapping the Agent
        afterwards would leave a report whose binding digest no longer matches,
        and the readiness failure would then be about the binding rather than
        about the qualification check under test.

        ``check=False`` skips the readiness pass, which is needed when the caller
        must bind a qualification preflight first: a report recorded before that
        binding would keep saying `qualification_preflight_required` forever,
        because a stored report is not recomputed behind the caller's back.
        """
        inspector_checks = {
            "process": {"status": "passed", "details": {}},
            "login": {"status": "passed", "details": {}},
            "model": {"status": "passed", "details": {"model_id": "manager-model"}},
            "permission": {"status": "passed", "details": {}},
            "version": {"status": "passed", "details": {}},
            "connection": {"status": "passed", "details": {}},
        }

        class Inspector:
            def inspect(self, binding):
                bound = dict(inspector_checks)
                bound["model"] = {
                    "status": "passed",
                    "details": {"model_id": binding["model_id"]},
                }
                return bound

        for role in ROLES:
            self.registry.upsert_agent(
                f"{role}-agent",
                adapter_type="cli" if (cli_manager and role == "manager") else "mock",
                provider_id=PROVIDER,
                model_id=f"{role}-model",
                role=role,
            )
        supervisor = SupervisorService(
            self.store, self.registry, inspector=Inspector()
        )
        for role in ROLES:
            supervisor.configure_role(
                role_key=role,
                agent_id=f"{role}-agent",
                model_id=f"{role}-model",
                launch_mode="spawn",
                transport="cli",
                check_profile=(
                    check_profile
                    if (check_profile is not None and role == "manager")
                    else {"fixture": "local"}
                ),
            )
        if check:
            supervisor.check_team()
        return supervisor

    def test_a_bound_record_is_current_and_grants_nothing(self):
        supervisor = self._ready_supervisor()
        built = self.service.build(submission())
        bound = supervisor.bind_observation_record("manager", built)

        self.assertEqual(bound["record_sha256"], built["record_sha256"])
        self.assertEqual(bound["integrity_status"], "current")
        self.assertIsNone(bound["integrity_code"])
        self.assertIsNone(bound["captured_team_snapshot_id"])
        self.assertIn("process", bound["summary"]["observed"])
        self.assertEqual(supervisor.approvals(), [])

    def test_expired_measurements_read_back_as_stale(self):
        supervisor = self._ready_supervisor()
        built = self.service.build(
            submission(measured_at=measured_at(-8 * 24 * 3600))
        )
        supervisor.bind_observation_record("manager", built)

        read_back = supervisor.observation_record("manager")
        self.assertEqual(read_back["integrity_status"], "stale")
        self.assertEqual(read_back["integrity_code"], "measurement_expired")

    def test_a_tampered_record_is_invalid(self):
        supervisor = self._ready_supervisor()
        built = self.service.build(submission())
        supervisor.bind_observation_record("manager", built)

        tampered = json.loads(json.dumps(built["record"]))
        tampered["facts"]["version"]["value"] = "9.9.9"
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE supervisor_observation_records
                SET record_json = ?
                WHERE role_key = 'manager'
                """,
                (json.dumps(tampered),),
            )

        read_back = supervisor.observation_record("manager")
        self.assertEqual(read_back["integrity_status"], "invalid")
        self.assertEqual(read_back["integrity_code"], "record_digest_mismatch")

    def test_binding_rejects_a_mismatched_identity(self):
        supervisor = self._ready_supervisor()
        built = self.service.build(
            submission(agent_id="worker-agent", model_id="worker-model")
        )
        with self.assertRaises(SupervisorError):
            supervisor.bind_observation_record("manager", built)

    def test_binding_rejects_an_invalid_digest(self):
        supervisor = self._ready_supervisor()
        built = self.service.build(submission())
        forged = dict(built)
        forged["record_sha256"] = "0" * 64
        with self.assertRaises(SupervisorError):
            supervisor.bind_observation_record("manager", forged)

    def test_binding_rejects_a_blocked_result(self):
        supervisor = self._ready_supervisor()
        blocked = self.service.build(submission(measured_at=None))
        with self.assertRaises(SupervisorError):
            supervisor.bind_observation_record("manager", blocked)

    def test_a_non_mock_role_is_not_ready_without_an_observation(self):
        # An empty profile keeps the qualification requirement in force: a
        # profile carrying synthetic_checks is the explicit test-fixture
        # exemption, and using it here would skip the check being tested.
        supervisor = self._ready_supervisor(
            cli_manager=True, check_profile={}, check=False
        )
        supervisor.bind_qualification_preflight(
            "manager", self._qualification()
        )
        supervisor.check_team()
        # A declared scope is not a measurement, so readiness still refuses.
        with self.assertRaises(SupervisorError) as caught:
            supervisor.snapshot()
        self.assertIn("observation", str(caught.exception))

        supervisor.bind_observation_record("manager", self.service.build(submission()))
        snapshot = supervisor.snapshot()
        role = next(
            item
            for item in snapshot["payload"]["roles"]
            if item["role_key"] == "manager"
        )
        self.assertIsNotNone(role["observation_record_sha256"])
        self.assertIsNotNone(role["observation_measured_at"])

    def test_a_measurement_change_makes_the_snapshot_stale(self):
        supervisor = self._ready_supervisor(
            cli_manager=True, check_profile={}, check=False
        )
        supervisor.bind_qualification_preflight(
            "manager", self._qualification()
        )
        supervisor.check_team()
        supervisor.bind_observation_record(
            "manager", self.service.build(submission())
        )
        snapshot = supervisor.snapshot()

        # Re-bind with a different measurement; the captured snapshot no longer
        # describes the current evidence.
        changed = self.service.build(
            submission(
                measured_at=measured_at(1),
                facts=observed_facts(
                    version={
                        "status": "observed",
                        "source": "tool_output",
                        "value": "0.155.0",
                    }
                ),
            )
        )
        supervisor.bind_observation_record("manager", changed)
        with self.assertRaises(SupervisorError):
            supervisor.validate_snapshot(snapshot["id"])

    def _qualification(self):
        from model_council.qualification import QualificationPreflightService

        return QualificationPreflightService().evaluate(
            {
                "agent_id": "manager-agent",
                "model_id": "manager-model",
                "provider_id": PROVIDER,
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
                    "max_input_tokens": 20000,
                    "max_output_tokens": 1000,
                    "max_total_tokens": 30000,
                    "max_total_cost": "0.10",
                    "currency": "USD",
                    "max_duration_seconds": 120,
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


class ObservationProjectionTests(unittest.TestCase):
    """CLI read-only projections for bound observations."""

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
                        PROVIDER: {"kind": "local", "display_name": "Local"}
                    },
                    "models": {
                        f"{role}-model": {
                            "provider": PROVIDER,
                            "display_name": role.title(),
                        }
                        for role in ROLES
                    },
                    "agents": {
                        f"{role}-agent": {
                            "type": "mock",
                            "provider": PROVIDER,
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
            PROVIDER, display_name="Local", kind="local"
        )
        for role in ROLES:
            self.registry.upsert_model(
                f"{role}-model", provider_id=PROVIDER, display_name=role.title()
            )
            self.registry.upsert_agent(
                f"{role}-agent",
                adapter_type="mock",
                provider_id=PROVIDER,
                model_id=f"{role}-model",
                role=role,
            )
        self.service = ObservationService()

    def _capture(self, argv):
        from contextlib import redirect_stdout
        from io import StringIO

        from model_council.cli import main

        output = StringIO()
        with redirect_stdout(output):
            main(argv)
        return json.loads(output.getvalue())

    def _supervisor_with_manager(self):
        """A supervisor with the manager role configured, nothing else needed.

        Binding validates the role against the configured team, so the role has
        to exist even though this test only reads the projection afterwards.
        """
        supervisor = SupervisorService(self.store, self.registry)
        supervisor.configure_role(
            role_key="manager",
            agent_id="manager-agent",
            model_id="manager-model",
            launch_mode="spawn",
            transport="cli",
            check_profile={"fixture": "local"},
        )
        return supervisor

    def test_observation_show_is_empty_before_binding(self):
        shown = self._capture(
            ["supervisor", "observation-show", "--config", str(self.config_path)]
        )
        self.assertEqual(shown["observation_records"], [])

    def test_observation_show_projects_a_bound_record(self):
        supervisor = self._supervisor_with_manager()
        built = self.service.build(submission())
        supervisor.bind_observation_record("manager", built)

        shown = self._capture(
            ["supervisor", "observation-show", "--config", str(self.config_path)]
        )
        self.assertEqual(len(shown["observation_records"]), 1)
        entry = shown["observation_records"][0]
        self.assertEqual(entry["role_key"], "manager")
        self.assertEqual(entry["integrity_status"], "current")
        self.assertEqual(entry["record_sha256"], built["record_sha256"])
        self.assertIn("process", entry["summary"]["observed"])

        single = self._capture(
            [
                "supervisor",
                "observation-show",
                "--role",
                "manager",
                "--config",
                str(self.config_path),
            ]
        )
        self.assertEqual(single["role_key"], "manager")

    def test_supervisor_show_includes_the_observation_projection(self):
        supervisor = self._supervisor_with_manager()
        supervisor.bind_observation_record(
            "manager", self.service.build(submission())
        )
        full = self._capture(
            ["supervisor", "show", "--config", str(self.config_path)]
        )
        self.assertEqual(len(full["observation_records"]), 1)


if __name__ == "__main__":
    unittest.main()
