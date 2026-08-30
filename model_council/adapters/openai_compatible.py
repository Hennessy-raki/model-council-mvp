from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from .base import AgentAdapter
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
    MeasurementSource,
    PermissionStatus,
)


class OpenAICompatibleAdapter(AgentAdapter):
    def __init__(
        self,
        card,
        settings: dict[str, Any],
        outbound_context: OutboundContextService | None = None,
    ):
        super().__init__(card)
        self.settings = settings
        self.base_url = str(settings.get("base_url", "")).rstrip("/")
        self.model = str(settings.get("model", ""))
        self.api_key_env = str(settings.get("api_key_env", "OPENAI_API_KEY"))
        self.api_style = str(settings.get("api_style", "responses"))
        self.timeout_seconds = int(settings.get("timeout_seconds", 180))
        self.max_response_bytes = int(settings.get("max_response_bytes", 16384))
        self.balance_endpoint = str(settings.get("balance_endpoint", "")).strip()
        self.balance_amount_field = str(
            settings.get("balance_amount_field", "balance")
        )
        self.balance_currency_field = str(
            settings.get("balance_currency_field", "")
        )
        self.balance_currency = str(
            settings.get("balance_currency", "USD")
        ).upper()
        self.invoke_enabled = bool(settings.get("invoke_enabled", False))
        context_settings = settings.get("outbound_context")
        self.outbound_policy = (
            OutboundContextPolicy.from_settings(context_settings)
            if isinstance(context_settings, dict)
            else None
        )
        self.outbound_source = (
            str(context_settings["source"])
            if isinstance(context_settings, dict)
            else None
        )
        self.outbound_context = outbound_context
        self.endpoint_id = f"agent:{card.name}"
        if not self.base_url or not self.model:
            raise ValueError(
                f"OpenAI-compatible agent {card.name!r} requires base_url and model"
            )
        if self.api_style not in {"responses", "chat_completions"}:
            raise ValueError("api_style must be responses or chat_completions")

    def invoke(self, request: AgentRequest) -> AgentResponse:
        if not self.invoke_enabled:
            raise RuntimeError(
                f"OpenAI-compatible agent {self.card.name!r} requires "
                "invoke_enabled=true"
            )
        if (
            not self.outbound_context
            or not self.outbound_policy
            or not self.outbound_source
        ):
            raise RuntimeError(
                f"OpenAI-compatible agent {self.card.name!r} requires an exact "
                "outbound_context policy and local approval service"
            )
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"environment variable {self.api_key_env!r} is not configured"
            )
        prompt = self.render_outbound_prompt(request)
        transport_context = self.outbound_transport_context()
        manifest_id = request.metadata.get("outbound_context_manifest_id")
        if manifest_id:
            self.outbound_context.require_approved(
                manifest_id=str(manifest_id),
                endpoint_id=self.endpoint_id,
                prompt=prompt,
                transport_context=transport_context,
            )
        else:
            manifest = self.outbound_context.prepare(
                endpoint_id=self.endpoint_id,
                agent_id=self.card.name,
                request=request,
                prompt=prompt,
                source=self.outbound_source,
                policy=self.outbound_policy,
                transport_context=transport_context,
            )
            raise OutboundContextApprovalRequired(manifest["id"])
        if self.api_style == "responses":
            url = f"{self.base_url}/responses"
            payload = {
                "model": self.model,
                "input": prompt,
            }
        else:
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt()},
                    {"role": "user", "content": prompt},
                ],
            }
        raw = json.dumps(payload).encode("utf-8")
        http_request = Request(
            url,
            data=raw,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        data = self._read_json(http_request)

        content = self._extract_text(data)
        if not content.strip():
            raise RuntimeError(f"model {self.model!r} returned no text")
        metadata: dict[str, Any] = {"model": self.model}
        usage = data.get("usage")
        if isinstance(usage, dict):
            metadata["usage"] = usage
            metadata["usage_source"] = MeasurementSource.PROVIDER_REPORTED.value
        cost = data.get("cost")
        if isinstance(cost, dict):
            metadata["cost"] = cost
        return AgentResponse(content=content, metadata=metadata)

    def render_outbound_prompt(self, request: AgentRequest) -> str:
        capabilities = ", ".join(self.card.capabilities) or "none declared"
        boundaries = "\n".join(
            f"- {item}" for item in self.card.boundaries
        ) or "- none declared"
        artifacts = "\n".join(
            (
                f"- {item.name} "
                f"(media_type={item.media_type}, sha256={item.sha256})"
            )
            for item in request.artifacts
        ) or "- none"
        return (
            f"Role: {self.card.role}\n"
            f"Responsibility: {self.card.description}\n"
            f"Capabilities: {capabilities}\n"
            f"Boundaries:\n{boundaries}\n"
            "Follow only the assigned instruction. Distinguish facts, "
            "inferences, and unknowns.\n\n"
            f"Goal:\n{request.goal}\n\n"
            f"Instruction:\n{request.instruction}\n\n"
            f"Context:\n{request.context or 'none'}\n\n"
            f"Artifact references:\n{artifacts}\n"
        )

    def diagnose(self) -> dict[str, Any]:
        return {
            "ok": bool(os.environ.get(self.api_key_env)),
            "adapter": type(self).__name__,
            "agent": self.card.name,
            "base_url": self.base_url,
            "model": self.model,
            "api_style": self.api_style,
            "api_key_env": self.api_key_env,
            "api_key_present": bool(os.environ.get(self.api_key_env)),
            "invoke_enabled": self.invoke_enabled,
        }

    def outbound_transport_context(self) -> dict[str, Any]:
        path = (
            "/responses"
            if self.api_style == "responses"
            else "/chat/completions"
        )
        payload_fields = (
            ["model", "input"]
            if self.api_style == "responses"
            else ["model", "messages"]
        )
        return {
            "adapter": "openai_compatible",
            "base_url": self.base_url,
            "request_url": f"{self.base_url}{path}",
            "api_style": self.api_style,
            "model": self.model,
            "payload_fields": payload_fields,
            "headers": {
                "Authorization": "Bearer <environment-only>",
                "Content-Type": "application/json",
            },
            "credential_env": self.api_key_env,
            "max_response_bytes": self.max_response_bytes,
        }

    def discovery_capabilities(self) -> dict[str, bool]:
        return {
            "executable_check": False,
            "authentication_check": True,
            "permission_check": True,
            "model_discovery": True,
            "connectivity_test": True,
        }

    def check_authentication(self) -> dict[str, Any]:
        present = bool(os.environ.get(self.api_key_env))
        return {
            "status": (
                AuthenticationStatus.CONFIGURED.value
                if present
                else AuthenticationStatus.MISSING.value
            ),
            "details": {
                "check": "environment",
                "api_key_env": self.api_key_env,
            },
        }

    def check_permissions(self) -> dict[str, Any]:
        return {
            "status": PermissionStatus.NOT_APPLICABLE.value,
            "details": {"reason": "remote API permissions are provider-managed"},
        }

    def discover_models(self) -> list[dict[str, Any]]:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"environment variable {self.api_key_env!r} is not configured"
            )
        request = Request(
            f"{self.base_url}/models",
            method="GET",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        data = self._read_json(request)
        values = data.get("data", data.get("models", []))
        if not isinstance(values, list):
            raise RuntimeError("model discovery response did not contain a list")
        result = []
        seen: set[str] = set()
        for item in values:
            model_id = item.get("id") if isinstance(item, dict) else item
            if model_id is None:
                continue
            model_id = str(model_id).strip()
            if model_id and model_id not in seen:
                seen.add(model_id)
                result.append({"id": model_id, "source": "provider"})
        return result

    def connectivity_probe(self) -> dict[str, Any]:
        try:
            models = self.discover_models()
        except Exception as exc:
            return {
                "status": ConnectivityStatus.FAILED.value,
                "details": {"error": type(exc).__name__},
            }
        return {
            "status": ConnectivityStatus.PASSED.value,
            "details": {
                "transport": "models_endpoint",
                "model_count": len(models),
            },
        }

    def billing_capabilities(self) -> dict[str, bool]:
        return {"provider_balance": bool(self.balance_endpoint)}

    def provider_balance(self) -> dict[str, Any]:
        if not self.balance_endpoint:
            return super().provider_balance()
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"environment variable {self.api_key_env!r} is not configured"
            )
        url = (
            self.balance_endpoint
            if self.balance_endpoint.startswith(("http://", "https://"))
            else f"{self.base_url}/{self.balance_endpoint.lstrip('/')}"
        )
        request = Request(
            url,
            method="GET",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        data = self._read_json(request)
        amount = self._field_value(data, self.balance_amount_field)
        currency = (
            self._field_value(data, self.balance_currency_field)
            if self.balance_currency_field
            else self.balance_currency
        )
        if amount is None:
            raise RuntimeError(
                f"balance response lacks field {self.balance_amount_field!r}"
            )
        return {
            "amount": str(amount),
            "currency": str(currency or self.balance_currency).upper(),
            "source": MeasurementSource.PROVIDER_REPORTED.value,
            "details": {"endpoint_supported": True},
        }

    def _read_json(self, request: Request) -> dict[str, Any]:
        try:
            with _NO_REDIRECT_OPENER.open(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise RuntimeError(
                        f"response from {request.full_url} exceeded "
                        f"{self.max_response_bytes} bytes"
                    )
                data = json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = exc.read(self.max_response_bytes + 1)
            finally:
                exc.close()
            detail_text = detail[: self.max_response_bytes].decode(
                "utf-8",
                errors="replace",
            )
            raise RuntimeError(
                f"HTTP {exc.code} from {request.full_url}: "
                f"{detail_text[-2000:]}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"cannot reach {request.full_url}: {exc.reason}"
            ) from exc
        if not isinstance(data, dict):
            raise RuntimeError("provider response was not a JSON object")
        return data

    @staticmethod
    def _field_value(data: dict[str, Any], path: str) -> Any:
        value: Any = data
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    def _extract_text(self, data: dict[str, Any]) -> str:
        if self.api_style == "chat_completions":
            choices = data.get("choices") or []
            if choices:
                return str(choices[0].get("message", {}).get("content", ""))
            return ""
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        texts: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return "\n".join(texts)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler())
