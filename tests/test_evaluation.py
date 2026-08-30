from __future__ import annotations

import json
import os
from contextlib import redirect_stdout
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from model_council.config import load_config
from model_council.cli import main
from model_council.evaluation import (
    BOARD_11_API_KEY_ENV,
    BOARD_11_EXPECTED_TEXT,
    BOARD_11_MODEL,
    EvaluationError,
    EvaluationService,
)


class FakeResponsesHandler(BaseHTTPRequestHandler):
    response_text = BOARD_11_EXPECTED_TEXT
    request_payload = None
    authorization = None
    redirect_location = None
    request_count = 0

    def do_POST(self):
        type(self).request_count += 1
        if self.path != "/responses":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if type(self).redirect_location:
            self.send_response(HTTPStatus.TEMPORARY_REDIRECT)
            self.send_header("Location", type(self).redirect_location)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        length = int(self.headers["Content-Length"])
        type(self).request_payload = json.loads(
            self.rfile.read(length).decode("utf-8")
        )
        type(self).authorization = self.headers.get("Authorization")
        body = json.dumps(
            {
                "output_text": type(self).response_text,
                "usage": {
                    "input_tokens": 20,
                    "output_tokens": 8,
                    "total_tokens": 28,
                },
            }
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class EvaluationTests(unittest.TestCase):
    def test_public_example_freezes_the_deepseek_candidate(self):
        root = Path(__file__).resolve().parent.parent
        config = load_config(root / "config.evaluation.example.json")
        settings = config.agents["deepseek_evaluator"]
        self.assertEqual(settings["base_url"], "https://api.deepseek.com")
        self.assertEqual(settings["model"], BOARD_11_MODEL)
        self.assertEqual(settings["api_key_env"], BOARD_11_API_KEY_ENV)
        self.assertEqual(settings["api_style"], "responses")
        self.assertEqual(settings["max_response_bytes"], 16384)
        self.assertFalse(settings["invoke_enabled"])

    def _write_config(
        self,
        root: Path,
        *,
        endpoint: str,
        invoke_enabled: bool,
        plaintext_key: str | None = None,
    ) -> Path:
        candidate = {
            "type": "openai_compatible",
            "provider": "deepseek-api",
            "model": BOARD_11_MODEL,
            "role": "synthetic_evaluator",
            "description": "Evaluate one fixed synthetic task.",
            "capabilities": ["objective_evaluation"],
            "boundaries": [
                "synthetic context only",
                "zero files",
                "zero Artifacts",
                "one approved invocation only",
            ],
            "base_url": endpoint,
            "api_key_env": BOARD_11_API_KEY_ENV,
            "api_style": "responses",
            "timeout_seconds": 30,
            "max_response_bytes": 16384,
            "outbound_context": {
                "source": "synthetic",
                "allowed_sources": ["synthetic"],
                "max_files": 0,
                "max_total_bytes": 4096,
                "max_artifacts": 0,
                "max_artifact_bytes": 0,
            },
            "invoke_enabled": invoke_enabled,
        }
        if plaintext_key is not None:
            candidate["api_key"] = plaintext_key
        path = root / "config.json"
        path.write_text(
            json.dumps(
                {
                    "project_name": "board-11-test",
                    "state_dir": "runtime",
                    "manager": "manager",
                    "reviewer": "reviewer",
                    "providers": {
                        "mock-local": {
                            "kind": "mock",
                            "display_name": "Local mock",
                        },
                        "deepseek-api": {
                            "kind": "openai_compatible",
                            "display_name": "DeepSeek API",
                        },
                    },
                    "models": {
                        "mock-general": {
                            "provider": "mock-local",
                        },
                        BOARD_11_MODEL: {
                            "provider": "deepseek-api",
                            "capabilities": ["objective_evaluation"],
                        },
                    },
                    "agents": {
                        "manager": {
                            "type": "mock",
                            "provider": "mock-local",
                            "model": "mock-general",
                            "role": "manager",
                        },
                        "deepseek_evaluator": candidate,
                        "reviewer": {
                            "type": "mock",
                            "provider": "mock-local",
                            "model": "mock-general",
                            "role": "reviewer",
                        },
                    },
                    "role_assignments": {
                        "objective_evaluator": {
                            "mode": "manual",
                            "agent": "deepseek_evaluator",
                            "model": BOARD_11_MODEL,
                            "locked": True,
                        }
                    },
                    "settings": {
                        "usage_estimation_enabled": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_prepare_freezes_zero_file_scope_and_requires_invoke_gate(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = load_config(
                self._write_config(
                    root,
                    endpoint="http://127.0.0.1:1",
                    invoke_enabled=False,
                )
            )
            service = EvaluationService(config)
            evaluation = service.prepare("deepseek_evaluator")
            manifest = evaluation["case"]["outbound_context"]

            self.assertEqual(evaluation["status"], "prepared")
            self.assertEqual(
                evaluation["specification"]["expected_bytes"],
                len(BOARD_11_EXPECTED_TEXT.encode("utf-8")),
            )
            self.assertEqual(manifest["status"], "pending")
            self.assertEqual(manifest["manifest"]["source"], "synthetic")
            self.assertEqual(manifest["manifest"]["files"], [])
            self.assertEqual(manifest["manifest"]["artifacts"], [])
            self.assertEqual(manifest["manifest"]["limits"]["max_files"], 0)
            self.assertEqual(manifest["manifest"]["limits"]["max_artifacts"], 0)

            service.contexts.decide(
                manifest["id"],
                approve=True,
                confirmation=manifest["approval_sha256"],
            )
            with self.assertRaisesRegex(
                EvaluationError,
                "invoke_enabled=true",
            ):
                service.run(evaluation["id"], manifest["id"])
            self.assertEqual(
                service.contexts.manifest(manifest["id"])["status"],
                "approved",
            )

    def test_loopback_responses_candidate_passes_objective_evaluation(self):
        FakeResponsesHandler.response_text = BOARD_11_EXPECTED_TEXT
        FakeResponsesHandler.request_payload = None
        FakeResponsesHandler.authorization = None
        FakeResponsesHandler.redirect_location = None
        FakeResponsesHandler.request_count = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeResponsesHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as temp:
                root = Path(temp)
                endpoint = f"http://127.0.0.1:{server.server_port}"
                config = load_config(
                    self._write_config(
                        root,
                        endpoint=endpoint,
                        invoke_enabled=True,
                    )
                )
                service = EvaluationService(config)
                evaluation = service.prepare("deepseek_evaluator")
                manifest = evaluation["case"]["outbound_context"]
                service.contexts.decide(
                    manifest["id"],
                    approve=True,
                    confirmation=manifest["approval_sha256"],
                )
                with patch.dict(
                    os.environ,
                    {BOARD_11_API_KEY_ENV: "local-test-only"},
                ):
                    result = service.run(evaluation["id"], manifest["id"])

                self.assertEqual(result["status"], "passed")
                self.assertTrue(all(result["case"]["assertions"].values()))
                self.assertEqual(
                    result["case"]["response_bytes"],
                    len(BOARD_11_EXPECTED_TEXT.encode("utf-8")),
                )
                self.assertEqual(
                    result["case"]["outbound_context"]["status"],
                    "consumed",
                )
                self.assertEqual(
                    FakeResponsesHandler.request_payload["model"],
                    BOARD_11_MODEL,
                )
                self.assertIn(
                    BOARD_11_EXPECTED_TEXT,
                    FakeResponsesHandler.request_payload["input"],
                )
                self.assertEqual(
                    FakeResponsesHandler.authorization,
                    "Bearer local-test-only",
                )
                with service.store.connect() as conn:
                    case_row = conn.execute(
                        "SELECT * FROM evaluation_cases WHERE evaluation_id = ?",
                        (evaluation["id"],),
                    ).fetchone()
                    usage_row = conn.execute(
                        "SELECT * FROM usage_events WHERE id = ?",
                        (case_row["ledger_event_id"],),
                    ).fetchone()
                self.assertNotIn(
                    BOARD_11_EXPECTED_TEXT,
                    json.dumps(dict(case_row), ensure_ascii=False),
                )
                self.assertEqual(usage_row["token_source"], "provider_reported")
                self.assertEqual(usage_row["total_tokens"], 28)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_wrong_response_records_failed_hash_without_retry(self):
        FakeResponsesHandler.response_text = f"{BOARD_11_EXPECTED_TEXT}\n"
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeResponsesHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as temp:
                root = Path(temp)
                config = load_config(
                    self._write_config(
                        root,
                        endpoint=f"http://127.0.0.1:{server.server_port}",
                        invoke_enabled=True,
                    )
                )
                service = EvaluationService(config)
                evaluation = service.prepare("deepseek_evaluator")
                manifest = evaluation["case"]["outbound_context"]
                service.contexts.decide(
                    manifest["id"],
                    approve=True,
                    confirmation=manifest["approval_sha256"],
                )
                with patch.dict(
                    os.environ,
                    {BOARD_11_API_KEY_ENV: "local-test-only"},
                ):
                    result = service.run(evaluation["id"], manifest["id"])

                self.assertEqual(result["status"], "failed")
                self.assertFalse(result["case"]["assertions"]["exact_text"])
                self.assertEqual(
                    result["case"]["failure_class"],
                    "objective_assertion_failed",
                )
                with service.store.connect() as conn:
                    count = conn.execute(
                        """
                        SELECT COUNT(*) AS count FROM usage_events
                        WHERE run_id = ? AND agent_id = 'deepseek_evaluator'
                        """,
                        (result["run_id"],),
                    ).fetchone()["count"]
                self.assertEqual(count, 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_response_byte_limit_fails_without_retry(self):
        FakeResponsesHandler.response_text = "x" * 20000
        FakeResponsesHandler.redirect_location = None
        FakeResponsesHandler.request_count = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeResponsesHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as temp:
                root = Path(temp)
                config = load_config(
                    self._write_config(
                        root,
                        endpoint=f"http://127.0.0.1:{server.server_port}",
                        invoke_enabled=True,
                    )
                )
                service = EvaluationService(config)
                evaluation = service.prepare("deepseek_evaluator")
                manifest = evaluation["case"]["outbound_context"]
                service.contexts.decide(
                    manifest["id"],
                    approve=True,
                    confirmation=manifest["approval_sha256"],
                )
                with patch.dict(
                    os.environ,
                    {BOARD_11_API_KEY_ENV: "local-test-only"},
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "exceeded 16384 bytes",
                    ):
                        service.run(evaluation["id"], manifest["id"])
                failed = service.snapshot(evaluation["id"])
                self.assertEqual(failed["status"], "failed")
                self.assertEqual(
                    failed["case"]["failure_class"],
                    "RuntimeError",
                )
                with service.store.connect() as conn:
                    count = conn.execute(
                        """
                        SELECT COUNT(*) AS count FROM usage_events
                        WHERE run_id = ? AND agent_id = 'deepseek_evaluator'
                        """,
                        (failed["run_id"],),
                    ).fetchone()["count"]
                self.assertEqual(count, 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_redirect_is_rejected_before_a_second_request(self):
        FakeResponsesHandler.response_text = BOARD_11_EXPECTED_TEXT
        FakeResponsesHandler.redirect_location = "/redirected"
        FakeResponsesHandler.request_count = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeResponsesHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as temp:
                root = Path(temp)
                config = load_config(
                    self._write_config(
                        root,
                        endpoint=f"http://127.0.0.1:{server.server_port}",
                        invoke_enabled=True,
                    )
                )
                service = EvaluationService(config)
                evaluation = service.prepare("deepseek_evaluator")
                manifest = evaluation["case"]["outbound_context"]
                service.contexts.decide(
                    manifest["id"],
                    approve=True,
                    confirmation=manifest["approval_sha256"],
                )
                with patch.dict(
                    os.environ,
                    {BOARD_11_API_KEY_ENV: "local-test-only"},
                ):
                    with self.assertRaisesRegex(RuntimeError, "HTTP 307"):
                        service.run(evaluation["id"], manifest["id"])
                self.assertEqual(FakeResponsesHandler.request_count, 1)
                self.assertEqual(
                    service.snapshot(evaluation["id"])["status"],
                    "failed",
                )
        finally:
            FakeResponsesHandler.redirect_location = None
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_candidate_rejects_plaintext_key_and_unfrozen_endpoint(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(
                ValueError,
                "environment variable names",
            ):
                load_config(
                    self._write_config(
                        root,
                        endpoint="https://api.deepseek.com",
                        invoke_enabled=False,
                        plaintext_key="must-not-be-accepted",
                    )
                )

            config = load_config(
                self._write_config(
                    root,
                    endpoint="https://provider.example/v1",
                    invoke_enabled=False,
                )
            )
            with self.assertRaisesRegex(
                EvaluationError,
                "candidate endpoint",
            ):
                EvaluationService(config).prepare("deepseek_evaluator")
            with self.assertRaisesRegex(
                ValueError,
                "HTTPS for non-loopback",
            ):
                load_config(
                    self._write_config(
                        root,
                        endpoint="http://provider.example/v1",
                        invoke_enabled=False,
                    )
                )

    def test_cli_prepares_and_displays_exact_local_prompt(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = self._write_config(
                root,
                endpoint="http://127.0.0.1:1",
                invoke_enabled=False,
            )
            output = StringIO()
            with redirect_stdout(output):
                main(
                    [
                        "evaluation",
                        "prepare",
                        "deepseek_evaluator",
                        "--config",
                        str(config_path),
                    ]
                )
            prepared = json.loads(output.getvalue())
            output = StringIO()
            with redirect_stdout(output):
                main(
                    [
                        "evaluation",
                        "context",
                        prepared["id"],
                        "--show-prompt",
                        "--config",
                        str(config_path),
                    ]
                )
            context = json.loads(output.getvalue())
            self.assertIn(BOARD_11_EXPECTED_TEXT, context["prompt"])
            self.assertIn("Role: synthetic_evaluator", context["prompt"])
            self.assertNotIn("\ufffd", context["prompt"])
            self.assertEqual(context["status"], "pending")
            self.assertEqual(
                context["approval_sha256"],
                context["manifest"]["scope_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
