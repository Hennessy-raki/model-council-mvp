from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any

from .qualification import (
    ABSOLUTE_PATH_RE,
    CREDENTIAL_VALUE_RE,
    CURRENCY_RE,
    IDENTIFIER_RE,
    PERSONAL_PATH_RE,
)
from .supervisor import (
    CANONICAL_LIFECYCLE_CHECKS,
    LAUNCH_MODES,
    TRANSPORTS,
)


PACKAGE_KIND = "offline_agent_qualification_authorization_package"
PACKAGE_VERSION = 1

# The package must describe what the operator would authorize without storing
# the machine values themselves. A working directory is referenced by
# environment-variable name and by category, never by value.
ENV_VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
PATH_CATEGORIES = (
    "synthetic_workspace",
    "system_temp",
    "dedicated_operator_directory",
)
PERMISSIONS = ["read_only"]
TOOLS = ["none"]
CONTEXT_INCLUSIONS = [
    "synthetic_task_text",
    "transport_metadata",
]
CONTEXT_EXCLUSIONS = [
    "repository_context",
    "private_project_content",
    "worktree",
    "workspace_write",
    "artifact_body",
    "environment_file",
]
# Distinct from the approval ladder: the ladder says which human approvals are
# required; single_use says the execution authority, once granted, is spent.
SINGLE_USE = {
    "consume_once": True,
    "reusable": False,
    "replay_forbidden": True,
}
REQUIRED_APPROVAL_LADDER = (
    "authorization_review",
    "execution_approval",
)
REQUIRED_EVIDENCE_KINDS = (
    "process",
    "login",
    "actual_model",
    "permission",
    "version",
    "protocol",
    "connectivity",
)

STATUS_USER_CONFIRMATION_REQUIRED = "user_confirmation_required"
STATUS_ELIGIBLE_FOR_REVIEW = "eligible_for_separate_review"
STATUS_BLOCKED = "blocked"


class AuthorizationPackageError(ValueError):
    """Raised only when the candidate cannot be parsed as a JSON object."""


class AuthorizationPackageService:
    """Build one deterministic, privacy-safe real-Agent authorization request.

    The package is the reviewable handoff between local readiness metadata and a
    future exact user authorization. It never starts a process, loads runtime
    state, invokes an Adapter or contacts an endpoint, and it cannot grant
    execution authority. A package that lacks real observation evidence stays
    ``user_confirmation_required`` by construction: the missing facts are what
    the operator is being asked about, not something this service may assume.
    """

    def build(
        self,
        candidate: dict[str, Any],
        declared: dict[str, Any] | None = None,
        observations: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(candidate, dict):
            raise AuthorizationPackageError(
                "authorization candidate must be an object"
            )
        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        self._reject_sensitive_material(candidate, blockers)
        self._reject_unknown_fields(candidate, blockers)

        identity = self._identity(candidate, blockers)
        launch = self._launch(candidate, blockers)
        permissions = self._permissions(candidate, blockers)
        tools = self._tools(candidate, blockers)
        context = self._context(candidate, blockers)
        working_directory = self._working_directory(candidate, blockers)
        limits = self._limits(candidate, blockers)
        approval_ladder = self._approval_ladder(candidate, blockers)
        single_use = self._single_use(candidate, blockers)
        if candidate.get("execution_authorized") is not False:
            self._block(
                blockers,
                "execution_authority_must_be_false",
                "execution_authorized",
            )

        facts = self._classify_facts(declared, observations, blockers)
        if blockers:
            return {
                "status": STATUS_BLOCKED,
                "execution_authorized": False,
                "blockers": blockers,
                "warnings": warnings,
                "package": None,
                "package_sha256": None,
                "facts": facts,
                "user_confirmation_required": True,
                "missing_observations": list(REQUIRED_EVIDENCE_KINDS),
            }

        package = {
            "kind": PACKAGE_KIND,
            "version": PACKAGE_VERSION,
            "identity": identity,
            "launch": launch,
            "permissions": permissions,
            "tools": tools,
            "context": context,
            "working_directory": working_directory,
            "limits": limits,
            "approval_ladder": approval_ladder,
            "single_use": single_use,
            "execution_authorized": False,
        }
        missing = [
            kind
            for kind in REQUIRED_EVIDENCE_KINDS
            if facts["observed"].get(kind) is None
            or facts["observed"].get(kind) == "unknown"
        ]
        confirmed = self._confirmed_values(candidate)
        if confirmed:
            package["confirmed"] = confirmed
        # The package must become stale when the facts behind it change.
        # Without this digest, a package approved while the actual Model was
        # unknown would keep validating after a later observation contradicted
        # it. The frozen scope requires stale-on-drift, so the fact state is
        # bound into the package and therefore into `package_sha256`.
        package["fact_digest"] = self._digest(facts)
        package["declared_fact_names"] = sorted(facts["declared"])
        package["observed_fact_names"] = sorted(
            kind
            for kind, value in facts["observed"].items()
            if value != "unknown"
        )
        status = (
            STATUS_USER_CONFIRMATION_REQUIRED
            if missing
            else STATUS_ELIGIBLE_FOR_REVIEW
        )
        return {
            "status": status,
            "execution_authorized": False,
            "blockers": [],
            "warnings": warnings,
            "package": package,
            "package_sha256": self._digest(package),
            "facts": facts,
            "user_confirmation_required": bool(missing),
            "missing_observations": missing,
        }

    def verify(self, package: dict[str, Any], digest: str) -> bool:
        """Re-check a stored package against its digest."""
        if not isinstance(package, dict) or not isinstance(digest, str):
            return False
        return self._digest(package) == digest

    # ---------------------------------------------------------------- fields

    def _reject_unknown_fields(
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
            "permissions",
            "tools",
            "context",
            "working_directory",
            "limits",
            "approval_ladder",
            "single_use",
            "execution_authorized",
            "declared",
            "observations",
            "confirmed",
        }
        for key in candidate:
            if key not in allowed:
                self._block(blockers, "unsupported_candidate_field", "candidate")

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
        elif ABSOLUTE_PATH_RE.search(value):
            self._block(blockers, "absolute_path_forbidden", path)
        if CREDENTIAL_VALUE_RE.search(value):
            self._block(blockers, "credential_value_forbidden", path)
        # Mirrors the Board 21 rule: the protected private runtime prefix must
        # not be referenced from a reviewable package.
        if "runtime-board14" in value.lower():
            self._block(blockers, "protected_runtime_reference_forbidden", path)

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
            "lifecycle_checks": list(CANONICAL_LIFECYCLE_CHECKS),
        }

    def _permissions(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> list[str]:
        if candidate.get("permissions") != PERMISSIONS:
            self._block(blockers, "read_only_permission_required", "permissions")
            return []
        return list(PERMISSIONS)

    def _tools(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> list[str]:
        if candidate.get("tools") != TOOLS:
            self._block(blockers, "no_tools_required", "tools")
            return []
        return list(TOOLS)

    def _context(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, Any]:
        value = candidate.get("context")
        if not isinstance(value, dict) or set(value) != {
            "include",
            "exclude",
            "files",
            "artifacts",
        }:
            self._block(blockers, "exact_context_policy_required", "context")
            return {}
        if value.get("include") != CONTEXT_INCLUSIONS:
            self._block(blockers, "exact_context_inclusions_required", "context.include")
        if value.get("exclude") != CONTEXT_EXCLUSIONS:
            self._block(blockers, "exact_context_exclusions_required", "context.exclude")
        if value.get("files") != 0:
            self._block(blockers, "zero_files_required", "context.files")
        if value.get("artifacts") != 0:
            self._block(blockers, "zero_artifacts_required", "context.artifacts")
        return {
            "include": list(CONTEXT_INCLUSIONS),
            "exclude": list(CONTEXT_EXCLUSIONS),
            "files": 0,
            "artifacts": 0,
        }

    def _working_directory(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, str]:
        value = candidate.get("working_directory")
        if not isinstance(value, dict) or set(value) != {"category", "env_var"}:
            self._block(
                blockers,
                "exact_working_directory_reference_required",
                "working_directory",
            )
            return {}
        category = value.get("category")
        env_var = value.get("env_var")
        if category not in PATH_CATEGORIES:
            self._block(
                blockers,
                "unsupported_working_directory_category",
                "working_directory.category",
            )
        if not isinstance(env_var, str) or not ENV_VAR_RE.fullmatch(env_var):
            self._block(
                blockers,
                "working_directory_env_var_required",
                "working_directory.env_var",
            )
        return {"category": str(category), "env_var": str(env_var)}

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
            "timeout_action",
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
            {"max_input_tokens", "max_output_tokens", "max_total_tokens"}
            <= integers.keys()
            and integers["max_total_tokens"]
            < integers["max_input_tokens"] + integers["max_output_tokens"]
        ):
            self._block(
                blockers,
                "total_token_limit_incompatible",
                "limits.max_total_tokens",
            )
        if integers.get("max_attempts") != 1:
            self._block(blockers, "single_attempt_required", "limits.max_attempts")
        if value.get("retry_on_failure") is not False:
            self._block(blockers, "retry_must_be_disabled", "limits.retry_on_failure")
        if value.get("timeout_action") != "stop":
            self._block(blockers, "timeout_must_stop", "limits.timeout_action")
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
            "timeout_action": "stop",
        }

    def _approval_ladder(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> list[str]:
        if candidate.get("approval_ladder") != list(REQUIRED_APPROVAL_LADDER):
            self._block(
                blockers,
                "exact_approval_ladder_required",
                "approval_ladder",
            )
            return []
        return list(REQUIRED_APPROVAL_LADDER)

    def _single_use(
        self,
        candidate: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, bool]:
        if candidate.get("single_use") != SINGLE_USE:
            self._block(blockers, "single_use_semantics_required", "single_use")
            return {}
        return dict(SINGLE_USE)

    # ----------------------------------------------------------------- facts

    def _classify_facts(
        self,
        declared: dict[str, Any] | None,
        observations: dict[str, Any] | None,
        blockers: list[dict[str, str]],
    ) -> dict[str, dict[str, Any]]:
        facts: dict[str, dict[str, Any]] = {
            "declared": {},
            "observed": {},
            "confirmed": {},
        }
        for raw, bucket in (
            (declared, "declared"),
            (observations, "observed"),
        ):
            if raw is None:
                continue
            if not isinstance(raw, dict):
                self._block(
                    blockers,
                    "fact_bucket_must_be_an_object",
                    bucket,
                )
                continue
            for key, value in raw.items():
                if not isinstance(key, str) or not key:
                    self._block(blockers, "invalid_fact_name", bucket)
                    continue
                if isinstance(value, str):
                    if PERSONAL_PATH_RE.search(value):
                        self._block(
                            blockers,
                            "personal_path_forbidden",
                            f"{bucket}.{key}",
                        )
                        continue
                    if CREDENTIAL_VALUE_RE.search(value):
                        self._block(
                            blockers,
                            "credential_value_forbidden",
                            f"{bucket}.{key}",
                        )
                        continue
                facts[bucket][key] = value
        for kind in REQUIRED_EVIDENCE_KINDS:
            facts["observed"].setdefault(kind, "unknown")
        return facts

    @staticmethod
    def _confirmed_values(candidate: dict[str, Any]) -> dict[str, Any]:
        value = candidate.get("confirmed")
        if not isinstance(value, dict):
            return {}
        return {
            key: item
            for key, item in value.items()
            if isinstance(key, str) and key in REQUIRED_EVIDENCE_KINDS
        }

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _block(blockers: list[dict[str, str]], code: str, field: str) -> None:
        item = {"code": code, "field": field}
        if item not in blockers:
            blockers.append(item)

    @staticmethod
    def _is_sensitive_key(normalized: str) -> bool:
        if normalized in {
            "max_input_tokens",
            "max_output_tokens",
            "max_total_tokens",
        }:
            return False
        return any(
            part in normalized
            for part in (
                "api_key",
                "apikey",
                "authorization",
                "bearer",
                "password",
                "secret",
                "token",
            )
        )

    @staticmethod
    def _digest(package: dict[str, Any]) -> str:
        serialized = json.dumps(
            package,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(serialized.encode("utf-8")).hexdigest()
