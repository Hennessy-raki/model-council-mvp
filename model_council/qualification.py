from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any

from .supervisor import (
    CANONICAL_LIFECYCLE_CHECKS,
    LAUNCH_MODES,
    TRANSPORTS,
)


IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
PERSONAL_PATH_RE = re.compile(
    r"(?i)(?:[a-z]:[\\/]+users[\\/]+[^\\/]+|/(?:home|users)/[^/]+)"
)
CREDENTIAL_VALUE_RE = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:sk|pk|rk)-[a-z0-9_-]{8,}|api[_ -]?key\s*[:=])"
)
SENSITIVE_KEY_PARTS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "password",
    "secret",
    "token",
}
TOKEN_METRIC_KEYS = {
    "max_input_tokens",
    "max_output_tokens",
    "max_total_tokens",
}
REQUIRED_APPROVAL_LADDER = (
    "preflight_review",
    "external_scope_approval",
    "execution_approval",
)
REQUIRED_CONTEXT_EXCLUSIONS = (
    "repository_context",
    "private_project_content",
    "worktree",
    "workspace_write",
    "prompt_instance",
    "artifact_body",
)
REQUIRED_EVIDENCE_POLICY = (
    "storage",
    "retain_raw_output",
    "retain_stdout",
    "retain_stderr",
    "retain_prompt",
    "retain_response",
)


class QualificationPreflightError(ValueError):
    """Raised only when the candidate cannot be parsed as a JSON object."""


class QualificationPreflightService:
    """Pure local validation for a future Agent-qualification scope.

    This service intentionally has no store, process, Adapter or network
    dependency. It cannot grant execution authority and does not retain a
    submitted declaration.
    """

    def evaluate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(candidate, dict):
            raise QualificationPreflightError("qualification candidate must be an object")

        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        self._reject_sensitive_material(candidate, blockers)
        self._reject_unknown_top_level_fields(candidate, blockers)

        identity = self._identity(candidate, blockers)
        launch = self._launch(candidate, blockers)
        lifecycle_checks = self._lifecycle_checks(candidate, blockers)
        permissions = self._permissions(candidate, blockers)
        context = self._context(candidate, blockers)
        limits = self._limits(candidate, blockers)
        approval_ladder = self._approval_ladder(candidate, blockers)
        evidence = self._evidence(candidate, blockers)
        execution_authorized = candidate.get("execution_authorized")
        if execution_authorized is not False:
            self._block(
                blockers,
                "execution_authority_must_be_false",
                "execution_authorized",
            )

        if blockers:
            return {
                "status": "blocked",
                "execution_authorized": False,
                "blockers": blockers,
                "warnings": warnings,
                "normalized_scope": None,
                "scope_sha256": None,
            }

        scope = {
            "kind": "offline_agent_qualification_preflight",
            "identity": identity,
            "launch": launch,
            "lifecycle_checks": lifecycle_checks,
            "permissions": permissions,
            "context_exclusions": context,
            "limits": limits,
            "approval_ladder": approval_ladder,
            "evidence_policy": evidence,
            "execution_authorized": False,
        }
        return {
            "status": "eligible_for_separate_review",
            "execution_authorized": False,
            "blockers": [],
            "warnings": warnings,
            "normalized_scope": scope,
            "scope_sha256": self._digest(scope),
        }

    def _reject_sensitive_material(
        self,
        value: Any,
        blockers: list[dict[str, str]],
        path: str = "candidate",
    ) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                normalized = key_text.lower().replace("-", "_")
                if self._is_sensitive_key(normalized):
                    self._block(blockers, "sensitive_field_forbidden", path)
                self._reject_sensitive_material(item, blockers, f"{path}.{key_text}")
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                self._reject_sensitive_material(item, blockers, f"{path}[{index}]")
            return
        if not isinstance(value, str):
            return
        if PERSONAL_PATH_RE.search(value):
            self._block(blockers, "personal_path_forbidden", path)
        if CREDENTIAL_VALUE_RE.search(value):
            self._block(blockers, "credential_value_forbidden", path)
        if "runtime-board14" in value.lower():
            self._block(blockers, "protected_runtime_reference_forbidden", path)

    def _reject_unknown_top_level_fields(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> None:
        allowed = {
            "agent_id",
            "model_id",
            "provider_id",
            "launch_mode",
            "transport",
            "lifecycle_checks",
            "permissions",
            "context",
            "limits",
            "approval_ladder",
            "evidence",
            "execution_authorized",
        }
        for key in candidate:
            if key not in allowed:
                self._block(blockers, "unsupported_candidate_field", "candidate")

    def _identity(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, str]:
        identity: dict[str, str] = {}
        for key in ("agent_id", "model_id", "provider_id"):
            value = candidate.get(key)
            if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
                self._block(blockers, "invalid_identity_identifier", key)
            else:
                identity[key] = value
        return identity

    def _launch(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, str]:
        launch_mode = candidate.get("launch_mode")
        transport = candidate.get("transport")
        if launch_mode not in LAUNCH_MODES:
            self._block(blockers, "unsupported_launch_mode", "launch_mode")
        if transport not in TRANSPORTS:
            self._block(blockers, "unsupported_transport", "transport")
        if launch_mode == "manual" and transport != "manual":
            self._block(blockers, "manual_launch_requires_manual_transport", "transport")
        if transport == "manual" and launch_mode != "manual":
            self._block(blockers, "manual_transport_requires_manual_launch", "launch_mode")
        return {
            "launch_mode": str(launch_mode),
            "transport": str(transport),
        }

    def _lifecycle_checks(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> list[str]:
        value = candidate.get("lifecycle_checks")
        if not isinstance(value, list) or tuple(value) != CANONICAL_LIFECYCLE_CHECKS:
            self._block(blockers, "canonical_lifecycle_checks_required", "lifecycle_checks")
            return []
        return list(CANONICAL_LIFECYCLE_CHECKS)

    def _permissions(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> list[str]:
        value = candidate.get("permissions")
        if value != ["read_only"]:
            self._block(blockers, "read_only_permission_required", "permissions")
            return []
        return ["read_only"]

    def _context(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, bool]:
        value = candidate.get("context")
        if not isinstance(value, dict):
            self._block(blockers, "context_exclusions_required", "context")
            return {}
        if set(value) != set(REQUIRED_CONTEXT_EXCLUSIONS):
            self._block(blockers, "exact_context_exclusions_required", "context")
        normalized: dict[str, bool] = {}
        for key in REQUIRED_CONTEXT_EXCLUSIONS:
            if value.get(key) is not False:
                self._block(blockers, "private_context_must_be_excluded", f"context.{key}")
            normalized[key] = False
        return normalized

    def _limits(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, Any]:
        value = candidate.get("limits")
        required = {
            "max_input_tokens",
            "max_output_tokens",
            "max_total_tokens",
            "max_total_cost",
            "currency",
            "max_duration_seconds",
            "max_attempts",
            "retry_on_failure",
        }
        if not isinstance(value, dict) or set(value) != required:
            self._block(blockers, "exact_limits_required", "limits")
            return {}
        integers: dict[str, int] = {}
        for key in (
            "max_input_tokens",
            "max_output_tokens",
            "max_total_tokens",
            "max_duration_seconds",
            "max_attempts",
        ):
            item = value.get(key)
            if not isinstance(item, int) or isinstance(item, bool) or item < 1:
                self._block(blockers, "positive_limit_required", f"limits.{key}")
            else:
                integers[key] = item
        if (
            {"max_input_tokens", "max_output_tokens", "max_total_tokens"} <= integers.keys()
            and integers["max_total_tokens"]
            < integers["max_input_tokens"] + integers["max_output_tokens"]
        ):
            self._block(blockers, "total_token_limit_incompatible", "limits.max_total_tokens")
        if integers.get("max_attempts") != 1:
            self._block(blockers, "single_attempt_required", "limits.max_attempts")
        if value.get("retry_on_failure") is not False:
            self._block(blockers, "retry_must_be_disabled", "limits.retry_on_failure")
        currency = value.get("currency")
        if not isinstance(currency, str) or not CURRENCY_RE.fullmatch(currency):
            self._block(blockers, "currency_required", "limits.currency")
        amount = value.get("max_total_cost")
        try:
            decimal = Decimal(str(amount))
            if not decimal.is_finite() or decimal <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            self._block(blockers, "positive_cost_limit_required", "limits.max_total_cost")
            decimal = Decimal("0")
        return {
            **integers,
            "max_total_cost": format(decimal, "f"),
            "currency": currency,
            "retry_on_failure": False,
        }

    def _approval_ladder(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> list[str]:
        value = candidate.get("approval_ladder")
        if value != list(REQUIRED_APPROVAL_LADDER):
            self._block(blockers, "exact_approval_ladder_required", "approval_ladder")
            return []
        return list(REQUIRED_APPROVAL_LADDER)

    def _evidence(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, Any]:
        value = candidate.get("evidence")
        if not isinstance(value, dict) or set(value) != set(REQUIRED_EVIDENCE_POLICY):
            self._block(blockers, "exact_evidence_policy_required", "evidence")
            return {}
        if value.get("storage") != "runtime_only":
            self._block(blockers, "runtime_only_evidence_required", "evidence.storage")
        for key in REQUIRED_EVIDENCE_POLICY[1:]:
            if value.get(key) is not False:
                self._block(blockers, "raw_evidence_retention_forbidden", f"evidence.{key}")
        return {
            "storage": "runtime_only",
            "retain_raw_output": False,
            "retain_stdout": False,
            "retain_stderr": False,
            "retain_prompt": False,
            "retain_response": False,
        }

    @staticmethod
    def _block(blockers: list[dict[str, str]], code: str, field: str) -> None:
        item = {"code": code, "field": field}
        if item not in blockers:
            blockers.append(item)

    @staticmethod
    def _is_sensitive_key(normalized: str) -> bool:
        if normalized in TOKEN_METRIC_KEYS:
            return False
        return any(part in normalized for part in SENSITIVE_KEY_PARTS)

    @staticmethod
    def _digest(scope: dict[str, Any]) -> str:
        serialized = json.dumps(
            scope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(serialized.encode("utf-8")).hexdigest()
