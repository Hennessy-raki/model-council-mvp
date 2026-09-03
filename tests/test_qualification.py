from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from model_council.cli import main
from model_council.qualification import QualificationPreflightService


class QualificationPreflightTests(unittest.TestCase):
    def _candidate(self) -> dict:
        return {
            "agent_id": "candidate-agent",
            "model_id": "candidate-model",
            "provider_id": "candidate-provider",
            "launch_mode": "attach",
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

    def test_valid_candidate_has_stable_digest_and_no_execution_authority(self):
        service = QualificationPreflightService()

        first = service.evaluate(self._candidate())
        second = service.evaluate(self._candidate())

        self.assertEqual(first["status"], "eligible_for_separate_review")
        self.assertFalse(first["execution_authorized"])
        self.assertEqual(first["scope_sha256"], second["scope_sha256"])
        self.assertEqual(first["normalized_scope"]["permissions"], ["read_only"])
        self.assertFalse(
            first["normalized_scope"]["context_exclusions"]["repository_context"]
        )

    def test_private_context_and_unbounded_execution_claims_fail_closed(self):
        candidate = self._candidate()
        candidate["context"]["repository_context"] = True
        candidate["permissions"] = ["read_only", "workspace_write"]
        candidate["limits"]["max_attempts"] = 2
        candidate["execution_authorized"] = True

        result = QualificationPreflightService().evaluate(candidate)

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["execution_authorized"])
        self.assertIsNone(result["normalized_scope"])
        self.assertIsNone(result["scope_sha256"])
        self.assertEqual(
            {item["code"] for item in result["blockers"]},
            {
                "private_context_must_be_excluded",
                "read_only_permission_required",
                "single_attempt_required",
                "execution_authority_must_be_false",
            },
        )

    def test_credential_and_personal_path_are_rejected_without_echoing_values(self):
        candidate = self._candidate()
        candidate["agent_id"] = "candidate-agent"
        candidate["evidence"]["note"] = "Bearer private-value"
        candidate["context"]["private_project_content"] = (
            "C:" + chr(92) + "Users" + chr(92) + "private-user" + chr(92) + "project"
        )

        result = QualificationPreflightService().evaluate(candidate)
        rendered = json.dumps(result, ensure_ascii=False)

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "credential_value_forbidden",
            {item["code"] for item in result["blockers"]},
        )
        self.assertIn(
            "personal_path_forbidden",
            {item["code"] for item in result["blockers"]},
        )
        self.assertNotIn("private-value", rendered)
        self.assertNotIn("private-user", rendered)

    def test_cli_uses_pure_service_without_loading_config_or_runtime_state(self):
        with TemporaryDirectory() as temp:
            candidate_path = Path(temp) / "candidate.json"
            candidate_path.write_text(
                json.dumps(self._candidate()),
                encoding="utf-8",
            )
            output = StringIO()
            with patch(
                "model_council.cli.load_config",
                side_effect=AssertionError("preflight must not load config"),
            ):
                with redirect_stdout(output):
                    main(
                        [
                            "supervisor",
                            "qualification-preflight",
                            "--candidate-file",
                            str(candidate_path),
                        ]
                    )

        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "eligible_for_separate_review")
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
