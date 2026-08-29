from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import uuid4

from .adapters.base import AgentAdapter
from .config import CouncilConfig
from .registry import RegistryService, sanitize_for_storage
from .store import CouncilStore, utc_now


RESERVED_ROLE_KEYS = {"decision_manager", "independent_reviewer"}
SEPARATION_DIMENSIONS = {"agent", "model", "provider"}


class RoutingError(RuntimeError):
    """Raised when deterministic policy cannot resolve a role."""


@dataclass(frozen=True)
class RoutingResult:
    decision_id: str
    role_key: str
    agent_id: str
    provider_id: str | None
    model_id: str | None
    reason_code: str


class RoutingService:
    """Deterministic role selection backed by persisted control-plane evidence."""

    def __init__(
        self,
        config: CouncilConfig,
        store: CouncilStore,
        registry: RegistryService,
        adapters: dict[str, AgentAdapter],
    ):
        self.config = config
        self.store = store
        self.registry = registry
        self.adapters = adapters

    def worker_cards(self) -> list[dict[str, Any]]:
        snapshot = self.registry.snapshot()
        roles = [
            item
            for item in snapshot["roles"]
            if item["role_key"] not in RESERVED_ROLE_KEYS
        ]
        profiles = {item["id"]: item for item in snapshot["agents"]}
        excluded_agents = {
            item["agent_id"]
            for item in snapshot["roles"]
            if item["role_key"] in RESERVED_ROLE_KEYS and item["agent_id"]
        }
        if roles:
            return [
                self._worker_card(
                    role_key=role["role_key"],
                    preferred_agent=role["agent_id"],
                    assignment=role,
                    profile=profiles.get(role["agent_id"]),
                )
                for role in roles
            ]

        cards = []
        for agent_id in self.config.agents:
            if agent_id in excluded_agents:
                continue
            cards.append(
                self._worker_card(
                    role_key=f"agent:{agent_id}",
                    preferred_agent=agent_id,
                    assignment=None,
                    profile=profiles[agent_id],
                )
            )
        if not cards:
            raise ValueError("at least one worker role is required")
        return cards

    def resolve(
        self,
        *,
        run_id: str,
        role_key: str,
        task_key: str | None = None,
        preferred_agent: str | None = None,
    ) -> RoutingResult:
        snapshot = self.registry.snapshot()
        assignments = {
            item["role_key"]: item for item in snapshot["roles"]
        }
        assignment = assignments.get(role_key)
        implicit = assignment is None
        if implicit:
            if not preferred_agent:
                raise RoutingError(
                    f"role {role_key!r} has no persisted assignment or preference"
                )
            assignment = {
                "role_key": role_key,
                "mode": "manual",
                "agent_id": preferred_agent,
                "model_id": None,
                "locked": True,
                "constraints": {},
                "source": "implicit",
            }

        mode = str(assignment["mode"])
        constraints = dict(assignment.get("constraints") or {})
        requested_agent = assignment.get("agent_id") or preferred_agent
        requested_model = assignment.get("model_id")
        candidate_ids = self._candidate_order(
            mode=mode,
            requested_agent=requested_agent,
            preferred_agent=preferred_agent,
            locked=bool(assignment.get("locked")),
        )

        prior = self._resolved_decisions(run_id)
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for agent_id in candidate_ids:
            evidence = self._candidate_evidence(
                agent_id=agent_id,
                role_key=role_key,
                run_id=run_id,
                mode=mode,
                required_model=requested_model,
                constraints=constraints,
                prior_decisions=prior,
            )
            if evidence["accepted"]:
                accepted.append(evidence)
            else:
                rejected.append(evidence)

        if not accepted:
            decision_id = self._persist_decision(
                run_id=run_id,
                task_key=task_key,
                role_key=role_key,
                mode=mode,
                requested_agent=requested_agent,
                requested_model=requested_model,
                selected=None,
                status="failed",
                reason_code="no_eligible_candidate",
                constraints=constraints,
                rejected=rejected,
            )
            reasons = sorted(
                {
                    reason
                    for item in rejected
                    for reason in item["reason_codes"]
                }
            )
            detail = ", ".join(reasons) if reasons else "no candidates"
            raise RoutingError(
                f"role {role_key!r} could not be resolved ({detail}); "
                f"decision {decision_id}"
            )

        selected, reason_code = self._select_candidate(
            mode=mode,
            accepted=accepted,
            requested_agent=requested_agent,
            implicit=implicit,
        )
        rejected.extend(
            {
                **item,
                "accepted": False,
                "reason_codes": ["lower_ranked_candidate"],
            }
            for item in accepted
            if item["agent_id"] != selected["agent_id"]
        )
        decision_id = self._persist_decision(
            run_id=run_id,
            task_key=task_key,
            role_key=role_key,
            mode=mode,
            requested_agent=requested_agent,
            requested_model=requested_model,
            selected=selected,
            status="resolved",
            reason_code=reason_code,
            constraints=constraints,
            rejected=rejected,
        )
        return RoutingResult(
            decision_id=decision_id,
            role_key=role_key,
            agent_id=selected["agent_id"],
            provider_id=selected["provider_id"],
            model_id=selected["model_id"],
            reason_code=reason_code,
        )

    def decisions(self, run_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM routing_decisions"
        params: tuple[Any, ...] = ()
        if run_id:
            query += " WHERE run_id = ?"
            params = (run_id,)
        query += " ORDER BY created_at, id"
        with self.store.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for field in (
                "constraints_json",
                "selected_evidence_json",
                "rejected_candidates_json",
            ):
                item[field.removesuffix("_json")] = json.loads(item.pop(field))
            result.append(item)
        return result

    def _candidate_order(
        self,
        *,
        mode: str,
        requested_agent: str | None,
        preferred_agent: str | None,
        locked: bool,
    ) -> list[str]:
        preferences = []
        for agent_id in (requested_agent, preferred_agent):
            if agent_id and agent_id not in preferences:
                preferences.append(agent_id)
        if mode == "manual" or locked:
            if not preferences:
                raise RoutingError(
                    f"{mode} or locked role requires an explicit Agent"
                )
            return preferences[:1]
        candidates = list(self.adapters)
        return preferences + [
            agent_id for agent_id in candidates if agent_id not in preferences
        ]

    def _candidate_evidence(
        self,
        *,
        agent_id: str,
        role_key: str,
        run_id: str,
        mode: str,
        required_model: str | None,
        constraints: dict[str, Any],
        prior_decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        snapshot = self.registry.snapshot()
        profiles = {item["id"]: item for item in snapshot["agents"]}
        models = {item["id"]: item for item in snapshot["models"]}
        providers = {item["id"]: item for item in snapshot["providers"]}
        profile = profiles.get(agent_id)
        reasons: list[str] = []
        if profile is None:
            return self._rejected_candidate(agent_id, "unknown_agent")
        reserved_agents = {
            item["agent_id"]
            for item in snapshot["roles"]
            if item["role_key"] in RESERVED_ROLE_KEYS and item["agent_id"]
        }
        if role_key not in RESERVED_ROLE_KEYS and agent_id in reserved_agents:
            reasons.append("reserved_role_agent")
        model = models.get(profile["model_id"])
        provider = providers.get(profile["provider_id"])
        model_id = profile["model_id"]
        provider_id = profile["provider_id"]

        if agent_id not in self.adapters:
            reasons.append("adapter_not_configured")
        if not profile["enabled"]:
            reasons.append("agent_disabled")
        if model is None:
            reasons.append("model_unknown")
        elif not model["enabled"]:
            reasons.append("model_disabled")
        if provider is None:
            reasons.append("provider_unknown")
        elif not provider["enabled"]:
            reasons.append("provider_disabled")
        if required_model and model_id != required_model:
            reasons.append("assigned_model_mismatch")

        capabilities = set(profile["capabilities"])
        if model:
            capabilities.update(model["capabilities"])
        required_capabilities = {
            str(item)
            for item in constraints.get("required_capabilities", [])
        }
        missing_capabilities = sorted(required_capabilities - capabilities)
        if missing_capabilities:
            reasons.append("missing_required_capabilities")

        availability = self._availability_evidence(agent_id, profile)
        reasons.extend(
            self._availability_reasons(
                availability=availability,
                mode=mode,
                constraints=constraints,
            )
        )
        history = self._historical_evidence(
            agent_id,
            str(constraints.get("cost_currency", "USD")).upper(),
        )
        reasons.extend(self._history_reasons(history, constraints))
        reasons.extend(
            self._identity_constraint_reasons(
                agent_id=agent_id,
                model_id=model_id,
                provider_id=provider_id,
                constraints=constraints,
                prior_decisions=prior_decisions,
            )
        )
        reasons.extend(
            self._budget_reasons(
                run_id=run_id,
                role_key=role_key,
                profile_role=profile["role"],
            )
        )
        return {
            "agent_id": agent_id,
            "provider_id": provider_id,
            "model_id": model_id,
            "accepted": not reasons,
            "reason_codes": sorted(set(reasons)),
            "capabilities": sorted(capabilities),
            "missing_capabilities": missing_capabilities,
            "availability": availability,
            "history": history,
        }

    def _availability_evidence(
        self,
        agent_id: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        record = self.registry.discovery_record(f"configured:{agent_id}")
        if record is None:
            if profile["adapter_type"] == "mock":
                return {
                    "status": "available",
                    "source": "offline_mock",
                    "executable": "not_applicable",
                    "authentication": "not_applicable",
                    "permission": "not_applicable",
                    "connectivity": "not_checked",
                }
            return {
                "status": "unknown",
                "source": "not_scanned",
                "executable": "unknown",
                "authentication": "unknown",
                "permission": "unknown",
                "connectivity": "not_checked",
            }
        fields = {
            "executable": record["executable_status"],
            "authentication": record["authentication_status"],
            "permission": record["permission_status"],
            "connectivity": record["connectivity_status"],
        }
        unavailable = (
            fields["executable"] == "missing"
            or fields["authentication"] in {"failed", "missing"}
            or fields["connectivity"] == "failed"
        )
        unknown = (
            fields["executable"] == "unknown"
            or fields["authentication"] == "unknown"
            or fields["permission"] == "unknown"
            or fields["connectivity"] == "not_checked"
        )
        if profile["adapter_type"] == "mock" and not unavailable:
            unknown = False
        return {
            "status": (
                "unavailable" if unavailable else "unknown" if unknown else "available"
            ),
            "source": "agent_discovery",
            **fields,
        }

    @staticmethod
    def _availability_reasons(
        *,
        availability: dict[str, Any],
        mode: str,
        constraints: dict[str, Any],
    ) -> list[str]:
        reasons = []
        if availability["status"] == "unavailable":
            reasons.append("unavailable")
        elif (
            availability["status"] == "unknown"
            and mode in {"auto", "hybrid"}
            and not bool(constraints.get("allow_unknown_availability", False))
        ):
            reasons.append("availability_unknown")
        if (
            constraints.get("require_connectivity")
            and availability["connectivity"] != "passed"
        ):
            reasons.append("connectivity_not_verified")
        if (
            constraints.get("require_authentication")
            and availability["authentication"] not in {"verified", "configured"}
        ):
            reasons.append("authentication_not_verified")
        required_permission = constraints.get("required_permission")
        if (
            required_permission
            and availability["permission"] != str(required_permission)
        ):
            reasons.append("permission_mismatch")
        return reasons

    def _historical_evidence(
        self,
        agent_id: str,
        currency: str,
    ) -> dict[str, Any]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT duration_ms, cost_amount, cost_currency,
                       cost_source, token_source
                FROM usage_events
                WHERE project_name = ? AND agent_id = ?
                ORDER BY created_at, id
                """,
                (self.config.project_name, agent_id),
            ).fetchall()
        durations = [Decimal(row["duration_ms"]) for row in rows]
        costs = [
            Decimal(row["cost_amount"])
            for row in rows
            if row["cost_amount"] is not None
            and row["cost_currency"] == currency
        ]
        return {
            "samples": len(rows),
            "average_latency_ms": (
                self._decimal_text(sum(durations) / len(durations))
                if durations
                else None
            ),
            "average_cost": (
                self._decimal_text(sum(costs) / len(costs)) if costs else None
            ),
            "cost_currency": currency,
            "cost_samples": len(costs),
            "cost_unknown_samples": len(rows) - len(costs),
            "cost_sources": sorted(
                {row["cost_source"] for row in rows}
            ),
            "token_sources": sorted(
                {row["token_source"] for row in rows}
            ),
        }

    @staticmethod
    def _history_reasons(
        history: dict[str, Any],
        constraints: dict[str, Any],
    ) -> list[str]:
        reasons = []
        max_cost = constraints.get(
            "max_average_cost",
            constraints.get("max_cost"),
        )
        if max_cost is not None:
            if history["average_cost"] is None:
                if not constraints.get("allow_unknown_cost", False):
                    reasons.append("cost_unknown")
            elif Decimal(history["average_cost"]) > Decimal(str(max_cost)):
                reasons.append("cost_limit_exceeded")
        max_latency = constraints.get(
            "max_average_latency_ms",
            constraints.get("max_latency_ms"),
        )
        if max_latency is not None:
            if history["average_latency_ms"] is None:
                if not constraints.get("allow_unknown_latency", False):
                    reasons.append("latency_unknown")
            elif Decimal(history["average_latency_ms"]) > Decimal(
                str(max_latency)
            ):
                reasons.append("latency_limit_exceeded")
        return reasons

    @staticmethod
    def _identity_constraint_reasons(
        *,
        agent_id: str,
        model_id: str | None,
        provider_id: str | None,
        constraints: dict[str, Any],
        prior_decisions: list[dict[str, Any]],
    ) -> list[str]:
        reasons = []
        if agent_id in constraints.get("excluded_agents", []):
            reasons.append("agent_excluded")
        if model_id in constraints.get("excluded_models", []):
            reasons.append("model_excluded")
        if provider_id in constraints.get("excluded_providers", []):
            reasons.append("provider_excluded")

        separation = constraints.get("separation", {})
        if not isinstance(separation, dict):
            separation = {}
        common_roles = list(
            separation.get(
                "roles",
                constraints.get("separate_from_roles", []),
            )
        )
        common_dimensions = list(
            separation.get(
                "dimensions",
                constraints.get("separation_dimensions", ["agent"]),
            )
        )
        dimension_roles = {
            "agent": set(common_roles)
            | set(constraints.get("distinct_agent_from_roles", [])),
            "model": set(common_roles)
            | set(constraints.get("distinct_model_from_roles", [])),
            "provider": set(common_roles)
            | set(constraints.get("distinct_provider_from_roles", [])),
        }
        common_dimension_set = {
            str(item) for item in common_dimensions
        } & SEPARATION_DIMENSIONS
        for dimension in SEPARATION_DIMENSIONS:
            if dimension not in common_dimension_set:
                dimension_roles[dimension] -= set(common_roles)
        current = {
            "agent": agent_id,
            "model": model_id,
            "provider": provider_id,
        }
        selected_fields = {
            "agent": "selected_agent_id",
            "model": "selected_model_id",
            "provider": "selected_provider_id",
        }
        for prior in prior_decisions:
            for dimension, roles in dimension_roles.items():
                if (
                    prior["role_key"] in roles
                    and current[dimension] is not None
                    and current[dimension] == prior[selected_fields[dimension]]
                ):
                    reasons.append(f"{dimension}_separation_violation")
        return reasons

    def _budget_reasons(
        self,
        *,
        run_id: str,
        role_key: str,
        profile_role: str,
    ) -> list[str]:
        with self.store.connect() as conn:
            policies = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT * FROM budget_policies
                    WHERE hard_limit IS NOT NULL
                    ORDER BY id
                    """
                ).fetchall()
            ]
        reasons = []
        for policy in policies:
            if policy["scope_type"] == "project":
                active = policy["scope_key"] == self.config.project_name
            elif policy["scope_type"] == "run":
                active = policy["scope_key"] == run_id
            else:
                active = policy["scope_key"] in {role_key, profile_role}
            if not active:
                continue
            observed, unavailable = self._budget_observation(
                policy,
                run_id,
                profile_role,
            )
            if unavailable:
                reasons.append("hard_budget_evidence_unavailable")
            elif observed >= Decimal(policy["hard_limit"]):
                reasons.append("hard_budget_reached")
        return reasons

    def _budget_observation(
        self,
        policy: dict[str, Any],
        run_id: str,
        profile_role: str,
    ) -> tuple[Decimal, int]:
        where = ["project_name = ?"]
        params: list[Any] = [self.config.project_name]
        if policy["scope_type"] == "run":
            where.append("run_id = ?")
            params.append(run_id)
        elif policy["scope_type"] == "role":
            where.append("role = ?")
            params.append(profile_role)
        with self.store.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM usage_events WHERE {' AND '.join(where)}",
                params,
            ).fetchall()
        observed = Decimal(0)
        unavailable = 0
        for row in rows:
            if policy["metric"] == "tokens":
                if row["total_tokens"] is None:
                    unavailable += 1
                else:
                    observed += Decimal(row["total_tokens"])
            elif (
                row["cost_amount"] is None
                or row["cost_currency"] != policy["currency"]
            ):
                unavailable += 1
            else:
                observed += Decimal(row["cost_amount"])
        return observed, unavailable

    @staticmethod
    def _select_candidate(
        *,
        mode: str,
        accepted: list[dict[str, Any]],
        requested_agent: str | None,
        implicit: bool,
    ) -> tuple[dict[str, Any], str]:
        if requested_agent:
            preferred = next(
                (
                    item
                    for item in accepted
                    if item["agent_id"] == requested_agent
                ),
                None,
            )
            if preferred is not None:
                if implicit:
                    return preferred, "implicit_manual_assignment"
                if mode == "manual":
                    return preferred, "manual_assignment"
                if mode == "hybrid":
                    return preferred, "hybrid_preference"
        ranked = sorted(
            accepted,
            key=lambda item: (
                RoutingService._unknown_last(item["history"]["average_cost"]),
                RoutingService._unknown_last(
                    item["history"]["average_latency_ms"]
                ),
                item["agent_id"],
            ),
        )
        if mode == "hybrid":
            return ranked[0], "hybrid_fallback"
        return ranked[0], "automatic_selection"

    @staticmethod
    def _unknown_last(value: str | None) -> tuple[int, Decimal]:
        if value is None:
            return (1, Decimal(0))
        return (0, Decimal(value))

    def _resolved_decisions(self, run_id: str) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT role_key, selected_agent_id, selected_model_id,
                       selected_provider_id
                FROM routing_decisions
                WHERE run_id = ? AND status = 'resolved'
                ORDER BY created_at, id
                """,
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _persist_decision(
        self,
        *,
        run_id: str,
        task_key: str | None,
        role_key: str,
        mode: str,
        requested_agent: str | None,
        requested_model: str | None,
        selected: dict[str, Any] | None,
        status: str,
        reason_code: str,
        constraints: dict[str, Any],
        rejected: list[dict[str, Any]],
    ) -> str:
        decision_id = str(uuid4())
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO routing_decisions(
                    id, run_id, task_key, role_key, mode,
                    requested_agent_id, requested_model_id,
                    selected_agent_id, selected_provider_id, selected_model_id,
                    status, reason_code, constraints_json,
                    selected_evidence_json, rejected_candidates_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    run_id,
                    task_key,
                    role_key,
                    mode,
                    requested_agent,
                    requested_model,
                    selected["agent_id"] if selected else None,
                    selected["provider_id"] if selected else None,
                    selected["model_id"] if selected else None,
                    status,
                    reason_code,
                    json.dumps(
                        sanitize_for_storage(constraints),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    json.dumps(
                        sanitize_for_storage(selected or {}),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    json.dumps(
                        sanitize_for_storage(rejected),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    utc_now(),
                ),
            )
        return decision_id

    @staticmethod
    def _worker_card(
        *,
        role_key: str,
        preferred_agent: str | None,
        assignment: dict[str, Any] | None,
        profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        constraints = (assignment or {}).get("constraints") or {}
        capabilities = (
            profile["capabilities"]
            if profile
            else list(constraints.get("required_capabilities", []))
        )
        return {
            "name": preferred_agent or role_key,
            "role_key": role_key,
            "role": profile["role"] if profile else role_key,
            "description": profile["description"] if profile else "",
            "capabilities": list(capabilities),
            "boundaries": list(profile["boundaries"]) if profile else [],
            "routing_mode": (
                assignment["mode"] if assignment else "implicit_manual"
            ),
            "preferred_agent": preferred_agent,
        }

    @staticmethod
    def _rejected_candidate(agent_id: str, reason: str) -> dict[str, Any]:
        return {
            "agent_id": agent_id,
            "provider_id": None,
            "model_id": None,
            "accepted": False,
            "reason_codes": [reason],
            "capabilities": [],
            "missing_capabilities": [],
            "availability": {"status": "unknown", "source": "registry"},
            "history": {
                "samples": 0,
                "average_latency_ms": None,
                "average_cost": None,
                "cost_currency": None,
                "cost_samples": 0,
                "cost_unknown_samples": 0,
                "cost_sources": [],
                "token_sources": [],
            },
        }

    @staticmethod
    def _decimal_text(value: Decimal) -> str:
        normalized = value.normalize()
        if normalized == normalized.to_integral():
            return str(normalized.quantize(Decimal(1)))
        return format(normalized, "f")
