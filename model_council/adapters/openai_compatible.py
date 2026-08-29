from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import AgentAdapter
from ..types import (
    AgentRequest,
    AgentResponse,
    AuthenticationStatus,
    ConnectivityStatus,
    MeasurementSource,
    PermissionStatus,
)


class OpenAICompatibleAdapter(AgentAdapter):
    def __init__(self, card, settings: dict[str, Any]):
        super().__init__(card)
        self.base_url = str(settings.get("base_url", "")).rstrip("/")
        self.model = str(settings.get("model", ""))
        self.api_key_env = str(settings.get("api_key_env", "OPENAI_API_KEY"))
        self.api_style = str(settings.get("api_style", "responses"))
        self.timeout_seconds = int(settings.get("timeout_seconds", 180))
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
        if not self.base_url or not self.model:
            raise ValueError(
                f"OpenAI-compatible agent {card.name!r} requires base_url and model"
            )
        if self.api_style not in {"responses", "chat_completions"}:
            raise ValueError("api_style must be responses or chat_completions")

    def invoke(self, request: AgentRequest) -> AgentResponse:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"environment variable {self.api_key_env!r} is not configured"
            )
        prompt = self.render_prompt(request)
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
        if not content:
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
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"HTTP {exc.code} from {request.full_url}: {detail[-2000:]}"
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
                return str(choices[0].get("message", {}).get("content", "")).strip()
            return ""
        if isinstance(data.get("output_text"), str):
            return data["output_text"].strip()
        texts: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return "\n".join(texts).strip()
