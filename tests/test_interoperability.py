from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import sys
import unittest

from model_council.adapters import build_adapters
from model_council.config import load_config
from model_council.interoperability import (
    InteroperabilityError,
    InteroperabilityService,
    MCPToolBroker,
)
from model_council.store import CouncilStore
from model_council.types import AgentRequest


class FakeA2AHandler(BaseHTTPRequestHandler):
    polls = 0

    def do_GET(self):
        if self.path == "/redirect-card":
            self.send_response(HTTPStatus.FOUND)
            self.send_header(
                "Location",
                "/.well-known/agent-card.json",
            )
            self.end_headers()
            return
        if self.path != "/.well-known/agent-card.json":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._json(
            {
                "name": "Local fake A2A Agent",
                "description": "Offline interoperability fixture",
                "url": f"http://127.0.0.1:{self.server.server_port}/a2a",
                "protocolVersion": "1.0",
                "preferredTransport": "JSONRPC",
                "skills": [],
            }
        )

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        method = payload["method"]
        if method == "message/send":
            result = {
                "kind": "task",
                "id": "task-a2a-1",
                "contextId": "context-a2a-1",
                "status": {"state": "working"},
            }
        elif method == "tasks/get":
            type(self).polls += 1
            result = {
                "kind": "task",
                "id": "task-a2a-1",
                "contextId": "context-a2a-1",
                "status": {
                    "state": "completed",
                    "message": {
                        "kind": "message",
                        "messageId": "message-a2a-1",
                        "role": "agent",
                        "parts": [
                            {
                                "kind": "text",
                                "text": "A2A task completed locally.",
                            }
                        ],
                    },
                },
            }
        else:
            result = {}
        self._json(
            {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": result,
            }
        )

    def log_message(self, format, *args):
        return

    def _json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FakeMCPHTTPHandler(BaseHTTPRequestHandler):
    initialized = False
    headers_valid = True

    def do_POST(self):
        if self.headers["Origin"] != "http://localhost":
            type(self).headers_valid = False
        if self.headers["MCP-Protocol-Version"] != "2025-11-25":
            type(self).headers_valid = False
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        method = payload["method"]
        if method == "initialize":
            self._json(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "fake-http-mcp", "version": "1.0"},
                    },
                },
                session_id="mcp-http-session-1",
            )
        elif method == "notifications/initialized":
            if self.headers["Mcp-Session-Id"] != "mcp-http-session-1":
                type(self).headers_valid = False
            type(self).initialized = True
            self.send_response(HTTPStatus.ACCEPTED)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif method == "tools/list":
            if not type(self).initialized:
                type(self).headers_valid = False
            if self.headers["Mcp-Session-Id"] != "mcp-http-session-1":
                type(self).headers_valid = False
            self._json(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "http-echo",
                                "inputSchema": {"type": "object"},
                            }
                        ]
                    },
                }
            )
        else:
            self.send_error(HTTPStatus.BAD_REQUEST)

    def log_message(self, format, *args):
        return

    def _json(self, payload, session_id=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        if session_id:
            self.send_header("Mcp-Session-Id", session_id)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class InteroperabilityTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parent.parent
        self.fake_codex = (
            self.repo / "tests" / "fixtures" / "fake_codex_app_server.py"
        )
        self.fake_mcp = self.repo / "tests" / "fixtures" / "fake_mcp_server.py"

    def _write_config(
        self,
        root: Path,
        *,
        a2a_endpoint: str = "http://127.0.0.1:1/a2a",
        invoke_enabled: bool = True,
    ) -> Path:
        path = root / "config.json"
        path.write_text(
            json.dumps(
                {
                    "project_name": "interop-test",
                    "state_dir": "runtime",
                    "manager": "manager",
                    "reviewer": "reviewer",
                    "agents": {
                        "manager": {
                            "type": "mock",
                            "role": "manager",
                        },
                        "codex_app": {
                            "type": "codex_app_server",
                            "role": "architect",
                            "command": [
                                sys.executable,
                                str(self.fake_codex),
                            ],
                            "sandbox": "read-only",
                            "approval_policy": "never",
                            "invoke_enabled": invoke_enabled,
                        },
                        "remote_a2a": {
                            "type": "a2a",
                            "role": "researcher",
                            "endpoint": a2a_endpoint,
                            "protocol_version": "1.0",
                            "invoke_enabled": invoke_enabled,
                            "poll_interval_seconds": 0.01,
                        },
                        "reviewer": {
                            "type": "mock",
                            "role": "reviewer",
                        },
                    },
                    "mcp_servers": {
                        "local-tools": {
                            "transport": "stdio",
                            "command": [
                                sys.executable,
                                str(self.fake_mcp),
                            ],
                            "protocol_version": "2025-11-25",
                            "invoke_enabled": invoke_enabled,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _request(agent: str) -> AgentRequest:
        return AgentRequest(
            run_id="run-interop",
            task_id=f"task-{agent}",
            mode="work",
            goal="Exercise offline interoperability",
            instruction="Return a local fixture result",
            sender="manager",
            recipient=agent,
        )

    def test_codex_app_server_persists_thread_and_rejects_approval(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = load_config(self._write_config(root))
            store = CouncilStore(config.state_dir / "council.db")
            adapters = build_adapters(config, store)
            first = adapters["codex_app"].invoke(self._request("codex_app"))
            second = adapters["codex_app"].invoke(self._request("codex_app"))

            self.assertIn("Persistent App Server result", first.content)
            self.assertEqual(
                first.metadata["thread_id"],
                "thread-persistent-1",
            )
            self.assertEqual(
                second.metadata["thread_id"],
                "thread-persistent-1",
            )
            service = InteroperabilityService(config, store)
            sessions = service.sessions(agent_id="codex_app")
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["status"], "active")
            endpoint = service.endpoint("agent:codex_app")
            self.assertEqual(
                endpoint["observations"]["initialize"]["userAgent"],
                "fake-codex-app-server",
            )
            approvals = service.approvals("rejected")
            self.assertEqual(len(approvals), 2)
            self.assertEqual(
                approvals[0]["action"],
                "item/commandExecution/requestApproval",
            )

    def test_a2a_task_and_agent_card_use_local_json_rpc(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeA2AHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as temp:
                root = Path(temp)
                endpoint = f"http://127.0.0.1:{server.server_port}/a2a"
                config = load_config(
                    self._write_config(root, a2a_endpoint=endpoint)
                )
                store = CouncilStore(config.state_dir / "council.db")
                adapter = build_adapters(config, store)["remote_a2a"]
                card = adapter.fetch_agent_card()
                response = adapter.invoke(self._request("remote_a2a"))

                self.assertEqual(card["protocolVersion"], "1.0")
                self.assertIn("completed locally", response.content)
                self.assertEqual(response.metadata["task_state"], "completed")
                adapter.agent_card_url = (
                    f"http://127.0.0.1:{server.server_port}/redirect-card"
                )
                with self.assertRaisesRegex(
                    InteroperabilityError,
                    "HTTP request failed",
                ):
                    adapter.fetch_agent_card()
                service = InteroperabilityService(config, store)
                sessions = service.sessions(agent_id="remote_a2a")
                self.assertEqual(sessions[0]["remote_session_id"], "context-a2a-1")
                self.assertEqual(sessions[0]["status"], "completed")
                endpoint_record = service.endpoint("agent:remote_a2a")
                self.assertEqual(
                    endpoint_record["observations"]["agent_card"]["name"],
                    "Local fake A2A Agent",
                )
                self.assertGreaterEqual(FakeA2AHandler.polls, 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_mcp_tool_call_requires_single_use_approval(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = load_config(self._write_config(root))
            store = CouncilStore(config.state_dir / "council.db")
            service = InteroperabilityService(config, store)
            broker = MCPToolBroker(service, config_dir=root)

            tools = broker.list_tools("local-tools")
            self.assertEqual(tools[0]["name"], "echo")
            endpoint = service.endpoint("mcp:local-tools")
            self.assertEqual(
                endpoint["observations"]["initialize"]["serverInfo"]["name"],
                "fake-mcp",
            )
            approval = broker.request_tool_call(
                "local-tools",
                "echo",
                {"text": "approved local result"},
            )
            with self.assertRaisesRegex(InteroperabilityError, "not approved"):
                broker.call_approved_tool(approval["id"])
            service.decide_approval(approval["id"], approve=True)
            result = broker.call_approved_tool(approval["id"])
            self.assertEqual(
                result["content"][0]["text"],
                "approved local result",
            )
            self.assertIsNotNone(service.approval(approval["id"])["consumed_at"])
            with self.assertRaisesRegex(InteroperabilityError, "unused"):
                broker.call_approved_tool(approval["id"])

            session = service.sessions(endpoint_id="mcp:local-tools")[0]
            service.record_event(
                session_id=session["id"],
                direction="outbound",
                method="large/test",
                payload={"text": "x" * 140_000},
            )
            large_event = service.events(session["id"], limit=1)[0]
            self.assertTrue(large_event["payload"]["truncated"])

    def test_mcp_streamable_http_initializes_before_listing_tools(self):
        FakeMCPHTTPHandler.initialized = False
        FakeMCPHTTPHandler.headers_valid = True
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeMCPHTTPHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as temp:
                root = Path(temp)
                config_data = json.loads(
                    self._write_config(root).read_text(encoding="utf-8")
                )
                config_data["mcp_servers"]["http-tools"] = {
                    "transport": "streamable_http",
                    "endpoint": f"http://127.0.0.1:{server.server_port}/mcp",
                    "protocol_version": "2025-11-25",
                    "invoke_enabled": True,
                }
                config_path = root / "http-config.json"
                config_path.write_text(
                    json.dumps(config_data),
                    encoding="utf-8",
                )
                config = load_config(config_path)
                store = CouncilStore(config.state_dir / "council.db")
                service = InteroperabilityService(config, store)
                broker = MCPToolBroker(service, config_dir=root)

                tools = broker.list_tools("http-tools")
                self.assertEqual(tools[0]["name"], "http-echo")
                self.assertTrue(FakeMCPHTTPHandler.initialized)
                self.assertTrue(FakeMCPHTTPHandler.headers_valid)
                session = service.sessions(endpoint_id="mcp:http-tools")[0]
                self.assertEqual(
                    session["remote_session_id"],
                    "mcp-http-session-1",
                )
                self.assertEqual(session["status"], "completed")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_external_invocation_and_plaintext_credentials_are_blocked(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = load_config(
                self._write_config(root, invoke_enabled=False)
            )
            store = CouncilStore(config.state_dir / "council.db")
            adapter = build_adapters(config, store)["codex_app"]
            with self.assertRaisesRegex(
                InteroperabilityError,
                "invoke_enabled=true",
            ):
                adapter.invoke(self._request("codex_app"))
            a2a = build_adapters(config, store)["remote_a2a"]
            with self.assertRaisesRegex(
                InteroperabilityError,
                "invoke_enabled=true",
            ):
                a2a.fetch_agent_card()

            data = json.loads(self._write_config(root).read_text(encoding="utf-8"))
            data["agents"]["remote_a2a"]["headers"] = {
                "author" + "ization": "not-allowed"
            }
            invalid_path = root / "invalid.json"
            invalid_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "environment variable"):
                load_config(invalid_path)

            insecure = json.loads(
                self._write_config(root).read_text(encoding="utf-8")
            )
            insecure["agents"]["remote_a2a"]["endpoint"] = (
                "http://agent.example.com/a2a"
            )
            insecure_path = root / "insecure.json"
            insecure_path.write_text(json.dumps(insecure), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must use HTTPS"):
                build_adapters(load_config(insecure_path))

            inline = json.loads(
                self._write_config(root).read_text(encoding="utf-8")
            )
            inline["agents"]["codex_app"]["command"].append(
                "--" + "token=not-allowed"
            )
            inline_path = root / "inline.json"
            inline_path.write_text(json.dumps(inline), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "inline credential"):
                load_config(inline_path)

            query = json.loads(
                self._write_config(root).read_text(encoding="utf-8")
            )
            query["agents"]["remote_a2a"]["endpoint"] = (
                "https://agent.example.com/a2a?credential=not-allowed"
            )
            query_path = root / "query.json"
            query_path.write_text(json.dumps(query), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "query parameters"):
                build_adapters(load_config(query_path))

            string_gate = json.loads(
                self._write_config(root).read_text(encoding="utf-8")
            )
            string_gate["agents"]["remote_a2a"]["invoke_enabled"] = "false"
            string_gate_path = root / "string-gate.json"
            string_gate_path.write_text(
                json.dumps(string_gate),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must be true or false"):
                load_config(string_gate_path)

            public_example = load_config(
                self.repo / "config.interop.example.json"
            )
            self.assertTrue(
                all(
                    not bool(item.get("invoke_enabled", False))
                    for item in public_example.agents.values()
                    if item.get("type") in {"codex_app_server", "a2a"}
                )
            )
            self.assertTrue(
                all(
                    not bool(item.get("invoke_enabled", False))
                    for item in public_example.mcp_servers.values()
                )
            )


if __name__ == "__main__":
    unittest.main()
