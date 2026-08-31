from __future__ import annotations

import json
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote, urlsplit

from .adapters import build_adapters
from .backup import BackupService
from .comparison import RunComparisonService
from .config import CouncilConfig
from .evaluation import EvaluationService
from .ledger import UsageLedger
from .interoperability import InteroperabilityService
from .outbound_context import OutboundContextService
from .repair import RepairService
from .registry import RegistryService
from .routing import RoutingService
from .store import CouncilStore
from .workspaces import WorkspaceService


MAX_REQUEST_BYTES = 1_000_000
LOCAL_HOSTS = {"127.0.0.1", "localhost"}


class LocalSettingsApplication:
    """Local-only Board 6 control surface over the persisted SQLite contracts."""

    def __init__(self, config: CouncilConfig):
        self.config = config
        self.store = CouncilStore(config.state_dir / "council.db")
        self.registry = RegistryService(self.store)
        self.registry.sync_from_config(config)
        self.interoperability = InteroperabilityService(config, self.store)
        self.adapters = build_adapters(config, self.store)
        self.ledger = UsageLedger(
            config=config,
            store=self.store,
            registry=self.registry,
        )
        self.router = RoutingService(
            config=config,
            store=self.store,
            registry=self.registry,
            adapters={},
        )
        self.outbound_context = OutboundContextService(self.store)
        self.workspaces = WorkspaceService(self.store)
        self.repairs = RepairService(self.store, self.workspaces)
        self.evaluations = EvaluationService(config, self.store)
        self.backups = BackupService(self.store)
        self.comparison = RunComparisonService(
            self.store,
            self.ledger,
            self.router,
        )

    def state(self) -> dict[str, Any]:
        runs = self.store.list_runs(limit=20)
        artifacts = []
        for run in runs:
            for artifact in self.store.artifacts_for_run(
                run["id"],
                display_mode=self.registry.provenance_display_mode(),
            ):
                artifacts.append(artifact)
        workspaces = self.workspaces.workspaces()
        repairs = self.repairs.sessions()
        evaluations = self.evaluations.evaluations()
        comparison = (
            self.comparison.compare(runs[1]["id"], runs[0]["id"])
            if len(runs) >= 2
            else None
        )
        return {
            "project": {
                "name": self.config.project_name,
                "state": "local SQLite",
                "external_calls": "none on page refresh",
            },
            "adapter_capabilities": [
                {
                    "agent_id": agent_id,
                    "adapter": type(adapter).__name__,
                    "discovery": adapter.discovery_capabilities(),
                    "billing": adapter.billing_capabilities(),
                }
                for agent_id, adapter in sorted(self.adapters.items())
            ],
            "interoperability": self.interoperability.snapshot(),
            "registry": self.registry.snapshot(),
            "ledger": {
                "summary": self.ledger.summary(
                    project_name=self.config.project_name
                ),
                "events": self.ledger.events(limit=100),
                "budgets": self.ledger.budget_policies(),
                "alerts": self.ledger.alerts(),
                "balance_snapshots": self.ledger.balance_snapshots(),
            },
            "routing": self.router.decisions(),
            "runs": runs,
            "artifacts": artifacts,
            "approval_center": self._approval_center(),
            "workspaces": {
                "leases": workspaces,
                "evidence": self._workspace_evidence(),
                "approvals": self.workspaces.approvals(),
            },
            "repairs": {
                "sessions": repairs,
                "details": [
                    self.repairs.snapshot(item["id"])
                    for item in repairs[:10]
                ],
            },
            "evaluations": evaluations,
            "run_comparison": comparison,
            "backups": {
                "items": self.backups.backups(),
                "restore_approvals": self.backups.approvals(),
            },
        }

    def compare_runs(self, left_run_id: str, right_run_id: str) -> dict[str, Any]:
        return self.comparison.compare(left_run_id, right_run_id)

    def update(
        self,
        resource: str,
        resource_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        _matching_id(resource, resource_id, payload)
        if resource == "providers":
            self.registry.upsert_provider(
                resource_id,
                display_name=_text(payload, "display_name", resource_id),
                kind=_text(payload, "kind"),
                enabled=_boolean(payload, "enabled", True),
                config=_object(payload, "config"),
            )
        elif resource == "models":
            self.registry.upsert_model(
                resource_id,
                provider_id=_text(payload, "provider_id"),
                display_name=_text(payload, "display_name", resource_id),
                enabled=_boolean(payload, "enabled", True),
                capabilities=_array(payload, "capabilities"),
                metadata=_object(payload, "metadata"),
            )
        elif resource == "agents":
            self.registry.upsert_agent(
                resource_id,
                adapter_type=_text(payload, "adapter_type"),
                provider_id=_optional_text(payload, "provider_id"),
                model_id=_optional_text(payload, "model_id"),
                role=_text(payload, "role"),
                description=_text(payload, "description", ""),
                enabled=_boolean(payload, "enabled", True),
                capabilities=_array(payload, "capabilities"),
                boundaries=_array(payload, "boundaries"),
                config=_object(payload, "config"),
            )
        elif resource == "roles":
            self.registry.assign_role(
                resource_id,
                mode=_text(payload, "mode"),
                agent_id=_optional_text(payload, "agent_id"),
                model_id=_optional_text(payload, "model_id"),
                locked=_boolean(payload, "locked", False),
                constraints=_object(payload, "constraints"),
            )
        elif resource == "settings":
            if "value" not in payload:
                raise ValueError("setting value is required")
            self.registry.set_setting(resource_id, payload["value"])
        elif resource == "budgets":
            self.ledger.set_budget_policy(
                policy_id=resource_id,
                scope=_text(payload, "scope"),
                scope_key=_text(payload, "scope_key"),
                metric=_text(payload, "metric"),
                warning=payload.get("warning"),
                hard=payload.get("hard"),
                currency=_optional_text(payload, "currency"),
            )
        elif resource == "interop-approvals":
            decision = _text(payload, "decision")
            if decision not in {"approve", "reject"}:
                raise ValueError("decision must be approve or reject")
            self.interoperability.decide_approval(
                resource_id,
                approve=decision == "approve",
            )
        elif resource == "outbound-context-approvals":
            decision = _decision(payload)
            self.outbound_context.decide(
                resource_id,
                approve=decision == "approve",
                confirmation=_text(payload, "scope_sha256", "")
                if decision == "approve"
                else "",
            )
        elif resource == "workspace-approvals":
            decision = _decision(payload)
            self.workspaces.decide(
                resource_id,
                approve=decision == "approve",
                confirmation=_text(payload, "scope_sha256", "")
                if decision == "approve"
                else "",
            )
        elif resource == "backups":
            if resource_id != "new":
                raise ValueError("backup creation resource id must be 'new'")
            self.backups.create(
                include_artifacts=_boolean(
                    payload,
                    "include_artifacts",
                    False,
                )
            )
        elif resource == "backup-restore-requests":
            self.backups.request_restore(resource_id)
        elif resource == "backup-restore-approvals":
            decision = _decision(payload)
            self.backups.decide(
                resource_id,
                approve=decision == "approve",
                confirmation=_text(payload, "scope_sha256", "")
                if decision == "approve"
                else "",
            )
        elif resource == "backup-restores":
            if _text(payload, "action") != "restore":
                raise ValueError("backup restore action must be restore")
            self.backups.restore(resource_id)
        else:
            raise ValueError(f"unsupported local resource {resource!r}")
        return self.state()

    def _approval_center(self) -> list[dict[str, Any]]:
        result = []
        for item in self.interoperability.approvals():
            result.append(
                {
                    "kind": "interoperability",
                    "id": item["id"],
                    "status": item["status"],
                    "action": item["action"],
                    "resource": item["resource"],
                    "scope_sha256": None,
                    "scope": item["arguments"],
                    "requested_at": item["requested_at"],
                    "decided_at": item["decided_at"],
                    "consumed_at": item["consumed_at"],
                }
            )
        for item in self.outbound_context.manifests():
            detailed = self.outbound_context.manifest(
                item["id"],
                include_prompt=True,
            )
            outbound_scope = dict(item["manifest"])
            outbound_scope["prompt"] = detailed["prompt"]
            result.append(
                {
                    "kind": "outbound_context",
                    "id": item["id"],
                    "status": item["status"],
                    "action": "external context",
                    "resource": item["endpoint_id"],
                    "scope_sha256": item["approval_sha256"],
                    "scope": outbound_scope,
                    "requested_at": item["requested_at"],
                    "decided_at": item["decided_at"],
                    "consumed_at": item["consumed_at"],
                }
            )
        for item in self.workspaces.approvals():
            result.append(
                {
                    "kind": "workspace",
                    "id": item["id"],
                    "status": item["status"],
                    "action": item["action"],
                    "resource": item["lease_id"],
                    "scope_sha256": item["scope_sha256"],
                    "scope": item["scope"],
                    "requested_at": item["requested_at"],
                    "decided_at": item["decided_at"],
                    "consumed_at": item["consumed_at"],
                }
            )
        for item in self.backups.approvals():
            result.append(
                {
                    "kind": "backup_restore",
                    "id": item["id"],
                    "status": item["status"],
                    "action": "restore",
                    "resource": item["backup_id"],
                    "scope_sha256": item["scope_sha256"],
                    "scope": item["scope"],
                    "requested_at": item["requested_at"],
                    "decided_at": item["decided_at"],
                    "consumed_at": item["consumed_at"],
                }
            )
        return sorted(
            result,
            key=lambda item: (item["requested_at"], item["id"]),
            reverse=True,
        )

    def _workspace_evidence(self) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM worktree_evidence
                ORDER BY created_at DESC, id DESC
                LIMIT 100
                """
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["command"] = json.loads(item.pop("command_json"))
            item["metadata"] = json.loads(item.pop("metadata_json"))
            result.append(item)
        return result


def serve(config: CouncilConfig, *, host: str, port: int) -> None:
    if host not in LOCAL_HOSTS:
        raise ValueError(
            "the local settings interface may bind only to 127.0.0.1 "
            "or localhost"
        )
    app = LocalSettingsApplication(config)
    write_token = secrets.token_urlsafe(32)
    page_nonce = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(
        (host, port),
        _handler_for(app, write_token, page_nonce),
    )
    server.daemon_threads = True
    actual_host, actual_port = server.server_address[:2]
    print(f"Model Council local settings interface: http://{actual_host}:{actual_port}/")
    print("SQLite remains authoritative; this server never invokes a model.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLocal settings interface stopped.")
    finally:
        server.server_close()


def _handler_for(
    app: LocalSettingsApplication,
    write_token: str | None = None,
    page_nonce: str | None = None,
):
    token = write_token or secrets.token_urlsafe(32)
    nonce = page_nonce or secrets.token_urlsafe(24)

    class LocalSettingsHandler(BaseHTTPRequestHandler):
        server_version = "ModelCouncilLocal/0.1"

        def do_GET(self) -> None:
            if not self._trusted_host():
                self._error(HTTPStatus.FORBIDDEN, "untrusted Host header")
                return
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/":
                self._html(
                    INDEX_HTML.replace("__WRITE_TOKEN__", token).replace(
                        "__CSP_NONCE__",
                        nonce,
                    )
                )
                return
            if path == "/api/state":
                self._json(HTTPStatus.OK, app.state())
                return
            if path == "/api/compare":
                from urllib.parse import parse_qs

                query = parse_qs(parsed.query)
                left = query.get("left", [""])[0]
                right = query.get("right", [""])[0]
                if not left or not right:
                    self._error(
                        HTTPStatus.BAD_REQUEST,
                        "left and right run ids are required",
                    )
                    return
                try:
                    payload = app.compare_runs(left, right)
                except ValueError as exc:
                    self._error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._json(HTTPStatus.OK, payload)
                return
            self._error(HTTPStatus.NOT_FOUND, "unknown local endpoint")

        def do_PUT(self) -> None:
            if not self._trusted_write(token):
                self._error(HTTPStatus.FORBIDDEN, "local write authorization failed")
                return
            parts = [
                unquote(part)
                for part in urlsplit(self.path).path.split("/")
                if part
            ]
            if len(parts) != 3 or parts[0] != "api":
                self._error(HTTPStatus.NOT_FOUND, "unknown local endpoint")
                return
            try:
                payload = self._request_json()
                state = app.update(parts[1], parts[2], payload)
            except (ValueError, RuntimeError) as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._json(HTTPStatus.OK, state)

        def do_POST(self) -> None:
            self._error(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "use PUT to persist a local setting",
            )

        def do_OPTIONS(self) -> None:
            self._error(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "cross-origin requests are not supported",
            )

        def log_message(self, format: str, *args: object) -> None:
            return

        def _request_json(self) -> dict[str, Any]:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Content-Length is required")
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise ValueError("Content-Length must be an integer") from exc
            if length < 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("request body exceeds the local size limit")
            content_type = self.headers.get("Content-Type", "")
            if content_type.split(";", 1)[0].strip().lower() != "application/json":
                raise ValueError("Content-Type must be application/json")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("request body must be UTF-8 JSON") from exc
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            return payload

        def _html(self, content: str) -> None:
            body = content.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self._security_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._write_body(body)

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._security_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._write_body(body)

        def _error(self, status: HTTPStatus, message: str) -> None:
            self._json(status, {"error": message})

        def _write_body(self, body: bytes) -> None:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

        def _security_headers(self) -> None:
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; connect-src 'self'; img-src 'self'; "
                f"style-src 'self' 'nonce-{nonce}'; "
                f"script-src 'self' 'nonce-{nonce}'; "
                "base-uri 'none'; frame-ancestors 'none'",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Permissions-Policy",
                "camera=(), geolocation=(), microphone=()",
            )
            self.send_header("Cache-Control", "no-store")

        def _trusted_host(self) -> bool:
            host_header = self.headers.get("Host", "")
            if not host_header:
                return False
            try:
                hostname = urlsplit(f"//{host_header}").hostname
            except ValueError:
                return False
            return hostname in LOCAL_HOSTS

        def _trusted_write(self, expected_token: str) -> bool:
            if not self._trusted_host():
                return False
            if self.headers.get("X-Model-Council-Token") != expected_token:
                return False
            origin = self.headers.get("Origin")
            if origin is None:
                return True
            return origin == f"http://{self.headers['Host']}"

    return LocalSettingsHandler


def _matching_id(resource: str, resource_id: str, payload: dict[str, Any]) -> None:
    if (
        not resource_id.strip()
        or len(resource_id) > 200
        or any(character in resource_id for character in "/\\\r\n\0")
    ):
        raise ValueError(f"{resource} id is invalid")
    body_id = payload.get("id")
    if body_id is not None and body_id != resource_id:
        raise ValueError("path id must match JSON id")


def _text(
    payload: dict[str, Any],
    key: str,
    default: str | None = None,
) -> str:
    value = payload.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def _boolean(payload: dict[str, Any], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be true or false")
    return value


def _array(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a JSON array")
    return value


def _object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return value


def _decision(payload: dict[str, Any]) -> str:
    decision = _text(payload, "decision")
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    return decision


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Model Council — Local Settings</title>
  <style nonce="__CSP_NONCE__">
    :root { color-scheme: light dark; font-family: ui-sans-serif, system-ui, sans-serif; }
    body { max-width: 1200px; margin: 0 auto; padding: 2rem; line-height: 1.45; }
    header { display: flex; gap: 1rem; justify-content: space-between; align-items: start; }
    h2 { border-bottom: 1px solid #7775; padding-bottom: .35rem; margin-top: 2.5rem; }
    .notice, #message { padding: .75rem 1rem; border-radius: .5rem; background: #1677ff22; }
    #message:empty { display: none; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 1rem; }
    form, details { border: 1px solid #7776; padding: 1rem; border-radius: .5rem; margin: 1rem 0; }
    label { display: grid; gap: .25rem; margin: .55rem 0; font-weight: 600; }
    input, select, textarea, button { font: inherit; padding: .5rem; }
    textarea { min-height: 5rem; }
    button { cursor: pointer; }
    table { border-collapse: collapse; width: 100%; margin: .75rem 0 1.5rem; }
    th, td { text-align: left; padding: .5rem; border-bottom: 1px solid #7775; vertical-align: top; }
    th { white-space: nowrap; }
    code { white-space: pre-wrap; overflow-wrap: anywhere; }
    .small { font-size: .9rem; opacity: .82; }
    .table-wrap { overflow-x: auto; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Model Council local settings</h1>
      <p class="notice">This control surface is local-only. It reads and writes SQLite state; it does not invoke models, discovery probes, balances, or external services.</p>
    </div>
    <button id="refresh" type="button">Refresh local state</button>
  </header>
  <p id="message" role="status"></p>
  <main id="app" aria-live="polite">Loading local state…</main>
  <script nonce="__CSP_NONCE__">
    const app = document.querySelector("#app");
    const message = document.querySelector("#message");
    const writeToken = "__WRITE_TOKEN__";
    let currentState = null;
    const text = value => value == null ? "" : String(value);
    const escapeHtml = value => text(value).replace(/[&<>"']/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
    const json = value => escapeHtml(JSON.stringify(value ?? {}, null, 2));
    const table = (items, columns, resource = null) => {
      if (!items.length) return "<p class='small'>No persisted records.</p>";
      const actionHeader = resource ? "<th>Action</th>" : "";
      const actionCell = item => resource
        ? `<td><button class="edit-record" type="button" data-resource="${escapeHtml(resource)}" data-id="${escapeHtml(item.id ?? item.role_key ?? item.key)}">Edit</button></td>`
        : "";
      return `<div class="table-wrap"><table><thead><tr>${columns.map(c => `<th>${escapeHtml(c.label)}</th>`).join("")}${actionHeader}</tr></thead><tbody>${items.map(item => `<tr>${columns.map(c => `<td>${c.json ? `<code>${json(item[c.key])}</code>` : escapeHtml(item[c.key])}</td>`).join("")}${actionCell(item)}</tr>`).join("")}</tbody></table></div>`;
    };
    const parse = (form, name, fallback) => {
      const raw = form.elements[name].value.trim();
      if (!raw) return fallback;
      try { return JSON.parse(raw); } catch { throw new Error(`${name} must be valid JSON`); }
    };
    const bool = (form, name) => form.elements[name].checked;
    const put = async (path, payload) => {
      const response = await fetch(path, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-Model-Council-Token": writeToken
        },
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Local save failed");
      return result;
    };
    const save = async (event, resource, fields) => {
      event.preventDefault();
      const form = event.currentTarget;
      try {
        const id = form.elements.id.value.trim();
        if (!id) throw new Error("id is required");
        const state = await put(`/api/${resource}/${encodeURIComponent(id)}`, fields(form, id));
        render(state);
        message.textContent = `Saved local ${resource.slice(0, -1)} “${id}”.`;
      } catch (error) {
        message.textContent = error.message;
      }
    };
    const form = (title, id, fields, resource) => `<details><summary>${title}</summary><form data-resource="${resource}">
      <label>Id<input name="id" value="${escapeHtml(id || "")}" required></label>
      ${fields}
      <button type="submit">Save locally</button>
      <p class="small">The saved record becomes user-owned and survives a later configuration sync. Sensitive key values are redacted before SQLite storage.</p>
    </form></details>`;
    const formField = (label, name, value, type = "text") => `<label>${label}${type === "checkbox" ? `<input name="${name}" type="checkbox" ${value ? "checked" : ""}>` : type === "textarea" ? `<textarea name="${name}">${escapeHtml(value)}</textarea>` : `<input name="${name}" value="${escapeHtml(value)}">`}</label>`;
    function bindForms() {
      document.querySelectorAll("form[data-resource]").forEach(formElement => {
        const resource = formElement.dataset.resource;
        formElement.addEventListener("submit", event => {
          const data = {
            providers: (f, id) => ({id, display_name: f.elements.display_name.value, kind: f.elements.kind.value, enabled: bool(f, "enabled"), config: parse(f, "config", {})}),
            models: (f, id) => ({id, provider_id: f.elements.provider_id.value, display_name: f.elements.display_name.value, enabled: bool(f, "enabled"), capabilities: parse(f, "capabilities", []), metadata: parse(f, "metadata", {})}),
            agents: (f, id) => ({id, adapter_type: f.elements.adapter_type.value, provider_id: f.elements.provider_id.value || null, model_id: f.elements.model_id.value || null, role: f.elements.role.value, description: f.elements.description.value, enabled: bool(f, "enabled"), capabilities: parse(f, "capabilities", []), boundaries: parse(f, "boundaries", []), config: parse(f, "config", {})}),
            roles: (f, id) => ({id, mode: f.elements.mode.value, agent_id: f.elements.agent_id.value || null, model_id: f.elements.model_id.value || null, locked: bool(f, "locked"), constraints: parse(f, "constraints", {})}),
            settings: (f, id) => ({id, value: parse(f, "value", "")}),
            budgets: (f, id) => ({id, scope: f.elements.scope.value, scope_key: f.elements.scope_key.value, metric: f.elements.metric.value, warning: f.elements.warning.value || null, hard: f.elements.hard.value || null, currency: f.elements.currency.value || null})
          };
          save(event, resource, data[resource]);
        });
      });
      document.querySelectorAll(".edit-record").forEach(button => {
        button.addEventListener("click", () => editRecord(
          button.dataset.resource,
          button.dataset.id
        ));
      });
      document.querySelectorAll(".approval-action").forEach(button => {
        button.addEventListener("click", async () => {
          try {
            const id = button.dataset.id;
            const decision = button.dataset.decision;
            const state = await put(
              `/api/interop-approvals/${encodeURIComponent(id)}`,
              {id, decision}
            );
            render(state);
            message.textContent = `${decision === "approve" ? "Approved" : "Rejected"} interoperability request “${id}”.`;
          } catch (error) {
            message.textContent = error.message;
          }
        });
      });
      document.querySelectorAll(".center-approval-action").forEach(button => {
        button.addEventListener("click", async () => {
          try {
            const id = button.dataset.id;
            const decision = button.dataset.decision;
            const kind = button.dataset.kind;
            const resources = {
              interoperability: "interop-approvals",
              outbound_context: "outbound-context-approvals",
              workspace: "workspace-approvals",
              backup_restore: "backup-restore-approvals"
            };
            const payload = {id, decision};
            if (button.dataset.scope) payload.scope_sha256 = button.dataset.scope;
            const state = await put(
              `/api/${resources[kind]}/${encodeURIComponent(id)}`,
              payload
            );
            render(state);
            message.textContent = `${decision === "approve" ? "Approved" : "Rejected"} ${kind} request ${id}.`;
          } catch (error) {
            message.textContent = error.message;
          }
        });
      });
      document.querySelectorAll(".backup-create").forEach(button => {
        button.addEventListener("click", async () => {
          try {
            const state = await put("/api/backups/new", {
              id: "new",
              include_artifacts: button.dataset.artifacts === "true"
            });
            render(state);
            message.textContent = "Created a verified local backup.";
          } catch (error) {
            message.textContent = error.message;
          }
        });
      });
      document.querySelectorAll(".backup-request").forEach(button => {
        button.addEventListener("click", async () => {
          try {
            const id = button.dataset.id;
            const state = await put(
              `/api/backup-restore-requests/${encodeURIComponent(id)}`,
              {id}
            );
            render(state);
            message.textContent = `Created an exact restore approval for backup ${id}.`;
          } catch (error) {
            message.textContent = error.message;
          }
        });
      });
      document.querySelectorAll(".backup-restore").forEach(button => {
        button.addEventListener("click", async () => {
          try {
            const id = button.dataset.id;
            const state = await put(
              `/api/backup-restores/${encodeURIComponent(id)}`,
              {id, action: "restore"}
            );
            render(state);
            message.textContent = `Consumed restore approval ${id}.`;
          } catch (error) {
            message.textContent = error.message;
          }
        });
      });
      const compareButton = document.querySelector("#compare-runs");
      if (compareButton) {
        compareButton.addEventListener("click", async () => {
          try {
            const left = document.querySelector("#compare-left").value;
            const right = document.querySelector("#compare-right").value;
            const response = await fetch(
              `/api/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`,
              {cache: "no-store"}
            );
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "Run comparison failed");
            document.querySelector("#comparison-result").innerHTML =
              `<pre><code>${json(result)}</code></pre>`;
          } catch (error) {
            message.textContent = error.message;
          }
        });
      }
    }
    function setField(formElement, name, value, asJson = false) {
      const field = formElement.elements[name];
      if (!field) return;
      if (field.type === "checkbox") {
        field.checked = Boolean(value);
      } else {
        field.value = asJson ? JSON.stringify(value ?? {}, null, 2) : text(value);
      }
    }
    function editRecord(resource, id) {
      const collections = {
        providers: currentState.registry.providers,
        models: currentState.registry.models,
        agents: currentState.registry.agents,
        roles: currentState.registry.roles,
        settings: Object.entries(currentState.registry.settings).map(([key, item]) => ({key, ...item})),
        budgets: currentState.ledger.budgets
      };
      const keys = {
        providers: "id", models: "id", agents: "id", roles: "role_key",
        settings: "key", budgets: "id"
      };
      const item = collections[resource].find(record => text(record[keys[resource]]) === id);
      const formElement = document.querySelector(`form[data-resource="${resource}"]`);
      if (!item || !formElement) return;
      setField(formElement, "id", id);
      const mappings = {
        providers: [["display_name","display_name"],["kind","kind"],["enabled","enabled"],["config","config",true]],
        models: [["provider_id","provider_id"],["display_name","display_name"],["enabled","enabled"],["capabilities","capabilities",true],["metadata","metadata",true]],
        agents: [["adapter_type","adapter_type"],["provider_id","provider_id"],["model_id","model_id"],["role","role"],["description","description"],["enabled","enabled"],["capabilities","capabilities",true],["boundaries","boundaries",true],["config","config",true]],
        roles: [["mode","mode"],["agent_id","agent_id"],["model_id","model_id"],["locked","locked"],["constraints","constraints",true]],
        settings: [["value","value",true]],
        budgets: [["scope","scope_type"],["scope_key","scope_key"],["metric","metric"],["warning","warning_limit"],["hard","hard_limit"],["currency","currency"]]
      };
      mappings[resource].forEach(([field, source, asJson]) => setField(formElement, field, item[source], asJson));
      formElement.closest("details").open = true;
      formElement.scrollIntoView({behavior: "smooth", block: "start"});
      message.textContent = `Editing local ${resource.slice(0, -1)} “${id}”.`;
    }
    function render(state) {
      currentState = state;
      const r = state.registry, ledger = state.ledger;
      const interop = state.interoperability;
      const approvalCenter = state.approval_center || [];
      const centerTable = approvalCenter.length
        ? `<div class="table-wrap"><table><thead><tr><th>Requested</th><th>Kind</th><th>Action</th><th>Resource</th><th>Scope SHA-256</th><th>Scope</th><th>Status</th><th>Decision</th><th>Consume</th></tr></thead><tbody>${approvalCenter.map(item => `<tr><td>${escapeHtml(item.requested_at)}</td><td>${escapeHtml(item.kind)}</td><td>${escapeHtml(item.action)}</td><td>${escapeHtml(item.resource)}</td><td><code>${escapeHtml(item.scope_sha256)}</code></td><td><details><summary>Inspect local scope</summary><code>${json(item.scope)}</code></details></td><td>${escapeHtml(item.status)}</td><td>${item.status === "pending" ? `<button class="center-approval-action" type="button" data-kind="${escapeHtml(item.kind)}" data-id="${escapeHtml(item.id)}" data-scope="${escapeHtml(item.scope_sha256)}" data-decision="approve">Approve exact scope</button> <button class="center-approval-action" type="button" data-kind="${escapeHtml(item.kind)}" data-id="${escapeHtml(item.id)}" data-decision="reject">Reject</button>` : ""}</td><td>${item.kind === "backup_restore" && item.status === "approved" ? `<button class="backup-restore" type="button" data-id="${escapeHtml(item.id)}">Restore once</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`
        : "<p class='small'>No approval records.</p>";
      const backupItems = state.backups.items || [];
      const backupTable = backupItems.length
        ? `<div class="table-wrap"><table><thead><tr><th>Created</th><th>Id</th><th>Reason</th><th>Database bytes</th><th>Artifacts</th><th>Database SHA-256</th><th>Restore</th></tr></thead><tbody>${backupItems.map(item => `<tr><td>${escapeHtml(item.created_at)}</td><td><code>${escapeHtml(item.id)}</code></td><td>${escapeHtml(item.manifest.reason)}</td><td>${escapeHtml(item.manifest.database.bytes)}</td><td>${escapeHtml(item.manifest.artifact_count)}</td><td><code>${escapeHtml(item.manifest.database.sha256)}</code></td><td><button class="backup-request" type="button" data-id="${escapeHtml(item.id)}">Request exact restore</button></td></tr>`).join("")}</tbody></table></div>`
        : "<p class='small'>No local backups.</p>";
      const runOptions = state.runs.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.created_at)} · ${escapeHtml(item.status)} · ${escapeHtml(item.goal)}</option>`).join("");
      const approvalTable = interop.approvals.length
        ? `<div class="table-wrap"><table><thead><tr><th>Requested</th><th>Endpoint</th><th>Action</th><th>Resource</th><th>Arguments</th><th>Status</th><th>Decision</th></tr></thead><tbody>${interop.approvals.map(item => `<tr><td>${escapeHtml(item.requested_at)}</td><td>${escapeHtml(item.endpoint_id)}</td><td>${escapeHtml(item.action)}</td><td>${escapeHtml(item.resource)}</td><td><code>${json(item.arguments)}</code></td><td>${escapeHtml(item.status)}</td><td>${item.status === "pending" ? `<button class="approval-action" type="button" data-id="${escapeHtml(item.id)}" data-decision="approve">Approve once</button> <button class="approval-action" type="button" data-id="${escapeHtml(item.id)}" data-decision="reject">Reject</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`
        : "<p class='small'>No interoperability approvals.</p>";
      app.innerHTML = `
        <h2>Local state</h2>
        <p><strong>${escapeHtml(state.project.name)}</strong> — ${escapeHtml(state.project.state)}. External calls: ${escapeHtml(state.project.external_calls)}.</p>
        <div class="grid">
          <section><h3>Usage total</h3><pre><code>${json(ledger.summary.total)}</code></pre></section>
          <section><h3>Persisted observations</h3><p>${r.discovery.length} discovery/health record(s), shown below. Refreshing this page does not rescan or probe.</p></section>
        </div>
        <h2>Approval center</h2>
        <p class="small">Approval and consumption remain separate. This page delegates to the same persisted single-use checks as the CLI and never invokes, merges, discards or restores merely by refreshing.</p>
        ${centerTable}
        <h2>Workspace evidence</h2>
        <h3>Leases and permissions</h3>
        ${table(state.workspaces.leases, [{key:"updated_at",label:"Updated"},{key:"id",label:"Lease"},{key:"agent_id",label:"Agent"},{key:"status",label:"Status"},{key:"target_branch",label:"Target"},{key:"base_sha",label:"Base SHA"},{key:"permissions",label:"Permissions",json:true}])}
        <h3>Bounded workspace evidence</h3>
        ${table(state.workspaces.evidence, [{key:"created_at",label:"Recorded"},{key:"lease_id",label:"Lease"},{key:"kind",label:"Kind"},{key:"status",label:"Status"},{key:"exit_code",label:"Exit"},{key:"duration_ms",label:"Duration ms"},{key:"stdout_bytes",label:"Stdout bytes"},{key:"stderr_bytes",label:"Stderr bytes"},{key:"stdout_text",label:"Bounded stdout"},{key:"stderr_text",label:"Bounded stderr"},{key:"metadata",label:"Metadata",json:true}])}
        <h2>Repair evidence</h2>
        ${table(state.repairs.sessions, [{key:"updated_at",label:"Updated"},{key:"id",label:"Session"},{key:"lease_id",label:"Lease"},{key:"writer_agent_id",label:"Writer"},{key:"reviewer_agent_id",label:"Reviewer"},{key:"status",label:"Status"},{key:"iteration_count",label:"Iterations"},{key:"policy",label:"Limits",json:true}])}
        ${state.repairs.details.length ? `<details><summary>Inspect bounded iteration and event evidence</summary><pre><code>${json(state.repairs.details)}</code></pre></details>` : ""}
        <h2>Objective evaluation evidence</h2>
        ${table(state.evaluations, [{key:"created_at",label:"Created"},{key:"id",label:"Evaluation"},{key:"agent_family",label:"Family"},{key:"agent_id",label:"Agent"},{key:"case_id",label:"Case"},{key:"status",label:"Status"},{key:"case",label:"Assertions and hashes",json:true}])}
        <h2>Run comparison</h2>
        ${state.runs.length >= 2 ? `<div class="grid"><label>Left run<select id="compare-left">${runOptions}</select></label><label>Right run<select id="compare-right">${runOptions}</select></label></div><button id="compare-runs" type="button">Compare local evidence</button><div id="comparison-result">${state.run_comparison ? `<pre><code>${json(state.run_comparison)}</code></pre>` : ""}</div>` : "<p class='small'>At least two runs are required.</p>"}
        <h2>Local backup and restore</h2>
        <p class="small">Database-only is the privacy-safe default. Artifact inclusion is explicit. Worktrees, repositories, credentials and environment files are always excluded. Restore requires a separately approved exact digest and creates a pre-restore safety backup.</p>
        <button class="backup-create" type="button" data-artifacts="false">Create database backup</button>
        <button class="backup-create" type="button" data-artifacts="true">Create database + registered Artifacts backup</button>
        ${backupTable}
        <h2>Providers</h2>
        ${table(r.providers, [{key:"id",label:"Id"},{key:"display_name",label:"Name"},{key:"kind",label:"Kind"},{key:"enabled",label:"Enabled"},{key:"source",label:"Source"},{key:"config",label:"Safe config",json:true}], "providers")}
        ${form("Add or edit Provider", "", formField("Display name", "display_name", "") + formField("Kind", "kind", "custom") + formField("Enabled", "enabled", true, "checkbox") + formField("Config JSON", "config", "{}", "textarea"), "providers")}
        <h2>Models</h2>
        ${table(r.models, [{key:"id",label:"Id"},{key:"provider_id",label:"Provider"},{key:"display_name",label:"Name"},{key:"enabled",label:"Enabled"},{key:"capabilities",label:"Capabilities",json:true},{key:"source",label:"Source"}], "models")}
        ${form("Add or edit Model", "", formField("Provider id", "provider_id", "") + formField("Display name", "display_name", "") + formField("Enabled", "enabled", true, "checkbox") + formField("Capabilities JSON", "capabilities", "[]", "textarea") + formField("Metadata JSON", "metadata", "{}", "textarea"), "models")}
        <h2>Agents</h2>
        ${table(r.agents, [{key:"id",label:"Id"},{key:"adapter_type",label:"Adapter"},{key:"provider_id",label:"Provider"},{key:"model_id",label:"Model"},{key:"role",label:"Role"},{key:"enabled",label:"Enabled"},{key:"source",label:"Source"}], "agents")}
        ${form("Add or edit Agent", "", formField("Adapter type", "adapter_type", "mock") + formField("Provider id", "provider_id", "") + formField("Model id", "model_id", "") + formField("Role", "role", "") + formField("Description", "description", "", "textarea") + formField("Enabled", "enabled", true, "checkbox") + formField("Capabilities JSON", "capabilities", "[]", "textarea") + formField("Boundaries JSON", "boundaries", "[]", "textarea") + formField("Config JSON", "config", "{}", "textarea"), "agents")}
        <h2>Roles and deterministic routing</h2>
        ${table(r.roles, [{key:"role_key",label:"Role"},{key:"mode",label:"Mode"},{key:"agent_id",label:"Preferred agent"},{key:"model_id",label:"Preferred model"},{key:"locked",label:"Locked"},{key:"constraints",label:"Constraints",json:true},{key:"source",label:"Source"}], "roles")}
        ${form("Add or edit Role", "", formField("Mode (manual, auto, hybrid)", "mode", "manual") + formField("Agent id", "agent_id", "") + formField("Model id", "model_id", "") + formField("Locked", "locked", false, "checkbox") + formField("Constraints JSON", "constraints", "{}", "textarea"), "roles")}
        <h3>Routing explanations</h3>
        ${table(state.routing, [{key:"created_at",label:"Recorded"},{key:"role_key",label:"Role"},{key:"status",label:"Status"},{key:"reason_code",label:"Reason"},{key:"selected_agent_id",label:"Selected agent"},{key:"rejected_candidates",label:"Rejected evidence",json:true}])}
        <h2>Application settings</h2>
        ${table(Object.entries(r.settings).map(([key, item]) => ({key, ...item})), [{key:"key",label:"Key"},{key:"value",label:"Value",json:true},{key:"source",label:"Source"},{key:"updated_at",label:"Updated"}], "settings")}
        ${form("Add or edit Application Setting", "", formField("Value JSON", "value", '""', "textarea"), "settings")}
        <h2>Discovery and health observations</h2>
        ${table(r.discovery, [{key:"id",label:"Id"},{key:"agent_id",label:"Agent"},{key:"executable_status",label:"Executable"},{key:"authentication_status",label:"Auth"},{key:"permission_status",label:"Permission"},{key:"connectivity_status",label:"Connectivity"},{key:"checked_at",label:"Checked"}])}
        <h3>Configured Adapter capabilities</h3>
        ${table(state.adapter_capabilities, [{key:"agent_id",label:"Agent"},{key:"adapter",label:"Adapter"},{key:"discovery",label:"Discovery support",json:true},{key:"billing",label:"Billing support",json:true}])}
        <h2>Usage, costs, budgets, and balances</h2>
        <h3>Budget policies</h3>
        ${table(ledger.budgets, [{key:"id",label:"Id"},{key:"scope_type",label:"Scope"},{key:"scope_key",label:"Scope key"},{key:"metric",label:"Metric"},{key:"warning_limit",label:"Warning"},{key:"hard_limit",label:"Hard"},{key:"currency",label:"Currency"},{key:"source",label:"Source"}], "budgets")}
        ${form("Add or edit Budget Policy", "", formField("Scope (project, run, role)", "scope", "project") + formField("Scope key", "scope_key", state.project.name) + formField("Metric (tokens, cost)", "metric", "tokens") + formField("Warning limit", "warning", "") + formField("Hard limit", "hard", "") + formField("Currency for cost", "currency", ""), "budgets")}
        <h3>Budget alerts</h3>${table(ledger.alerts, [{key:"created_at",label:"Recorded"},{key:"policy_id",label:"Policy"},{key:"level",label:"Level"},{key:"metric",label:"Metric"},{key:"observed_value",label:"Observed"},{key:"limit_value",label:"Limit"}])}
        <h3>Recent usage events</h3>${table(ledger.events, [{key:"created_at",label:"Recorded"},{key:"agent_id",label:"Agent"},{key:"role",label:"Role"},{key:"status",label:"Status"},{key:"total_tokens",label:"Tokens"},{key:"token_source",label:"Token source"},{key:"cost_amount",label:"Cost"},{key:"cost_currency",label:"Currency"},{key:"cost_source",label:"Cost source"}])}
        <h3>Provider balance snapshots</h3>${table(ledger.balance_snapshots, [{key:"checked_at",label:"Checked"},{key:"provider_id",label:"Provider"},{key:"amount",label:"Amount"},{key:"currency",label:"Currency"},{key:"source",label:"Source"}])}
        <h2>Artifact provenance</h2>
        ${table(state.artifacts, [{key:"run_id",label:"Run"},{key:"name",label:"Artifact"},{key:"sha256",label:"SHA-256"},{key:"created_at",label:"Created"},{key:"provenance",label:"Provenance",json:true}])}
        <h2>Persistent and remote interoperability</h2>
        <p class="small">These are local records. Listing a configured endpoint does not connect to it. Real invocation additionally requires <code>invoke_enabled=true</code>; MCP tool calls require a separate single-use approval.</p>
        <h3>Endpoints and remote identities</h3>
        ${table(interop.endpoints, [{key:"id",label:"Id"},{key:"protocol",label:"Protocol"},{key:"transport",label:"Transport"},{key:"display_name",label:"Name"},{key:"protocol_version",label:"Version"},{key:"auth_type",label:"Auth"},{key:"auth_env",label:"Credential env"},{key:"enabled",label:"Enabled"}])}
        <h3>Sessions</h3>
        ${table(interop.sessions, [{key:"updated_at",label:"Updated"},{key:"endpoint_id",label:"Endpoint"},{key:"agent_id",label:"Agent"},{key:"protocol",label:"Protocol"},{key:"remote_session_id",label:"Remote session"},{key:"status",label:"Status"},{key:"metadata",label:"Metadata",json:true}])}
        <h3>Human approvals</h3>
        ${approvalTable}
        <h3>Recent protocol events</h3>
        ${table(interop.events, [{key:"created_at",label:"Recorded"},{key:"session_id",label:"Session"},{key:"direction",label:"Direction"},{key:"method",label:"Method"},{key:"status",label:"Status"},{key:"payload",label:"Payload",json:true}])}
      `;
      bindForms();
    }
    async function refresh() {
      try {
        const response = await fetch("/api/state", {cache: "no-store"});
        if (!response.ok) throw new Error("Unable to read local state");
        render(await response.json());
        message.textContent = "";
      } catch (error) {
        app.textContent = error.message;
      }
    }
    document.querySelector("#refresh").addEventListener("click", refresh);
    refresh();
  </script>
</body>
</html>
"""
