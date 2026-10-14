from __future__ import annotations

import json
import unittest

from model_council.authorization import (
    CONTEXT_EXCLUSIONS,
    CONTEXT_INCLUSIONS,
    PACKAGE_KIND,
    STATUS_BLOCKED,
    STATUS_ELIGIBLE_FOR_REVIEW,
    STATUS_USER_CONFIRMATION_REQUIRED,
    AuthorizationPackageError,
    AuthorizationPackageService,
)
from model_council.supervisor import CANONICAL_LIFECYCLE_CHECKS


def base_candidate() -> dict:
    return {
        "agent_id": "codex-architect",
        "model_id": "codex-configured-default",
        "provider_id": "codex-local",
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
            "max_input_tokens": 4000,
            "max_output_tokens": 1000,
            "max_total_tokens": 8000,
            "max_total_cost": "0.25",
            "currency": "USD",
            "max_duration_seconds": 120,
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


FULL_OBSERVATIONS = {
    "process": {"state": "observed"},
    "login": {"state": "observed"},
    "actual_model": {"state": "observed"},
    "permission": {"state": "read_only"},
    "version": {"state": "observed"},
    "protocol": {"state": "observed"},
    "connectivity": {"state": "observed"},
}


class AuthorizationPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AuthorizationPackageService()

    def test_package_is_deterministic_and_hashable(self):
        first = self.service.build(base_candidate())
        second = self.service.build(base_candidate())
        self.assertEqual(first["status"], STATUS_USER_CONFIRMATION_REQUIRED)
        self.assertEqual(first["package"], second["package"])
        self.assertEqual(first["package_sha256"], second["package_sha256"])
        self.assertTrue(
            self.service.verify(first["package"], first["package_sha256"])
        )
        self.assertFalse(self.service.verify(first["package"], "0" * 64))

    def test_missing_observation_evidence_requires_user_confirmation(self):
        result = self.service.build(base_candidate())
        self.assertTrue(result["user_confirmation_required"])
        self.assertEqual(
            sorted(result["missing_observations"]),
            sorted(FULL_OBSERVATIONS),
        )
        observed = result["facts"]["observed"]
        for kind in FULL_OBSERVATIONS:
            self.assertEqual(observed[kind], "unknown")
        self.assertEqual(
            result["package"]["launch"]["lifecycle_checks"],
            list(CANONICAL_LIFECYCLE_CHECKS),
        )

    def test_complete_observation_evidence_removes_confirmation_requirement(self):
        result = self.service.build(
            base_candidate(),
            declared={"agent_id": "codex-architect"},
            observations=FULL_OBSERVATIONS,
        )
        self.assertEqual(result["status"], STATUS_ELIGIBLE_FOR_REVIEW)
        self.assertFalse(result["user_confirmation_required"])
        self.assertEqual(result["missing_observations"], [])
        self.assertEqual(
            result["facts"]["declared"]["agent_id"],
            "codex-architect",
        )

    def test_digest_changes_when_observation_facts_change(self):
        without = self.service.build(base_candidate())
        with_evidence = self.service.build(
            base_candidate(),
            observations=FULL_OBSERVATIONS,
        )
        self.assertNotEqual(
            without["package_sha256"],
            with_evidence["package_sha256"],
            "an approved package must go stale when its facts change",
        )
        self.assertIn("fact_digest", with_evidence["package"])
        self.assertEqual(
            with_evidence["package"]["observed_fact_names"],
            sorted(FULL_OBSERVATIONS),
        )
        self.assertEqual(without["package"]["observed_fact_names"], [])

        drift = dict(FULL_OBSERVATIONS)
        drift["actual_model"] = {"state": "observed", "model_id": "other-model"}
        drifted = self.service.build(base_candidate(), observations=drift)
        self.assertNotEqual(
            with_evidence["package_sha256"],
            drifted["package_sha256"],
            "a changed observation value must change the package digest",
        )

    def test_no_tracked_package_value_contains_an_absolute_path(self):
        result = self.service.build(
            base_candidate(),
            observations=FULL_OBSERVATIONS,
        )
        serialized = json.dumps(result["package"], ensure_ascii=False)
        self.assertNotIn(":\\", serialized)
        self.assertNotIn(":/", serialized)
        self.assertNotIn("\\Users\\", serialized)
        self.assertNotIn("/home/", serialized)
        self.assertEqual(result["package"]["kind"], PACKAGE_KIND)

    def test_rejects_personal_paths_credentials_and_absolute_paths(self):
        home_path = "c:" + "\\Users" + "\\alice\\model"
        temp_path = "c:" + "\\Temp" + "\\model"
        unix_home = "/home" + "/alice/model"
        for field, value, expected in (
            ("model_id", home_path, "personal_path_forbidden"),
            ("model_id", temp_path, "absolute_path_forbidden"),
            ("model_id", unix_home, "personal_path_forbidden"),
            ("model_id", "sk-" + "a" * 24, "credential_value_forbidden"),
            ("model_id", "runtime-board14/state", "protected_runtime_reference_forbidden"),
        ):
            candidate = base_candidate()
            candidate[field] = value
            result = self.service.build(candidate)
            codes = {item["code"] for item in result["blockers"]}
            self.assertIn(expected, codes)
            self.assertIsNone(result["package"])
            self.assertIsNone(result["package_sha256"])

    def test_rejects_execution_authority_and_permission_expansion(self):
        candidate = base_candidate()
        candidate["execution_authorized"] = True
        result = self.service.build(candidate)
        self.assertEqual(result["status"], STATUS_BLOCKED)
        self.assertIn(
            "execution_authority_must_be_false",
            {item["code"] for item in result["blockers"]},
        )
        self.assertFalse(result["execution_authorized"])

        candidate = base_candidate()
        candidate["permissions"] = ["read_only", "workspace_write"]
        result = self.service.build(candidate)
        self.assertIn(
            "read_only_permission_required",
            {item["code"] for item in result["blockers"]},
        )

    def test_rejects_tools_files_artifacts_and_retry(self):
        candidate = base_candidate()
        candidate["tools"] = ["shell"]
        candidate["context"]["files"] = 1
        candidate["context"]["artifacts"] = 2
        candidate["limits"]["max_attempts"] = 3
        candidate["limits"]["retry_on_failure"] = True
        candidate["limits"]["timeout_action"] = "continue"
        result = self.service.build(candidate)
        codes = {item["code"] for item in result["blockers"]}
        for expected in (
            "no_tools_required",
            "zero_files_required",
            "zero_artifacts_required",
            "single_attempt_required",
            "retry_must_be_disabled",
            "timeout_must_stop",
        ):
            self.assertIn(expected, codes)

    def test_working_directory_is_a_reference_not_a_value(self):
        candidate = base_candidate()
        candidate["working_directory"] = {
            "category": "synthetic_workspace",
            "env_var": "synthetic cwd",
        }
        result = self.service.build(candidate)
        self.assertIn(
            "working_directory_env_var_required",
            {item["code"] for item in result["blockers"]},
        )

        candidate["working_directory"] = {
            "category": "unknown_place",
            "env_var": "MODEL_COUNCIL_SYNTHETIC_CWD",
        }
        result = self.service.build(candidate)
        self.assertIn(
            "unsupported_working_directory_category",
            {item["code"] for item in result["blockers"]},
        )

    def test_unknown_fields_are_rejected(self):
        candidate = base_candidate()
        candidate["surprise"] = "value"
        result = self.service.build(candidate)
        self.assertIn(
            "unsupported_candidate_field",
            {item["code"] for item in result["blockers"]},
        )

    def test_sensitive_key_names_are_rejected(self):
        candidate = base_candidate()
        candidate["declared"] = {"api_key_env": "X"}
        result = self.service.build(candidate)
        self.assertIn(
            "sensitive_field_forbidden",
            {item["code"] for item in result["blockers"]},
        )

    def test_non_object_candidate_raises(self):
        with self.assertRaises(AuthorizationPackageError):
            self.service.build(["not", "an", "object"])


if __name__ == "__main__":
    unittest.main()
