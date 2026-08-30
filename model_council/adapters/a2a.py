from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from .base import AgentAdapter
from ..interoperability import (
    InteroperabilityError,
    InteroperabilityService,
    validate_remote_url,
)
from ..types import (
    AgentRequest,
    AgentResponse,
    AuthenticationStatus,
    ConnectivityStatus,
    PermissionStatus,
)


TERMINAL_TASK_STATES = {"completed", "failed", "canceled", "rejected"}


class A2AAdapter(AgentAdapter):
    """A2A v1.0 JSON-RPC client with durable session and event evidence."""

    def __init__(
        self,
        card,
        settings: dict[str, Any],
        interoperability: InteroperabilityService,
    ):
        super().__init__(card)
        self.settings = settings
        self.interoperability = interoperability
        self.endpoint_id = f"agent:{card.name}"
        self.endpoint = interoperability.endpoint(self.endpoint_id)
        self.url = validate_remote_url(str(settings["endpoint"]))
        self.timeout_seconds = int(settings.get("timeout_seconds", 60))
        self.poll_interval_seconds = float(
            settings.get("poll_interval_seconds", 0.2)
        )
        self.protocol_version = str(settings.get("protocol_version", "1.0"))
        self.agent_card_url = str(
            settings.get("agent_card_url") or self._default_card_url()
        )

    def invoke(self, request: AgentRequest) -> AgentResponse:
        self.interoperability.require_invocation_enabled(self.endpoint)
        session = self.interoperability.create_session(
            endpoint_id=self.endpoint_id,
            agent_id=self.card.name,
            protocol="a2a",
            metadata={"run_id": request.run_id, "task_id": request.task_id},
        )
        try:
            result = self._rpc(
                session["id"],
                "message/send",
                {
                    "message": {
                        "kind": "message",
                        "messageId": str(uuid4()),
                        "role": "user",
                        "parts": [
                            {
                                "kind": "text",
                                "text": self.render_prompt(request),
                            }
                        ],
                    },
                    "configuration": {
                        "acceptedOutputModes": ["text/plain", "text/markdown"],
                    },
                },
            )
            result = self._await_terminal(session["id"], result)
            content = self._extract_text(result)
            if not content:
                raise InteroperabilityError("A2A response contained no text")
            remote_id = _optional_text(
                result.get("contextId") or result.get("id")
            )
            self.interoperability.update_session(
                session["id"],
                remote_session_id=remote_id,
                status="completed",
                metadata={
                    "result_kind": result.get("kind"),
                    "task_state": _task_state(result),
                },
            )
            return AgentResponse(
                content=content,
                metadata={
                    "adapter": type(self).__name__,
                    "protocol": "a2a",
                    "protocol_version": self.protocol_version,
                    "session_id": session["id"],
                    "remote_session_id": remote_id,
                    "task_state": _task_state(result),
                },
            )
        except Exception as exc:
            self.interoperability.update_session(
                session["id"],
                status="failed",
                metadata={"error": type(exc).__name__},
            )
            raise

    def diagnose(self) -> dict[str, Any]:
        return {
            "ok": True,
            "adapter": type(self).__name__,
            "agent": self.card.name,
            "endpoint": self.url,
            "protocol_version": self.protocol_version,
            "invoke_enabled": bool(self.settings.get("invoke_enabled", False)),
            "auth_env": self.endpoint.get("auth_env"),
            "auth_present": bool(
                self.endpoint.get("auth_env")
                and os.environ.get(str(self.endpoint["auth_env"]))
            ),
        }

    def discovery_capabilities(self) -> dict[str, bool]:
        return {
            "executable_check": False,
            "authentication_check": True,
            "permission_check": True,
            "model_discovery": False,
            "connectivity_test": True,
            "agent_card": True,
        }

    def check_authentication(self) -> dict[str, Any]:
        auth_env = self.endpoint.get("auth_env")
        if not auth_env:
            return {
                "status": AuthenticationStatus.NOT_APPLICABLE.value,
                "details": {"scheme": "none"},
            }
        present = bool(os.environ.get(str(auth_env)))
        return {
            "status": (
                AuthenticationStatus.CONFIGURED.value
                if present
                else AuthenticationStatus.MISSING.value
            ),
            "details": {"scheme": "bearer", "auth_env": auth_env},
        }

    def check_permissions(self) -> dict[str, Any]:
        return {
            "status": PermissionStatus.UNKNOWN.value,
            "details": {
                "reason": "remote Agent permissions are declared by Agent Card"
            },
        }

    def connectivity_probe(self) -> dict[str, Any]:
        try:
            card = self.fetch_agent_card()
        except Exception as exc:
            return {
                "status": ConnectivityStatus.FAILED.value,
                "details": {"error": type(exc).__name__},
            }
        return {
            "status": ConnectivityStatus.PASSED.value,
            "details": {
                "agent_card": True,
                "name": card.get("name"),
                "protocol_version": card.get("protocolVersion"),
            },
        }

    def fetch_agent_card(self) -> dict[str, Any]:
        self.interoperability.require_invocation_enabled(self.endpoint)
        url = validate_remote_url(self.agent_card_url)
        headers = {"A2A-Version": self.protocol_version}
        self._add_auth(headers)
        request = Request(url, method="GET", headers=headers)
        card = self._read_json(request)
        self._validate_agent_card(card)
        self.interoperability.record_endpoint_observation(
            self.endpoint_id,
            "agent_card",
            card,
        )
        return card

    def _await_terminal(
        self,
        session_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        if result.get("kind") != "task":
            return result
        task_id = _optional_text(result.get("id"))
        if not task_id:
            raise InteroperabilityError("A2A Task response lacks id")
        deadline = time.monotonic() + self.timeout_seconds
        while _task_state(result) not in TERMINAL_TASK_STATES:
            if _task_state(result) in {"input-required", "auth-required"}:
                raise InteroperabilityError(
                    f"A2A Task requires interaction: {_task_state(result)}"
                )
            if time.monotonic() >= deadline:
                raise InteroperabilityError("timed out waiting for A2A Task")
            time.sleep(max(0.01, self.poll_interval_seconds))
            result = self._rpc(
                session_id,
                "tasks/get",
                {"id": task_id},
            )
        if _task_state(result) != "completed":
            raise InteroperabilityError(
                f"A2A Task ended in {_task_state(result)!r}"
            )
        return result

    def _rpc(
        self,
        session_id: str,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        request_id = str(uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        headers = {
            "Content-Type": "application/json",
            "A2A-Version": self.protocol_version,
        }
        self._add_auth(headers)
        self.interoperability.record_event(
            session_id=session_id,
            direction="outbound",
            method=method,
            request_id=request_id,
            payload=payload,
        )
        request = Request(
            self.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        body = self._read_json(request)
        self.interoperability.record_event(
            session_id=session_id,
            direction="inbound",
            method=str(body.get("method", "response")),
            request_id=body.get("id"),
            payload=body,
        )
        if body.get("id") != request_id:
            raise InteroperabilityError("A2A response id did not match request")
        if "error" in body:
            raise InteroperabilityError(f"A2A {method} failed: {body['error']}")
        result = body.get("result")
        if not isinstance(result, dict):
            raise InteroperabilityError("A2A result must be an object")
        return result

    def _read_json(self, request: Request) -> dict[str, Any]:
        try:
            with _NO_REDIRECT_OPENER.open(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                exc.read()
            finally:
                exc.close()
            raise InteroperabilityError(
                f"A2A HTTP request failed with {exc.code}"
            ) from exc
        except URLError as exc:
            raise InteroperabilityError(
                f"A2A endpoint is unreachable: {type(exc.reason).__name__}"
            ) from exc
        if not isinstance(data, dict):
            raise InteroperabilityError("A2A response must be a JSON object")
        return data

    def _add_auth(self, headers: dict[str, str]) -> None:
        auth_env = self.endpoint.get("auth_env")
        if not auth_env:
            return
        token = os.environ.get(str(auth_env))
        if not token:
            raise InteroperabilityError(
                f"environment variable {auth_env!r} is not configured"
            )
        headers["Authorization"] = f"Bearer {token}"

    def _default_card_url(self) -> str:
        parsed = urlsplit(self.url)
        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                "/.well-known/agent-card.json",
                "",
                "",
            )
        )

    @staticmethod
    def _validate_agent_card(card: dict[str, Any]) -> None:
        for key in ("name", "url", "protocolVersion"):
            if not isinstance(card.get(key), str) or not card[key].strip():
                raise InteroperabilityError(
                    f"A2A Agent Card requires non-empty {key}"
                )
        validate_remote_url(card["url"])
        if not isinstance(card.get("skills", []), list):
            raise InteroperabilityError("A2A Agent Card skills must be a list")

    @staticmethod
    def _extract_text(result: dict[str, Any]) -> str:
        texts: list[str] = []

        def add_parts(parts: Any) -> None:
            if not isinstance(parts, list):
                return
            for part in parts:
                if not isinstance(part, dict):
                    continue
                if part.get("kind") == "text" and isinstance(part.get("text"), str):
                    texts.append(part["text"].strip())

        add_parts(result.get("parts"))
        status = result.get("status")
        if isinstance(status, dict):
            message = status.get("message")
            if isinstance(message, dict):
                add_parts(message.get("parts"))
        artifacts = result.get("artifacts")
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if isinstance(artifact, dict):
                    add_parts(artifact.get("parts"))
        return "\n".join(text for text in texts if text).strip()


def _task_state(result: dict[str, Any]) -> str | None:
    status = result.get("status")
    if not isinstance(status, dict):
        return None
    value = status.get("state")
    return str(value) if value is not None else None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler())
