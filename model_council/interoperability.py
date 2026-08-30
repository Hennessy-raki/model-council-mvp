from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from .config import CouncilConfig
from .registry import sanitize_for_storage
from .store import CouncilStore, utc_now


LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
SESSION_STATUSES = {"active", "completed", "failed", "closed"}
APPROVAL_STATUSES = {"pending", "approved", "rejected"}
MAX_EVENT_BYTES = 128_000


class InteroperabilityError(RuntimeError):
    pass


class InteroperabilityService:
    """Persistent remote identities, sessions, events and explicit approvals."""

    def __init__(self, config: CouncilConfig, store: CouncilStore):
        self.config = config
        self.store = store
        self.sync_from_config()

    def sync_from_config(self) -> None:
        now = utc_now()
        with self.store.connect() as conn:
            for agent_id, item in self.config.agents.items():
                adapter_type = str(item.get("type", "mock"))
                if adapter_type == "codex_app_server":
                    self._upsert_endpoint(
                        conn=conn,
                        endpoint_id=f"agent:{agent_id}",
                        protocol="codex_app_server",
                        display_name=str(item.get("description") or agent_id),
                        transport="stdio",
                        endpoint=None,
                        command=list(item["command"]),
                        protocol_version=str(
                            item.get("protocol_version", "current")
                        ),
                        auth_type="host",
                        auth_env=None,
                        enabled=bool(item.get("enabled", True)),
                        config=item,
                        source="config",
                        now=now,
                    )
                elif adapter_type == "a2a":
                    auth_env = _optional_text(item.get("auth_env"))
                    self._upsert_endpoint(
                        conn=conn,
                        endpoint_id=f"agent:{agent_id}",
                        protocol="a2a",
                        display_name=str(item.get("description") or agent_id),
                        transport="http",
                        endpoint=str(item["endpoint"]),
                        command=[],
                        protocol_version=str(
                            item.get("protocol_version", "1.0")
                        ),
                        auth_type="bearer" if auth_env else "none",
                        auth_env=auth_env,
                        enabled=bool(item.get("enabled", True)),
                        config=item,
                        source="config",
                        now=now,
                    )
            for server_id, item in self.config.mcp_servers.items():
                auth_env = _optional_text(item.get("auth_env"))
                transport = str(item.get("transport", "stdio"))
                self._upsert_endpoint(
                    conn=conn,
                    endpoint_id=f"mcp:{server_id}",
                    protocol="mcp",
                    display_name=str(item.get("display_name", server_id)),
                    transport=transport,
                    endpoint=_optional_text(item.get("endpoint")),
                    command=list(item.get("command", [])),
                    protocol_version=str(
                        item.get("protocol_version", "2025-11-25")
                    ),
                    auth_type="bearer" if auth_env else "none",
                    auth_env=auth_env,
                    enabled=bool(item.get("enabled", True)),
                    config=item,
                    source="config",
                    now=now,
                )

    def endpoints(self) -> list[dict[str, Any]]:
        return self._rows(
            """
            SELECT * FROM interoperability_endpoints
            ORDER BY protocol, display_name, id
            """,
            json_fields=("command_json", "config_json", "observations_json"),
        )

    def endpoint(self, endpoint_id: str) -> dict[str, Any]:
        rows = self._rows(
            "SELECT * FROM interoperability_endpoints WHERE id = ?",
            (endpoint_id,),
            json_fields=("command_json", "config_json", "observations_json"),
        )
        if not rows:
            raise ValueError(f"interoperability endpoint {endpoint_id!r} not found")
        return rows[0]

    def sessions(
        self,
        *,
        endpoint_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        where = []
        params: list[Any] = []
        if endpoint_id:
            where.append("endpoint_id = ?")
            params.append(endpoint_id)
        if agent_id:
            where.append("agent_id = ?")
            params.append(agent_id)
        query = "SELECT * FROM interoperability_sessions"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY updated_at DESC, id DESC"
        return self._rows(
            query,
            tuple(params),
            json_fields=("metadata_json",),
        )

    def active_session(
        self,
        *,
        endpoint_id: str,
        agent_id: str | None,
    ) -> dict[str, Any] | None:
        query = """
            SELECT * FROM interoperability_sessions
            WHERE endpoint_id = ? AND status = 'active'
        """
        params: list[Any] = [endpoint_id]
        if agent_id is None:
            query += " AND agent_id IS NULL"
        else:
            query += " AND agent_id = ?"
            params.append(agent_id)
        query += " ORDER BY updated_at DESC, id DESC LIMIT 1"
        rows = self._rows(
            query,
            tuple(params),
            json_fields=("metadata_json",),
        )
        return rows[0] if rows else None

    def create_session(
        self,
        *,
        endpoint_id: str,
        agent_id: str | None,
        protocol: str,
        remote_session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.endpoint(endpoint_id)
        session_id = str(uuid4())
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO interoperability_sessions(
                    id, endpoint_id, agent_id, protocol, remote_session_id,
                    status, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    session_id,
                    endpoint_id,
                    agent_id,
                    protocol,
                    remote_session_id,
                    _dump(metadata or {}),
                    now,
                    now,
                ),
            )
        return self.sessions(endpoint_id=endpoint_id)[0]

    def record_endpoint_observation(
        self,
        endpoint_id: str,
        key: str,
        value: Any,
    ) -> None:
        if not key.strip():
            raise ValueError("endpoint observation key cannot be empty")
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT observations_json
                FROM interoperability_endpoints WHERE id = ?
                """,
                (endpoint_id,),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"interoperability endpoint {endpoint_id!r} not found"
                )
            observations = json.loads(row["observations_json"])
            observations[key] = _bounded_payload(value)
            conn.execute(
                """
                UPDATE interoperability_endpoints
                SET observations_json = ?, updated_at = ? WHERE id = ?
                """,
                (_dump(observations), utc_now(), endpoint_id),
            )

    def update_session(
        self,
        session_id: str,
        *,
        remote_session_id: str | None = None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if status is not None and status not in SESSION_STATUSES:
            raise ValueError(f"unsupported interoperability status {status!r}")
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT remote_session_id, status, metadata_json
                FROM interoperability_sessions WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"interoperability session {session_id!r} not found")
            merged_metadata = json.loads(row["metadata_json"])
            if metadata:
                merged_metadata.update(sanitize_for_storage(metadata))
            conn.execute(
                """
                UPDATE interoperability_sessions
                SET remote_session_id = ?, status = ?, metadata_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    remote_session_id
                    if remote_session_id is not None
                    else row["remote_session_id"],
                    status or row["status"],
                    _dump(merged_metadata),
                    utc_now(),
                    session_id,
                ),
            )

    def record_event(
        self,
        *,
        session_id: str,
        direction: str,
        method: str,
        payload: dict[str, Any],
        request_id: str | int | None = None,
        status: str = "observed",
    ) -> str:
        if direction not in {"inbound", "outbound"}:
            raise ValueError("event direction must be inbound or outbound")
        event_id = str(uuid4())
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO interoperability_events(
                    id, session_id, direction, method, request_id,
                    payload_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    session_id,
                    direction,
                    method,
                    str(request_id) if request_id is not None else None,
                    _dump(_bounded_payload(payload)),
                    status,
                    utc_now(),
                ),
            )
        return event_id

    def events(
        self,
        session_id: str | None = None,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM interoperability_events"
        params: list[Any] = []
        if session_id:
            query += " WHERE session_id = ?"
            params.append(session_id)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(max(1, limit))
        return self._rows(
            query,
            tuple(params),
            json_fields=("payload_json",),
        )

    def request_approval(
        self,
        *,
        endpoint_id: str,
        action: str,
        resource: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        endpoint = self.endpoint(endpoint_id)
        if not endpoint["enabled"]:
            raise InteroperabilityError(
                f"interoperability endpoint {endpoint_id!r} is disabled"
            )
        approval_id = str(uuid4())
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO interoperability_approvals(
                    id, endpoint_id, action, resource, arguments_json,
                    status, requested_at, decided_at, consumed_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL, NULL)
                """,
                (
                    approval_id,
                    endpoint_id,
                    action,
                    resource,
                    _dump(arguments),
                    utc_now(),
                ),
            )
        return self.approval(approval_id)

    def decide_approval(self, approval_id: str, *, approve: bool) -> None:
        status = "approved" if approve else "rejected"
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE interoperability_approvals
                SET status = ?, decided_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, utc_now(), approval_id),
            ).rowcount
        if not updated:
            raise ValueError(
                f"pending interoperability approval {approval_id!r} not found"
            )

    def approval(self, approval_id: str) -> dict[str, Any]:
        rows = self._rows(
            "SELECT * FROM interoperability_approvals WHERE id = ?",
            (approval_id,),
            json_fields=("arguments_json",),
        )
        if not rows:
            raise ValueError(f"interoperability approval {approval_id!r} not found")
        return rows[0]

    def approvals(self, status: str | None = None) -> list[dict[str, Any]]:
        params: tuple[Any, ...] = ()
        query = "SELECT * FROM interoperability_approvals"
        if status:
            if status not in APPROVAL_STATUSES:
                raise ValueError(f"unsupported approval status {status!r}")
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY requested_at DESC, id DESC"
        return self._rows(
            query,
            params,
            json_fields=("arguments_json",),
        )

    def consume_approval(
        self,
        approval_id: str,
        *,
        action: str,
    ) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM interoperability_approvals
                WHERE id = ? AND status = 'approved' AND consumed_at IS NULL
                """,
                (approval_id,),
            ).fetchone()
            if row is None:
                raise InteroperabilityError(
                    f"approval {approval_id!r} is not approved and unused"
                )
            if row["action"] != action:
                raise InteroperabilityError(
                    f"approval {approval_id!r} is for {row['action']!r}, "
                    f"not {action!r}"
                )
            conn.execute(
                """
                UPDATE interoperability_approvals
                SET consumed_at = ? WHERE id = ?
                """,
                (utc_now(), approval_id),
            )
            item = dict(row)
        item["arguments"] = json.loads(item.pop("arguments_json"))
        return item

    def snapshot(self) -> dict[str, Any]:
        return {
            "endpoints": self.endpoints(),
            "sessions": self.sessions(),
            "events": self.events(limit=100),
            "approvals": self.approvals(),
        }

    @staticmethod
    def require_invocation_enabled(endpoint: dict[str, Any]) -> None:
        if not endpoint["enabled"]:
            raise InteroperabilityError(
                f"interoperability endpoint {endpoint['id']!r} is disabled"
            )
        if not bool(endpoint["config"].get("invoke_enabled", False)):
            raise InteroperabilityError(
                f"interoperability endpoint {endpoint['id']!r} requires "
                "invoke_enabled=true"
            )

    @staticmethod
    def _upsert_endpoint(
        *,
        conn,
        endpoint_id: str,
        protocol: str,
        display_name: str,
        transport: str,
        endpoint: str | None,
        command: list[str],
        protocol_version: str,
        auth_type: str,
        auth_env: str | None,
        enabled: bool,
        config: dict[str, Any],
        source: str,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO interoperability_endpoints(
                id, protocol, display_name, transport, endpoint,
                command_json, protocol_version, auth_type, auth_env,
                enabled, config_json, observations_json, source,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                protocol = excluded.protocol,
                display_name = excluded.display_name,
                transport = excluded.transport,
                endpoint = excluded.endpoint,
                command_json = excluded.command_json,
                protocol_version = excluded.protocol_version,
                auth_type = excluded.auth_type,
                auth_env = excluded.auth_env,
                enabled = excluded.enabled,
                config_json = excluded.config_json,
                source = excluded.source,
                updated_at = excluded.updated_at
            WHERE excluded.source = 'user'
               OR interoperability_endpoints.source != 'user'
            """,
            (
                endpoint_id,
                protocol,
                display_name,
                transport,
                endpoint,
                _dump(command),
                protocol_version,
                auth_type,
                auth_env,
                int(enabled),
                _dump(config),
                source,
                now,
                now,
            ),
        )

    def _rows(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        json_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for field in json_fields:
                item[field.removesuffix("_json")] = json.loads(item.pop(field))
            if "enabled" in item:
                item["enabled"] = bool(item["enabled"])
            result.append(item)
        return result


class JsonLineProcess:
    """Bounded JSON-line subprocess transport using argument arrays only."""

    def __init__(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
    ):
        self.timeout_seconds = timeout_seconds
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            shell=False,
            bufsize=1,
        )
        self._stdout: queue.Queue[str | None] = queue.Queue()
        self._stderr: list[str] = []
        self._stdout_thread = threading.Thread(
            target=self._read_stdout,
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()

    def send(self, payload: dict[str, Any]) -> None:
        if self.process.stdin is None or self.process.poll() is not None:
            raise InteroperabilityError("JSON-line process is not running")
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def receive(self) -> dict[str, Any]:
        try:
            line = self._stdout.get(timeout=self.timeout_seconds)
        except queue.Empty as exc:
            raise InteroperabilityError(
                "timed out waiting for JSON-line response"
            ) from exc
        if line is None:
            raise InteroperabilityError(
                "JSON-line process exited before returning a response: "
                f"{self.stderr_tail()}"
            )
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InteroperabilityError(
                "JSON-line process returned invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise InteroperabilityError(
                "JSON-line process response must be an object"
            )
        return payload

    def stderr_tail(self) -> str:
        return "".join(self._stderr[-50:])[-2000:]

    def close(self) -> None:
        if self.process.stdin:
            try:
                self.process.stdin.close()
            except OSError:
                pass
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self._stdout_thread.join(timeout=1)
        self._stderr_thread.join(timeout=1)
        for stream in (self.process.stdout, self.process.stderr):
            if stream:
                try:
                    stream.close()
                except OSError:
                    pass

    def _read_stdout(self) -> None:
        if self.process.stdout is None:
            self._stdout.put(None)
            return
        for line in self.process.stdout:
            if line.strip():
                self._stdout.put(line)
        self._stdout.put(None)

    def _read_stderr(self) -> None:
        if self.process.stderr is None:
            return
        for line in self.process.stderr:
            self._stderr.append(line)


class MCPToolBroker:
    """MCP client with single-use, persisted human approvals for tool calls."""

    def __init__(
        self,
        service: InteroperabilityService,
        *,
        config_dir: Path,
    ):
        self.service = service
        self.config_dir = config_dir

    def list_tools(self, server_id: str) -> list[dict[str, Any]]:
        endpoint = self.service.endpoint(f"mcp:{server_id}")
        self.service.require_invocation_enabled(endpoint)
        result = self._request(endpoint, "tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise InteroperabilityError("MCP tools/list result must contain a list")
        return [item for item in tools if isinstance(item, dict)]

    def request_tool_call(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if not tool_name.strip():
            raise ValueError("MCP tool name cannot be empty")
        if not isinstance(arguments, dict):
            raise ValueError("MCP tool arguments must be an object")
        return self.service.request_approval(
            endpoint_id=f"mcp:{server_id}",
            action="mcp.tools.call",
            resource=tool_name,
            arguments=arguments,
        )

    def call_approved_tool(self, approval_id: str) -> dict[str, Any]:
        approval = self.service.consume_approval(
            approval_id,
            action="mcp.tools.call",
        )
        endpoint = self.service.endpoint(approval["endpoint_id"])
        self.service.require_invocation_enabled(endpoint)
        return self._request(
            endpoint,
            "tools/call",
            {
                "name": approval["resource"],
                "arguments": approval["arguments"],
            },
        )

    def _request(
        self,
        endpoint: dict[str, Any],
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if endpoint["transport"] == "stdio":
            return self._stdio_request(endpoint, method, params)
        if endpoint["transport"] == "streamable_http":
            return self._http_request(endpoint, method, params)
        raise InteroperabilityError(
            f"unsupported MCP transport {endpoint['transport']!r}"
        )

    def _stdio_request(
        self,
        endpoint: dict[str, Any],
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        command = endpoint["command"]
        transport = JsonLineProcess(
            command,
            cwd=self.config_dir,
            timeout_seconds=int(endpoint["config"].get("timeout_seconds", 30)),
        )
        session = self.service.create_session(
            endpoint_id=endpoint["id"],
            agent_id=None,
            protocol="mcp",
        )
        try:
            initialize_result = self._stdio_exchange(
                transport,
                session["id"],
                1,
                "initialize",
                {
                    "protocolVersion": endpoint["protocol_version"],
                    "capabilities": {},
                    "clientInfo": {
                        "name": "model-council",
                        "version": "0.1.0",
                    },
                },
            )
            self.service.record_endpoint_observation(
                endpoint["id"],
                "initialize",
                initialize_result,
            )
            initialized = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
            transport.send(initialized)
            self.service.record_event(
                session_id=session["id"],
                direction="outbound",
                method="notifications/initialized",
                payload=initialized,
            )
            result = self._stdio_exchange(
                transport,
                session["id"],
                2,
                method,
                params,
            )
            self.service.update_session(session["id"], status="completed")
            return result
        except Exception:
            self.service.update_session(
                session["id"],
                status="failed",
                metadata={"stderr_tail": transport.stderr_tail()},
            )
            raise
        finally:
            transport.close()

    def _stdio_exchange(
        self,
        transport: JsonLineProcess,
        session_id: str,
        request_id: int,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        transport.send(request)
        self.service.record_event(
            session_id=session_id,
            direction="outbound",
            method=method,
            request_id=request_id,
            payload=request,
        )
        while True:
            response = transport.receive()
            response_method = str(response.get("method", "response"))
            self.service.record_event(
                session_id=session_id,
                direction="inbound",
                method=response_method,
                request_id=response.get("id"),
                payload=response,
            )
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise InteroperabilityError(
                    f"MCP {method} failed: {response['error']}"
                )
            result = response.get("result", {})
            if not isinstance(result, dict):
                raise InteroperabilityError(
                    f"MCP {method} result must be an object"
                )
            return result

    def _http_request(
        self,
        endpoint: dict[str, Any],
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        url = validate_remote_url(str(endpoint["endpoint"]))
        session = self.service.create_session(
            endpoint_id=endpoint["id"],
            agent_id=None,
            protocol="mcp",
        )
        try:
            initialize_result, remote_session_id = self._http_exchange(
                endpoint,
                session["id"],
                url,
                1,
                "initialize",
                {
                    "protocolVersion": endpoint["protocol_version"],
                    "capabilities": {},
                    "clientInfo": {
                        "name": "model-council",
                        "version": "0.1.0",
                    },
                },
                None,
            )
            self.service.record_endpoint_observation(
                endpoint["id"],
                "initialize",
                initialize_result,
            )
            self.service.update_session(
                session["id"],
                remote_session_id=remote_session_id,
            )
            self._http_notification(
                endpoint,
                session["id"],
                url,
                "notifications/initialized",
                {},
                remote_session_id,
            )
            result, _ = self._http_exchange(
                endpoint,
                session["id"],
                url,
                2,
                method,
                params,
                remote_session_id,
            )
            self.service.update_session(session["id"], status="completed")
            return result
        except Exception:
            self.service.update_session(session["id"], status="failed")
            raise

    def _http_exchange(
        self,
        endpoint: dict[str, Any],
        session_id: str,
        url: str,
        request_id: int,
        method: str,
        params: dict[str, Any],
        remote_session_id: str | None,
    ) -> tuple[dict[str, Any], str | None]:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": endpoint["protocol_version"],
        }
        hostname = urlsplit(url).hostname
        if hostname in LOOPBACK_HOSTS:
            headers["Origin"] = "http://localhost"
        if remote_session_id:
            headers["Mcp-Session-Id"] = remote_session_id
        _authorization_header(endpoint, headers)
        self.service.record_event(
            session_id=session_id,
            direction="outbound",
            method=method,
            request_id=request_id,
            payload=payload,
        )
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with _NO_REDIRECT_OPENER.open(
                request,
                timeout=int(endpoint["config"].get("timeout_seconds", 30)),
            ) as response:
                content_type = response.headers.get("Content-Type", "")
                if not content_type.startswith("application/json"):
                    raise InteroperabilityError(
                        "MCP Streamable HTTP response must be JSON for "
                        "non-streaming requests"
                    )
                body = json.loads(response.read().decode("utf-8"))
                returned_session = response.headers.get("Mcp-Session-Id")
        except (HTTPError, URLError) as exc:
            if isinstance(exc, HTTPError):
                try:
                    exc.read()
                finally:
                    exc.close()
            raise InteroperabilityError(
                f"MCP Streamable HTTP request failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(body, dict):
            raise InteroperabilityError("MCP HTTP response must be an object")
        self.service.record_event(
            session_id=session_id,
            direction="inbound",
            method=str(body.get("method", "response")),
            request_id=body.get("id"),
            payload=body,
        )
        if "error" in body:
            raise InteroperabilityError(f"MCP {method} failed: {body['error']}")
        result = body.get("result", {})
        if not isinstance(result, dict):
            raise InteroperabilityError(f"MCP {method} result must be an object")
        return result, returned_session

    def _http_notification(
        self,
        endpoint: dict[str, Any],
        session_id: str,
        url: str,
        method: str,
        params: dict[str, Any],
        remote_session_id: str | None,
    ) -> None:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": endpoint["protocol_version"],
        }
        hostname = urlsplit(url).hostname
        if hostname in LOOPBACK_HOSTS:
            headers["Origin"] = "http://localhost"
        if remote_session_id:
            headers["Mcp-Session-Id"] = remote_session_id
        _authorization_header(endpoint, headers)
        self.service.record_event(
            session_id=session_id,
            direction="outbound",
            method=method,
            payload=payload,
        )
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with _NO_REDIRECT_OPENER.open(
                request,
                timeout=int(endpoint["config"].get("timeout_seconds", 30)),
            ) as response:
                response.read()
        except (HTTPError, URLError) as exc:
            if isinstance(exc, HTTPError):
                try:
                    exc.read()
                finally:
                    exc.close()
            raise InteroperabilityError(
                f"MCP Streamable HTTP notification failed: "
                f"{type(exc).__name__}"
            ) from exc


def validate_remote_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("remote endpoint must be an http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("remote endpoint URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError(
            "remote endpoint URL must not contain query parameters or fragments"
        )
    if parsed.scheme == "http" and parsed.hostname not in LOOPBACK_HOSTS:
        raise ValueError("non-loopback remote endpoints must use HTTPS")
    return url


def _authorization_header(
    endpoint: dict[str, Any],
    headers: dict[str, str],
) -> None:
    auth_env = endpoint.get("auth_env")
    if not auth_env:
        return
    token = os.environ.get(str(auth_env))
    if not token:
        raise InteroperabilityError(
            f"environment variable {auth_env!r} is not configured"
        )
    headers["Authorization"] = f"Bearer {token}"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dump(value: Any) -> str:
    return json.dumps(
        sanitize_for_storage(value),
        ensure_ascii=False,
        sort_keys=True,
    )


def _bounded_payload(value: Any) -> Any:
    sanitized = sanitize_for_storage(value)
    encoded = json.dumps(
        sanitized,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) <= MAX_EVENT_BYTES:
        return sanitized
    return {
        "truncated": True,
        "bytes": len(encoded),
        "sha256": sha256(encoded).hexdigest(),
        "top_level_type": type(sanitized).__name__,
    }


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler())
