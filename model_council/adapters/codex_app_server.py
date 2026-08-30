from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .base import AgentAdapter
from ..interoperability import (
    InteroperabilityError,
    InteroperabilityService,
    JsonLineProcess,
)
from ..outbound_context import (
    OutboundContextApprovalRequired,
    OutboundContextPolicy,
    OutboundContextService,
)
from ..types import (
    AgentRequest,
    AgentResponse,
    AuthenticationStatus,
    ConnectivityStatus,
    ExecutableStatus,
    PermissionStatus,
)


APPROVAL_METHODS = {
    "item/commandExecution/requestApproval",
    "item/fileChange/requestApproval",
}


class CodexAppServerAdapter(AgentAdapter):
    """Persistent Codex Thread adapter over the official app-server protocol."""

    def __init__(
        self,
        card,
        settings: dict[str, Any],
        config_dir: Path,
        interoperability: InteroperabilityService,
    ):
        super().__init__(card)
        self.settings = settings
        self.config_dir = config_dir
        self.interoperability = interoperability
        self.endpoint_id = f"agent:{card.name}"
        self.endpoint = interoperability.endpoint(self.endpoint_id)
        self.command = list(settings["command"])
        self.timeout_seconds = int(settings.get("timeout_seconds", 600))
        cwd_value = settings.get("cwd")
        if cwd_value:
            cwd = Path(str(cwd_value))
            self.cwd = (cwd if cwd.is_absolute() else config_dir / cwd).resolve()
        else:
            self.cwd = config_dir
        self.sandbox = str(settings.get("sandbox", "read-only"))
        if self.sandbox not in {"read-only", "workspace-write"}:
            raise ValueError(
                "Codex App Server sandbox must be read-only or workspace-write"
            )
        self.approval_policy = str(settings.get("approval_policy", "never"))
        if self.approval_policy not in {"never", "on-request"}:
            raise ValueError(
                "Codex App Server approval_policy must be never or on-request"
            )
        self.model = _optional_text(settings.get("model"))
        self.outbound_policy = OutboundContextPolicy.from_settings(
            dict(settings["outbound_context"])
        )
        self.outbound_source = str(settings["outbound_context"]["source"])
        self.outbound_context = OutboundContextService(interoperability.store)

    def invoke(self, request: AgentRequest) -> AgentResponse:
        self.interoperability.require_invocation_enabled(self.endpoint)
        prompt = self.render_outbound_prompt(request)
        manifest_id = _optional_text(
            request.metadata.get("outbound_context_manifest_id")
        )
        if manifest_id:
            manifest = self.outbound_context.require_approved(
                manifest_id=manifest_id,
                endpoint_id=self.endpoint_id,
                prompt=prompt,
            )
        else:
            manifest = self.outbound_context.prepare(
                endpoint_id=self.endpoint_id,
                agent_id=self.card.name,
                request=request,
                prompt=prompt,
                source=self.outbound_source,
                policy=self.outbound_policy,
            )
            if manifest["status"] == "blocked":
                raise InteroperabilityError(manifest["reason"])
            raise OutboundContextApprovalRequired(manifest["id"])
        session = self.interoperability.active_session(
            endpoint_id=self.endpoint_id,
            agent_id=self.card.name,
        )
        if session is None:
            session = self.interoperability.create_session(
                endpoint_id=self.endpoint_id,
                agent_id=self.card.name,
                protocol="codex_app_server",
                metadata={"run_id": request.run_id},
            )
        transport = JsonLineProcess(
            self.command,
            cwd=self.cwd,
            timeout_seconds=self.timeout_seconds,
        )
        try:
            initialize_result = self._exchange(
                transport,
                session["id"],
                1,
                "initialize",
                {
                    "clientInfo": {
                        "name": "model-council",
                        "version": "0.1.0",
                    }
                },
            )
            self.interoperability.record_endpoint_observation(
                self.endpoint_id,
                "initialize",
                initialize_result,
            )
            initialized = {"method": "initialized", "params": {}}
            transport.send(initialized)
            self.interoperability.record_event(
                session_id=session["id"],
                direction="outbound",
                method="initialized",
                payload=initialized,
            )

            thread_id = session.get("remote_session_id")
            if thread_id:
                result = self._exchange(
                    transport,
                    session["id"],
                    2,
                    "thread/resume",
                    {"threadId": thread_id},
                )
            else:
                params: dict[str, Any] = {
                    "cwd": str(self.cwd),
                    "approvalPolicy": self.approval_policy,
                    "sandbox": self.sandbox,
                    "experimentalRawEvents": False,
                    "persistExtendedHistory": True,
                }
                if self.model:
                    params["model"] = self.model
                result = self._exchange(
                    transport,
                    session["id"],
                    2,
                    "thread/start",
                    params,
                )
                thread_id = self._thread_id(result)
                self.interoperability.update_session(
                    session["id"],
                    remote_session_id=thread_id,
                )

            turn_params = {
                "threadId": thread_id,
                "input": [
                    {
                        "type": "text",
                        "text": prompt,
                    }
                ],
            }
            turn_result = self._exchange(
                transport,
                session["id"],
                3,
                "turn/start",
                turn_params,
                audit_params={
                    "threadId": thread_id,
                    "input": [
                        {
                            "type": "text",
                            "outbound_context_manifest_id": manifest["id"],
                            "prompt_sha256": manifest["prompt_sha256"],
                            "bytes": len(prompt.encode("utf-8")),
                        }
                    ],
                },
            )
            turn_id = self._turn_id(turn_result)
            content, turn = self._read_turn(
                transport,
                session_id=session["id"],
                turn_id=turn_id,
            )
            if not content:
                raise InteroperabilityError(
                    "Codex App Server returned no agent message"
                )
            usage = turn.get("usage") if isinstance(turn, dict) else None
            metadata: dict[str, Any] = {
                "adapter": type(self).__name__,
                "protocol": "codex_app_server",
                "session_id": session["id"],
                "thread_id": thread_id,
                "turn_id": turn_id,
                "sandbox": self.sandbox,
                "approval_policy": self.approval_policy,
                "outbound_context_manifest_id": manifest["id"],
                "outbound_context_sha256": manifest["prompt_sha256"],
                "stderr_tail": transport.stderr_tail(),
            }
            if isinstance(usage, dict):
                metadata["usage"] = usage
                metadata["usage_source"] = "provider_reported"
            self.interoperability.update_session(
                session["id"],
                status="active",
                metadata={
                    "last_turn_id": turn_id,
                    "last_run_id": request.run_id,
                },
            )
            return AgentResponse(content=content, metadata=metadata)
        except Exception as exc:
            self.interoperability.update_session(
                session["id"],
                status="failed",
                metadata={
                    "error": type(exc).__name__,
                    "stderr_tail": transport.stderr_tail(),
                },
            )
            raise
        finally:
            transport.close()

    def diagnose(self) -> dict[str, Any]:
        executable = self.command[0]
        resolved = shutil.which(executable)
        if not resolved and Path(executable).is_file():
            resolved = str(Path(executable).resolve())
        return {
            "ok": bool(resolved) and self.cwd.is_dir(),
            "adapter": type(self).__name__,
            "agent": self.card.name,
            "executable": executable,
            "resolved_executable": resolved,
            "cwd": str(self.cwd),
            "cwd_exists": self.cwd.is_dir(),
            "sandbox": self.sandbox,
            "approval_policy": self.approval_policy,
            "invoke_enabled": bool(self.settings.get("invoke_enabled", False)),
        }

    def discovery_capabilities(self) -> dict[str, bool]:
        return {
            "executable_check": True,
            "authentication_check": True,
            "permission_check": True,
            "model_discovery": False,
            "connectivity_test": False,
            "persistent_sessions": True,
        }

    def check_executable(self) -> dict[str, Any]:
        executable = self.command[0]
        resolved = shutil.which(executable)
        if not resolved and Path(executable).is_file():
            resolved = str(Path(executable).resolve())
        return {
            "status": (
                ExecutableStatus.AVAILABLE.value
                if resolved
                else ExecutableStatus.MISSING.value
            ),
            "resolved_executable": resolved,
            "details": {"configured_executable": executable},
        }

    def check_authentication(self) -> dict[str, Any]:
        return {
            "status": AuthenticationStatus.UNKNOWN.value,
            "details": {
                "reason": "authentication is managed by the local Codex host"
            },
        }

    def check_permissions(self) -> dict[str, Any]:
        return {
            "status": (
                PermissionStatus.READ_ONLY.value
                if self.sandbox == "read-only"
                else PermissionStatus.WORKSPACE_WRITE.value
            ),
            "details": {
                "sandbox_mode": self.sandbox,
                "approval_policy": self.approval_policy,
            },
        }

    def connectivity_probe(self) -> dict[str, Any]:
        return {
            "status": ConnectivityStatus.NOT_SUPPORTED.value,
            "details": {
                "reason": "app-server startup is reserved for explicit invocation"
            },
        }

    def _exchange(
        self,
        transport: JsonLineProcess,
        session_id: str,
        request_id: int,
        method: str,
        params: dict[str, Any],
        audit_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {"id": request_id, "method": method, "params": params}
        transport.send(payload)
        audit_payload = {
            "id": request_id,
            "method": method,
            "params": audit_params if audit_params is not None else params,
        }
        self.interoperability.record_event(
            session_id=session_id,
            direction="outbound",
            method=method,
            request_id=request_id,
            payload=audit_payload,
        )
        while True:
            response = transport.receive()
            self._record_inbound(session_id, response)
            if "method" in response and "id" in response:
                self._reject_server_request(transport, session_id, response)
                continue
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise InteroperabilityError(
                    f"Codex App Server {method} failed: {response['error']}"
                )
            result = response.get("result", {})
            if not isinstance(result, dict):
                raise InteroperabilityError(
                    f"Codex App Server {method} result must be an object"
                )
            return result

    def _read_turn(
        self,
        transport: JsonLineProcess,
        *,
        session_id: str,
        turn_id: str,
    ) -> tuple[str, dict[str, Any]]:
        deltas: list[str] = []
        completed_messages: list[str] = []
        while True:
            payload = transport.receive()
            self._record_inbound(session_id, payload)
            if "method" in payload and "id" in payload:
                self._reject_server_request(transport, session_id, payload)
                continue
            method = payload.get("method")
            params = payload.get("params")
            if not isinstance(params, dict):
                params = {}
            if method == "item/agentMessage/delta":
                delta = params.get("delta")
                if isinstance(delta, str):
                    deltas.append(delta)
            elif method == "item/completed":
                item = params.get("item")
                if isinstance(item, dict):
                    text = self._agent_message_text(item)
                    if text:
                        completed_messages.append(text)
            elif method == "turn/completed":
                turn = params.get("turn")
                if not isinstance(turn, dict):
                    turn = {}
                received_turn_id = _optional_text(turn.get("id"))
                if received_turn_id and received_turn_id != turn_id:
                    continue
                status = str(turn.get("status", "completed"))
                if status not in {"completed", "complete"}:
                    raise InteroperabilityError(
                        f"Codex turn ended in status {status!r}"
                    )
                content = (
                    completed_messages[-1]
                    if completed_messages
                    else "".join(deltas).strip()
                )
                return content, turn

    def _reject_server_request(
        self,
        transport: JsonLineProcess,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        method = str(payload.get("method", "unknown"))
        params = payload.get("params")
        if not isinstance(params, dict):
            params = {}
        resource = str(
            params.get("command")
            or params.get("reason")
            or params.get("itemId")
            or method
        )
        approval = self.interoperability.request_approval(
            endpoint_id=self.endpoint_id,
            action=method,
            resource=resource,
            arguments=params,
        )
        self.interoperability.decide_approval(
            approval["id"],
            approve=False,
        )
        if method in APPROVAL_METHODS:
            response = {
                "id": payload["id"],
                "result": {"decision": "decline"},
            }
        else:
            response = {
                "id": payload["id"],
                "error": {
                    "code": -32001,
                    "message": "interactive request rejected by local policy",
                },
            }
        transport.send(response)
        self.interoperability.record_event(
            session_id=session_id,
            direction="outbound",
            method=f"{method}/response",
            request_id=payload.get("id"),
            payload=response,
            status="rejected",
        )

    def _record_inbound(
        self,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.interoperability.record_event(
            session_id=session_id,
            direction="inbound",
            method=str(payload.get("method", "response")),
            request_id=payload.get("id"),
            payload=payload,
        )

    @staticmethod
    def _thread_id(result: dict[str, Any]) -> str:
        thread = result.get("thread")
        value = thread.get("id") if isinstance(thread, dict) else None
        thread_id = _optional_text(value)
        if not thread_id:
            raise InteroperabilityError("thread/start result lacks thread.id")
        return thread_id

    @staticmethod
    def _turn_id(result: dict[str, Any]) -> str:
        turn = result.get("turn")
        value = turn.get("id") if isinstance(turn, dict) else None
        turn_id = _optional_text(value)
        if not turn_id:
            raise InteroperabilityError("turn/start result lacks turn.id")
        return turn_id

    @staticmethod
    def _agent_message_text(item: dict[str, Any]) -> str:
        if item.get("type") not in {"agentMessage", "agent_message"}:
            return ""
        for key in ("text", "content"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
