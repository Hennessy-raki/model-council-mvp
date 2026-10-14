from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
import os
import unittest

from model_council.adapters.openai_compatible import OpenAICompatibleAdapter
from model_council.outbound_context import (
    OutboundContextPolicy,
    OutboundContextService,
    OutboundContextApprovalRequired,
)
from model_council.registry import RegistryService
from model_council.store import CouncilStore
from model_council.supervisor import SupervisorService
from model_council.types import AgentCard, AgentRequest

API_KEY_ENV = "IDENTITY_TEST_API_KEY"
OUTBOUND = {
    "source": "board29-test",
    "allowed_sources": ["board29-test"],
    "max_total_bytes": 4096,
    "max_files": 0,
    "max_artifacts": 0,
    "excluded_patterns": ["C:\\\\", "/home", "\\\\Users"],
}


def build_adapter(store, model="configured-model"):
    card = AgentCard("architect", "architect", "describe", ("architecture",), ())
    return OpenAICompatibleAdapter(
        card,
        {
            "base_url": "https://provider.example/v1",
            "model": model,
            "api_key_env": API_KEY_ENV,
            "api_style": "responses",
            "invoke_enabled": True,
            "outbound_context": OUTBOUND,
        },
        outbound_context=OutboundContextService(store),
    )


def sample_request():
    return AgentRequest(
        run_id="run",
        task_id="task",
        mode="architecture",
        goal="observe identity",
        instruction="return a token",
        sender="operator",
        recipient="architect",
    )


class ModelIdentityTests(unittest.TestCase):
    """The observed model is a different claim from the configured model."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CouncilStore(Path(self.temp.name) / "council.db")

    def _invoke(self, payload, model="configured-model"):
        """Drive one invocation through the real approval chain.

        The adapter refuses an unapproved outbound scope by design, so the test
        prepares a manifest, approves it exactly, and then invokes with that
        approval attached. The HTTP hop is the only thing stubbed.
        """
        adapter = build_adapter(self.store, model=model)
        service = adapter.outbound_context
        request = sample_request()
        with patch.dict(os.environ, {API_KEY_ENV: "test-value"}):
            try:
                adapter.invoke(request)
                raise AssertionError("an unapproved scope must be refused")
            except OutboundContextApprovalRequired as required:
                manifest_id = required.manifest_id
            manifest = service.manifest(manifest_id, include_prompt=True)
            # Confirmation must match the displayed approval digest exactly,
            # which is what binds the approval to this one scope.
            service.decide(
                manifest_id,
                approve=True,
                confirmation=manifest["approval_sha256"],
            )
            request.metadata["outbound_context_manifest_id"] = manifest_id
            with patch.object(adapter, "_read_json", return_value=payload):
                return adapter.invoke(request)

    def test_server_reported_model_is_recorded_separately(self):
        response = self._invoke(
            {
                "model": "actually-serving-model",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "text", "text": "ok"}],
                    }
                ],
                "usage": {"input_tokens": 16078, "output_tokens": 12},
            }
        )
        meta = response.metadata
        self.assertEqual(meta["configured_model"], "configured-model")
        self.assertEqual(meta["observed_model"], "actually-serving-model")
        self.assertEqual(meta["observed_model_source"], "provider_response")
        self.assertTrue(meta["model_identity_mismatch"])
        # The configured value stays available under the original key, so
        # existing consumers keep working.
        self.assertEqual(meta["model"], "configured-model")

    def test_matching_identity_is_not_flagged_as_a_mismatch(self):
        response = self._invoke(
            {
                "model": "configured-model",
                "output": [
                    {"type": "message", "content": [{"type": "text", "text": "ok"}]}
                ],
            }
        )
        self.assertEqual(response.metadata["observed_model"], "configured-model")
        self.assertNotIn("model_identity_mismatch", response.metadata)
        self.assertEqual(
            response.metadata["observed_model_source"],
            "provider_response",
        )

    def test_absent_identity_is_recorded_as_unavailable_not_guessed(self):
        response = self._invoke(
            {
                "output": [
                    {"type": "message", "content": [{"type": "text", "text": "ok"}]}
                ],
            }
        )
        meta = response.metadata
        self.assertIsNone(meta["observed_model"])
        self.assertEqual(meta["observed_model_source"], "unavailable")
        self.assertNotIn("model_identity_mismatch", meta)

    def test_identity_is_read_from_usage_when_absent_at_top_level(self):
        response = self._invoke(
            {
                "output": [
                    {"type": "message", "content": [{"type": "text", "text": "ok"}]}
                ],
                "usage": {"model": "from-usage", "input_tokens": 5},
            }
        )
        meta = response.metadata
        self.assertEqual(meta["observed_model"], "from-usage")
        self.assertEqual(meta["observed_model_source"], "provider_usage")
        self.assertTrue(meta["model_identity_mismatch"])

    def test_prompt_tokens_are_recorded_when_reported(self):
        response = self._invoke(
            {
                "output": [
                    {"type": "message", "content": [{"type": "text", "text": "ok"}]}
                ],
                "usage": {"input_tokens": 16078, "output_tokens": 12},
            }
        )
        self.assertEqual(response.metadata["prompt_tokens"], 16078)
        self.assertEqual(
            response.metadata["usage_source"],
            "provider_reported",
        )

    def test_prompt_tokens_accepts_the_chat_completions_field_name(self):
        response = self._invoke(
            {
                "output": [
                    {"type": "message", "content": [{"type": "text", "text": "ok"}]}
                ],
                "usage": {"prompt_tokens": 4242},
            }
        )
        self.assertEqual(response.metadata["prompt_tokens"], 4242)

    def test_prompt_tokens_absent_is_not_recorded(self):
        response = self._invoke(
            {
                "output": [
                    {"type": "message", "content": [{"type": "text", "text": "ok"}]}
                ],
            }
        )
        self.assertNotIn("prompt_tokens", response.metadata)

    def test_invocation_without_approval_still_requires_it(self):
        adapter = build_adapter(self.store)
        with patch.dict(os.environ, {API_KEY_ENV: "test-value"}):
            with self.assertRaises(OutboundContextApprovalRequired):
                adapter.invoke(sample_request())


class StaticReportedModelTests(unittest.TestCase):
    def test_extract_reported_model_accepts_known_shapes(self):
        extract = OpenAICompatibleAdapter._extract_reported_model
        for key in ("model", "model_id", "modelId", "model_name"):
            with self.subTest(key=key):
                self.assertEqual(extract({key: "  m-1  "}), "m-1")
        self.assertIsNone(extract({}))
        self.assertIsNone(extract({"model": "   "}))
        self.assertIsNone(extract({"model": 7}))
        self.assertIsNone(extract(None))
        self.assertIsNone(extract([]))

    def test_prompt_tokens_helper_is_defensive(self):
        helper = OpenAICompatibleAdapter._prompt_tokens
        self.assertEqual(helper({"input_tokens": 10}), 10)
        self.assertEqual(helper({"prompt_tokens": 20}), 20)
        self.assertIsNone(helper({}))
        self.assertIsNone(helper(None))
        self.assertIsNone(helper({"input_tokens": True}))
        self.assertIsNone(helper({"input_tokens": "12"}))


class AuthenticationModeTests(unittest.TestCase):
    """A key-based Agent has no login state, and saying otherwise misleads."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CouncilStore(Path(self.temp.name) / "council.db")
        self.registry = RegistryService(self.store)
        self.registry.upsert_provider(
            "provider-a", display_name="Provider A", kind="remote_http"
        )
        self.registry.upsert_model(
            "model-a", provider_id="provider-a", display_name="Model A"
        )
        self.supervisor = SupervisorService(self.store, self.registry)

    def _agent(self, agent_id, adapter_type, config=None):
        self.registry.upsert_agent(
            agent_id,
            adapter_type=adapter_type,
            provider_id="provider-a",
            model_id="model-a",
            role="manager",
            config=config,
        )
        return self.supervisor._authentication_mode(agent_id)

    def test_api_key_agent_is_classified_as_api_key(self):
        self.assertEqual(
            self._agent(
                "key-agent",
                "openai_compatible",
                {"api_key_env": "SOME_KEY"},
            ),
            "api_key",
        )

    def test_agent_without_a_key_is_interactive_login(self):
        self.assertEqual(
            self._agent("cli-agent", "cli", {}),
            "interactive_login",
        )

    def test_unknown_agent_is_unknown(self):
        self.assertEqual(
            self.supervisor._authentication_mode("does-not-exist"),
            "unknown",
        )

    def _checked_role(self, agent_id, adapter_type, config=None):
        inspector_checks = {
            "process": {"status": "passed", "details": {}},
            "login": {"status": "unknown", "details": {}},
            "model": {"status": "passed", "details": {"model_id": "model-a"}},
            "permission": {"status": "passed", "details": {}},
            "version": {"status": "passed", "details": {}},
            "connection": {"status": "passed", "details": {}},
        }

        class Inspector:
            def inspect(self, binding):
                return inspector_checks

        supervisor = SupervisorService(
            self.store, self.registry, inspector=Inspector()
        )
        self._agent(agent_id, adapter_type, config)
        supervisor.configure_role(
            role_key="manager",
            agent_id=agent_id,
            model_id="model-a",
            launch_mode="spawn",
            transport="http",
            check_profile={"fixture": "local"},
        )
        return supervisor.check_role("manager")

    def test_login_is_not_applicable_for_an_api_key_agent(self):
        report = self._checked_role(
            "key-agent",
            "openai_compatible",
            {"api_key_env": "SOME_KEY"},
        )
        login = report["checks"]["login"]
        self.assertEqual(login["status"], "not_applicable")
        self.assertEqual(login["code"], "login_not_applicable_for_api_key")
        self.assertEqual(
            login["details"]["authentication_mode"],
            "api_key",
        )

    def test_login_check_is_left_alone_for_an_interactive_agent(self):
        report = self._checked_role("cli-agent", "cli", {})
        login = report["checks"]["login"]
        # An unknown login state for a login-based Agent stays a real fact to
        # resolve, not a not-applicable shortcut.
        self.assertNotEqual(login["status"], "not_applicable")
        self.assertNotEqual(
            login.get("code"),
            "login_not_applicable_for_api_key",
        )


class ConnectivityModeTests(unittest.TestCase):
    """A provider that refuses `/models` is still reachable."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CouncilStore(Path(self.temp.name) / "council.db")

    def _adapter(self, **extra):
        settings = {
            "base_url": "https://provider.example/v1",
            "model": "configured-model",
            "api_key_env": API_KEY_ENV,
            "api_style": "responses",
        }
        settings.update(extra)
        return OpenAICompatibleAdapter(
            AgentCard("api", "API", "API"), settings
        )

    def test_models_endpoint_mode_is_the_default(self):
        adapter = self._adapter()
        self.assertTrue(adapter.models_endpoint_available)
        with patch.dict(os.environ, {API_KEY_ENV: "test-value"}):
            with patch.object(
                adapter,
                "discover_models",
                return_value=[{"id": "m-1"}],
            ):
                result = adapter.connectivity_probe()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["details"]["transport"], "models_endpoint")

    def test_completion_endpoint_mode_avoids_the_models_endpoint(self):
        adapter = self._adapter(models_endpoint_available=False)
        with patch.dict(os.environ, {API_KEY_ENV: "test-value"}):
            with patch.object(
                adapter,
                "discover_models",
                side_effect=AssertionError("the models endpoint must not be used"),
            ):
                with patch.object(
                    adapter,
                    "_read_json",
                    return_value={"model": "served-by", "output": []},
                ):
                    result = adapter.connectivity_probe()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["details"]["transport"], "completion_endpoint")
        # The probe doubles as an identity observation.
        self.assertEqual(result["details"]["observed_model"], "served-by")
        self.assertEqual(
            result["details"]["configured_model"],
            "configured-model",
        )

    def test_completion_endpoint_mode_reports_a_failure_not_a_pass(self):
        adapter = self._adapter(models_endpoint_available=False)
        with patch.dict(os.environ, {API_KEY_ENV: "test-value"}):
            with patch.object(
                adapter,
                "_read_json",
                side_effect=RuntimeError("403"),
            ):
                result = adapter.connectivity_probe()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["details"]["error"], "RuntimeError")

    def test_missing_credential_fails_without_a_request(self):
        adapter = self._adapter(models_endpoint_available=False)
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                adapter,
                "_read_json",
                side_effect=AssertionError("no request may be sent"),
            ):
                result = adapter.connectivity_probe()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["details"]["error"], "api_key_not_configured")


if __name__ == "__main__":
    unittest.main()
