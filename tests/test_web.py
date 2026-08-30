from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import unittest

from model_council.config import load_config
from model_council.web import LocalSettingsApplication, _handler_for


class LocalSettingsWebTests(unittest.TestCase):
    def _app(self, root: Path) -> LocalSettingsApplication:
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "project_name": "web-test",
                    "state_dir": "runtime",
                    "manager": "manager",
                    "reviewer": "reviewer",
                    "providers": {
                        "mock-local": {
                            "kind": "mock",
                            "display_name": "Mock provider",
                        }
                    },
                    "models": {
                        "mock-model": {
                            "provider": "mock-local",
                            "display_name": "Mock model",
                        }
                    },
                    "agents": {
                        "manager": {
                            "type": "mock",
                            "provider": "mock-local",
                            "model": "mock-model",
                            "role": "manager",
                        },
                        "reviewer": {
                            "type": "mock",
                            "provider": "mock-local",
                            "model": "mock-model",
                            "role": "reviewer",
                        },
                    },
                    "settings": {"locale": "en-US"},
                    "mcp_servers": {
                        "local-disabled": {
                            "transport": "stdio",
                            "command": ["placeholder-mcp-command"],
                            "invoke_enabled": False,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return LocalSettingsApplication(load_config(config_path))

    def test_local_updates_are_user_owned_and_credentials_are_redacted(self):
        with TemporaryDirectory() as temp:
            app = self._app(Path(temp))
            app.update(
                "providers",
                "local-api",
                {
                    "id": "local-api",
                    "display_name": "Local API",
                    "kind": "openai_compatible",
                    "enabled": True,
                    "config": {
                        "base_url": "http://127.0.0.1/v1",
                        "api_key": "not-stored",
                    },
                },
            )
            app.update(
                "models",
                "local-model",
                {
                    "id": "local-model",
                    "provider_id": "local-api",
                    "display_name": "Local model",
                    "enabled": True,
                    "capabilities": ["analysis"],
                    "metadata": {},
                },
            )
            app.update(
                "agents",
                "analyst",
                {
                    "id": "analyst",
                    "adapter_type": "mock",
                    "provider_id": "local-api",
                    "model_id": "local-model",
                    "role": "analyst",
                    "description": "Local only",
                    "enabled": True,
                    "capabilities": ["analysis"],
                    "boundaries": ["no network"],
                    "config": {},
                },
            )
            app.update(
                "roles",
                "analysis_lead",
                {
                    "id": "analysis_lead",
                    "mode": "manual",
                    "agent_id": "analyst",
                    "model_id": "local-model",
                    "locked": True,
                    "constraints": {"required_capabilities": ["analysis"]},
                },
            )
            state = app.update(
                "settings",
                "locale",
                {"id": "locale", "value": "zh-CN"},
            )

            provider = next(
                item
                for item in state["registry"]["providers"]
                if item["id"] == "local-api"
            )
            self.assertEqual(provider["source"], "user")
            self.assertEqual(provider["config"]["api_key"], "[REDACTED]")
            self.assertEqual(
                state["registry"]["settings"]["locale"]["source"],
                "user",
            )
            role = next(
                item
                for item in state["registry"]["roles"]
                if item["role_key"] == "analysis_lead"
            )
            self.assertEqual(role["constraints"]["required_capabilities"], ["analysis"])

    def test_budget_updates_and_state_are_local_observations(self):
        with TemporaryDirectory() as temp:
            app = self._app(Path(temp))
            state = app.update(
                "budgets",
                "local-budget",
                {
                    "id": "local-budget",
                    "scope": "project",
                    "scope_key": "web-test",
                    "metric": "tokens",
                    "warning": 10,
                    "hard": None,
                    "currency": None,
                },
            )
            self.assertEqual(state["project"]["external_calls"], "none")
            capability = next(
                item
                for item in state["adapter_capabilities"]
                if item["agent_id"] == "manager"
            )
            self.assertFalse(capability["billing"]["provider_balance"])
            policy = next(
                item
                for item in state["ledger"]["budgets"]
                if item["id"] == "local-budget"
            )
            self.assertEqual(policy["source"], "user")
            self.assertEqual(policy["warning_limit"], "10")

    def test_http_interface_is_loopback_and_uses_json_updates(self):
        with TemporaryDirectory() as temp:
            app = self._app(Path(temp))
            token = "local-test-token"
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                _handler_for(app, token),
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address[:2]
                with urlopen(f"http://{host}:{port}/") as response:
                    page = response.read().decode("utf-8")
                    self.assertIn("Model Council local settings", page)
                    self.assertIn(
                        "default-src 'self'",
                        response.headers["Content-Security-Policy"],
                    )
                request = Request(
                    f"http://{host}:{port}/api/settings/locale",
                    data=json.dumps(
                        {"id": "locale", "value": "zh-CN"}
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="PUT",
                )
                with self.assertRaises(HTTPError) as missing_token:
                    urlopen(request)
                self.assertEqual(missing_token.exception.code, 403)
                missing_token.exception.close()
                request.add_header("X-Model-Council-Token", token)
                with urlopen(request) as response:
                    state = json.loads(response.read().decode("utf-8"))
                self.assertEqual(
                    state["registry"]["settings"]["locale"]["value"],
                    "zh-CN",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_cross_origin_write_and_invalid_list_values_are_rejected(self):
        with TemporaryDirectory() as temp:
            app = self._app(Path(temp))
            with self.assertRaisesRegex(ValueError, "non-empty strings"):
                app.update(
                    "models",
                    "bad-model",
                    {
                        "id": "bad-model",
                        "provider_id": "mock-local",
                        "display_name": "Bad model",
                        "capabilities": ["analysis", ""],
                    },
                )

            token = "local-test-token"
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                _handler_for(app, token),
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address[:2]
                request = Request(
                    f"http://{host}:{port}/api/settings/locale",
                    data=json.dumps(
                        {"id": "locale", "value": "zh-CN"}
                    ).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Model-Council-Token": token,
                        "Origin": "https://example.invalid",
                    },
                    method="PUT",
                )
                with self.assertRaises(HTTPError) as cross_origin:
                    urlopen(request)
                self.assertEqual(cross_origin.exception.code, 403)
                cross_origin.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_local_interface_can_decide_interoperability_approval(self):
        with TemporaryDirectory() as temp:
            app = self._app(Path(temp))
            approval = app.interoperability.request_approval(
                endpoint_id="mcp:local-disabled",
                action="mcp.tools.call",
                resource="local-test",
                arguments={"value": "safe"},
            )
            token = "local-test-token"
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                _handler_for(app, token),
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address[:2]
                request = Request(
                    (
                        f"http://{host}:{port}/api/interop-approvals/"
                        f"{approval['id']}"
                    ),
                    data=json.dumps(
                        {"id": approval["id"], "decision": "approve"}
                    ).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Model-Council-Token": token,
                    },
                    method="PUT",
                )
                with urlopen(request) as response:
                    state = json.loads(response.read().decode("utf-8"))
                decided = next(
                    item
                    for item in state["interoperability"]["approvals"]
                    if item["id"] == approval["id"]
                )
                self.assertEqual(decided["status"], "approved")
                self.assertIsNotNone(decided["decided_at"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
