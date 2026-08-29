from __future__ import annotations

import json
import math
import time
from collections import Counter
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Any
from uuid import uuid4

from .adapters.base import AgentAdapter
from .config import CouncilConfig
from .registry import RegistryService, sanitize_for_storage
from .store import CouncilStore, utc_now
from .types import (
    AgentRequest,
    AgentResponse,
    BudgetLevel,
    BudgetMetric,
    BudgetScope,
    MeasurementSource,
)


class BudgetExceededError(RuntimeError):
    pass


class UsageLedger:
    """Normalized per-call usage, cost, budget and balance ledger."""

    def __init__(
        self,
        config: CouncilConfig,
        store: CouncilStore,
        registry: RegistryService,
    ):
        self.config = config
        self.store = store
        self.registry = registry
        self._budget_lock = Lock()
        self.sync_budget_policies()

    def invoke(
        self,
        agent_id: str,
        adapter: AgentAdapter,
        request: AgentRequest,
    ) -> AgentResponse:
        role = self.config.card(agent_id).role
        hard_policies = [
            item
            for item in self._active_policies(request.run_id, role)
            if item["hard_limit"] is not None
        ]
        if hard_policies:
            with self._budget_lock:
                self._enforce_hard_limits(
                    request.run_id,
                    role,
                    hard_policies,
                )
                return self._invoke_and_record(
                    agent_id,
                    role,
                    adapter,
                    request,
                )
        return self._invoke_and_record(
            agent_id,
            role,
            adapter,
            request,
        )

    def _invoke_and_record(
        self,
        agent_id: str,
        role: str,
        adapter: AgentAdapter,
        request: AgentRequest,
    ) -> AgentResponse:
        started = time.perf_counter()
        prompt_length = len(adapter.render_prompt(request))
        try:
            response = adapter.invoke(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000)
            self._record_event(
                run_id=request.run_id,
                task_id=request.task_id,
                agent_id=agent_id,
                role=role,
                phase=request.mode,
                status="failed",
                duration_ms=duration_ms,
                prompt_length=prompt_length,
                response=None,
            )
            self.evaluate_budgets(request.run_id, role)
            raise
        duration_ms = round((time.perf_counter() - started) * 1000)
        event_id = self._record_event(
            run_id=request.run_id,
            task_id=request.task_id,
            agent_id=agent_id,
            role=role,
            phase=request.mode,
            status="completed",
            duration_ms=duration_ms,
            prompt_length=prompt_length,
            response=response,
        )
        alerts = self.evaluate_budgets(request.run_id, role)
        response.metadata["ledger"] = {
            "event_id": event_id,
            "alerts": alerts,
        }
        return response

    def _record_event(
        self,
        *,
        run_id: str,
        task_id: str | None,
        agent_id: str,
        role: str,
        phase: str,
        status: str,
        duration_ms: int,
        prompt_length: int,
        response: AgentResponse | None,
    ) -> str:
        identity = self.store.identity_for_agent(agent_id)
        metadata = response.metadata if response else {}
        normalized = self._normalize_usage(
            metadata=metadata,
            prompt_length=prompt_length,
            output_length=len(response.content) if response else 0,
            model_id=identity.model_id,
        )
        event_id = str(uuid4())
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO usage_events(
                    id, run_id, task_id, project_name, agent_id, role,
                    provider_id, model_id, phase, status,
                    request_count, request_source,
                    input_tokens, output_tokens, total_tokens, token_source,
                    duration_ms, duration_source,
                    cost_amount, cost_currency, cost_source,
                    raw_usage_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    run_id,
                    task_id,
                    self.config.project_name,
                    agent_id,
                    role,
                    identity.provider_id,
                    identity.model_id,
                    phase,
                    status,
                    MeasurementSource.ACTUAL.value,
                    normalized["input_tokens"],
                    normalized["output_tokens"],
                    normalized["total_tokens"],
                    normalized["token_source"],
                    max(0, duration_ms),
                    MeasurementSource.ACTUAL.value,
                    normalized["cost_amount"],
                    normalized["cost_currency"],
                    normalized["cost_source"],
                    json.dumps(
                        sanitize_for_storage(normalized["raw_usage"]),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    utc_now(),
                ),
            )
        return event_id

    def _normalize_usage(
        self,
        *,
        metadata: dict[str, Any],
        prompt_length: int,
        output_length: int,
        model_id: str | None,
    ) -> dict[str, Any]:
        usage = metadata.get("usage")
        input_tokens: int | None = None
        output_tokens: int | None = None
        total_tokens: int | None = None
        token_source = MeasurementSource.UNAVAILABLE
        if isinstance(usage, dict):
            input_tokens = self._first_non_negative_int(
                usage,
                "input_tokens",
                "prompt_tokens",
            )
            output_tokens = self._first_non_negative_int(
                usage,
                "output_tokens",
                "completion_tokens",
            )
            total_tokens = self._first_non_negative_int(
                usage,
                "total_tokens",
            )
            if total_tokens is None and (
                input_tokens is not None or output_tokens is not None
            ):
                total_tokens = (input_tokens or 0) + (output_tokens or 0)
            if any(
                value is not None
                for value in (input_tokens, output_tokens, total_tokens)
            ):
                token_source = self._measurement_source(
                    metadata.get("usage_source"),
                    MeasurementSource.PROVIDER_REPORTED,
                )
        if (
            token_source == MeasurementSource.UNAVAILABLE
            and bool(
                self.registry.setting_value(
                    "usage_estimation_enabled",
                    False,
                )
            )
        ):
            input_tokens = self._estimate_tokens(prompt_length)
            output_tokens = self._estimate_tokens(output_length)
            total_tokens = input_tokens + output_tokens
            token_source = MeasurementSource.ESTIMATED

        cost_amount: str | None = None
        cost_currency: str | None = None
        cost_source = MeasurementSource.UNAVAILABLE
        cost = metadata.get("cost")
        if isinstance(cost, dict) and cost.get("amount") is not None:
            amount = self._decimal(cost["amount"], "reported cost")
            cost_amount = self._decimal_text(amount)
            cost_currency = str(cost.get("currency", "USD")).upper()
            cost_source = self._measurement_source(
                cost.get("source"),
                MeasurementSource.PROVIDER_REPORTED,
            )
        elif isinstance(cost, (int, float, str)):
            amount = self._decimal(cost, "reported cost")
            cost_amount = self._decimal_text(amount)
            cost_currency = "USD"
            cost_source = MeasurementSource.PROVIDER_REPORTED
        else:
            estimated_cost = self._estimate_cost(
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            if estimated_cost is not None:
                amount, currency = estimated_cost
                cost_amount = self._decimal_text(amount)
                cost_currency = currency
                cost_source = MeasurementSource.ESTIMATED

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "token_source": token_source.value,
            "cost_amount": cost_amount,
            "cost_currency": cost_currency,
            "cost_source": cost_source.value,
            "raw_usage": usage if isinstance(usage, dict) else {},
        }

    def _estimate_cost(
        self,
        *,
        model_id: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> tuple[Decimal, str] | None:
        if model_id is None or input_tokens is None or output_tokens is None:
            return None
        model = self.config.models.get(model_id, {})
        pricing = model.get("pricing")
        if not isinstance(pricing, dict):
            return None
        input_rate = self._decimal(
            pricing.get("input_per_million", 0),
            "input price",
        )
        output_rate = self._decimal(
            pricing.get("output_per_million", 0),
            "output price",
        )
        per_request = self._decimal(
            pricing.get("per_request", 0),
            "per-request price",
        )
        amount = (
            Decimal(input_tokens) * input_rate / Decimal(1_000_000)
            + Decimal(output_tokens) * output_rate / Decimal(1_000_000)
            + per_request
        )
        return amount, str(pricing.get("currency", "USD")).upper()

    def sync_budget_policies(self) -> int:
        now = utc_now()
        with self.store.connect() as conn:
            for policy_id, item in self.config.budgets.items():
                scope = BudgetScope(str(item.get("scope", "project")))
                scope_key = str(
                    item.get(
                        "scope_key",
                        self.config.project_name
                        if scope == BudgetScope.PROJECT
                        else "",
                    )
                )
                metric = BudgetMetric(str(item.get("metric", "tokens")))
                warning = self._optional_decimal_text(item.get("warning"))
                hard = self._optional_decimal_text(item.get("hard"))
                currency = (
                    str(item.get("currency", "USD")).upper()
                    if metric == BudgetMetric.COST
                    else None
                )
                conn.execute(
                    """
                    INSERT INTO budget_policies(
                        id, scope_type, scope_key, metric, warning_limit,
                        hard_limit, currency, source, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'config', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        scope_type = excluded.scope_type,
                        scope_key = excluded.scope_key,
                        metric = excluded.metric,
                        warning_limit = excluded.warning_limit,
                        hard_limit = excluded.hard_limit,
                        currency = excluded.currency,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    WHERE budget_policies.source != 'user'
                    """,
                    (
                        policy_id,
                        scope.value,
                        scope_key,
                        metric.value,
                        warning,
                        hard,
                        currency,
                        now,
                        now,
                    ),
                )
        return len(self.config.budgets)

    def set_budget_policy(
        self,
        *,
        policy_id: str,
        scope: str | BudgetScope,
        scope_key: str,
        metric: str | BudgetMetric,
        warning: Any = None,
        hard: Any = None,
        currency: str | None = None,
    ) -> None:
        scope = BudgetScope(scope)
        metric = BudgetMetric(metric)
        if not policy_id.strip() or not scope_key.strip():
            raise ValueError("budget id and scope key cannot be empty")
        warning_text = self._optional_decimal_text(warning)
        hard_text = self._optional_decimal_text(hard)
        if warning_text is None and hard_text is None:
            raise ValueError("budget requires warning or hard limit")
        if (
            warning_text is not None
            and hard_text is not None
            and Decimal(warning_text) > Decimal(hard_text)
        ):
            raise ValueError("budget warning cannot exceed hard limit")
        if metric == BudgetMetric.COST and not currency:
            raise ValueError("cost budget requires currency")
        now = utc_now()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO budget_policies(
                    id, scope_type, scope_key, metric, warning_limit,
                    hard_limit, currency, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'user', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    scope_type = excluded.scope_type,
                    scope_key = excluded.scope_key,
                    metric = excluded.metric,
                    warning_limit = excluded.warning_limit,
                    hard_limit = excluded.hard_limit,
                    currency = excluded.currency,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (
                    policy_id,
                    scope.value,
                    scope_key,
                    metric.value,
                    warning_text,
                    hard_text,
                    currency.upper() if currency else None,
                    now,
                    now,
                ),
            )

    def budget_policies(self) -> list[dict[str, Any]]:
        with self.store.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM budget_policies ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def evaluate_budgets(
        self,
        run_id: str,
        role: str,
    ) -> list[dict[str, Any]]:
        alerts = []
        for policy in self._active_policies(run_id, role):
            observed, unavailable = self._policy_observation(
                policy,
                run_id,
                role,
            )
            if unavailable:
                alert = self._add_alert(
                    policy,
                    run_id,
                    BudgetLevel.UNAVAILABLE,
                    None,
                    policy["hard_limit"] or policy["warning_limit"],
                    {"unavailable_events": unavailable},
                )
                if alert:
                    alerts.append(alert)
            warning = self._optional_decimal(policy["warning_limit"])
            hard = self._optional_decimal(policy["hard_limit"])
            if warning is not None and observed >= warning:
                alert = self._add_alert(
                    policy,
                    run_id,
                    BudgetLevel.WARNING,
                    observed,
                    warning,
                    {},
                )
                if alert:
                    alerts.append(alert)
            if hard is not None and observed >= hard:
                alert = self._add_alert(
                    policy,
                    run_id,
                    BudgetLevel.HARD,
                    observed,
                    hard,
                    {},
                )
                if alert:
                    alerts.append(alert)
        return alerts

    def _enforce_hard_limits(
        self,
        run_id: str,
        role: str,
        policies: list[dict[str, Any]],
    ) -> None:
        for policy in policies:
            observed, unavailable = self._policy_observation(
                policy,
                run_id,
                role,
            )
            hard = Decimal(policy["hard_limit"])
            if unavailable:
                self._add_alert(
                    policy,
                    run_id,
                    BudgetLevel.UNAVAILABLE,
                    None,
                    hard,
                    {"unavailable_events": unavailable, "blocked": True},
                )
                raise BudgetExceededError(
                    f"hard budget {policy['id']!r} cannot be enforced because "
                    f"{unavailable} prior event(s) are unavailable"
                )
            if observed >= hard:
                self._add_alert(
                    policy,
                    run_id,
                    BudgetLevel.HARD,
                    observed,
                    hard,
                    {"blocked": True},
                )
                raise BudgetExceededError(
                    f"hard budget {policy['id']!r} reached: "
                    f"{self._decimal_text(observed)} >= "
                    f"{self._decimal_text(hard)}"
                )

    def _active_policies(
        self,
        run_id: str,
        role: str,
    ) -> list[dict[str, Any]]:
        result = []
        for item in self.budget_policies():
            scope = BudgetScope(item["scope_type"])
            if scope == BudgetScope.PROJECT:
                active = item["scope_key"] == self.config.project_name
            elif scope == BudgetScope.RUN:
                active = item["scope_key"] == run_id
            else:
                active = item["scope_key"] == role
            if active:
                result.append(item)
        return result

    def _policy_observation(
        self,
        policy: dict[str, Any],
        run_id: str,
        role: str,
    ) -> tuple[Decimal, int]:
        scope = BudgetScope(policy["scope_type"])
        where = ["project_name = ?"]
        params: list[Any] = [self.config.project_name]
        if scope == BudgetScope.RUN:
            where.append("run_id = ?")
            params.append(run_id)
        elif scope == BudgetScope.ROLE:
            where.append("role = ?")
            params.append(role)
        with self.store.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM usage_events WHERE {' AND '.join(where)}",
                params,
            ).fetchall()
        metric = BudgetMetric(policy["metric"])
        observed = Decimal(0)
        unavailable = 0
        for row in rows:
            if metric == BudgetMetric.TOKENS:
                if row["total_tokens"] is None:
                    unavailable += 1
                else:
                    observed += Decimal(row["total_tokens"])
            else:
                if (
                    row["cost_amount"] is None
                    or row["cost_currency"] != policy["currency"]
                ):
                    unavailable += 1
                else:
                    observed += Decimal(row["cost_amount"])
        return observed, unavailable

    def _add_alert(
        self,
        policy: dict[str, Any],
        run_id: str,
        level: BudgetLevel,
        observed: Decimal | None,
        limit: Decimal | str | None,
        details: dict[str, Any],
    ) -> dict[str, Any] | None:
        alert_id = str(uuid4())
        observed_text = (
            self._decimal_text(observed) if observed is not None else None
        )
        limit_decimal = self._optional_decimal(limit)
        limit_text = (
            self._decimal_text(limit_decimal)
            if limit_decimal is not None
            else None
        )
        with self.store.connect() as conn:
            inserted = conn.execute(
                """
                INSERT OR IGNORE INTO budget_alerts(
                    id, policy_id, run_id, level, metric,
                    observed_value, limit_value, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    policy["id"],
                    run_id,
                    level.value,
                    policy["metric"],
                    observed_text,
                    limit_text,
                    json.dumps(
                        sanitize_for_storage(details),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    utc_now(),
                ),
            ).rowcount
        if not inserted:
            return None
        return {
            "id": alert_id,
            "policy_id": policy["id"],
            "level": level.value,
            "metric": policy["metric"],
            "observed_value": observed_text,
            "limit_value": limit_text,
        }

    def alerts(self, run_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM budget_alerts"
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
            item["details"] = json.loads(item.pop("details_json"))
            result.append(item)
        return result

    def events(
        self,
        *,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM usage_events"
        params: list[Any] = []
        if run_id:
            query += " WHERE run_id = ?"
            params.append(run_id)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(max(1, limit))
        with self.store.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["raw_usage"] = json.loads(item.pop("raw_usage_json"))
            result.append(item)
        return result

    def summary(
        self,
        *,
        project_name: str | None = None,
        run_id: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        where = []
        params: list[Any] = []
        if project_name:
            where.append("project_name = ?")
            params.append(project_name)
        if run_id:
            where.append("run_id = ?")
            params.append(run_id)
        if role:
            where.append("role = ?")
            params.append(role)
        query = "SELECT * FROM usage_events"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY created_at, id"
        with self.store.connect() as conn:
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]
        roles: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            roles.setdefault(row["role"], []).append(row)
        return {
            "filters": {
                "project_name": project_name,
                "run_id": run_id,
                "role": role,
            },
            "total": self._aggregate(rows),
            "roles": [
                {"role": role_name, **self._aggregate(role_rows)}
                for role_name, role_rows in sorted(roles.items())
            ],
        }

    def provider_balance(
        self,
        provider_id: str,
        adapters: dict[str, AgentAdapter],
    ) -> dict[str, Any]:
        candidates = [
            (agent_id, adapters[agent_id])
            for agent_id, settings in self.config.agents.items()
            if str(settings.get("provider", "")) == provider_id
            and agent_id in adapters
            and adapters[agent_id]
            .billing_capabilities()
            .get("provider_balance", False)
        ]
        if not candidates:
            return {
                "provider_id": provider_id,
                "status": "unavailable",
                "source": MeasurementSource.UNAVAILABLE.value,
                "reason": "no configured Adapter exposes a supported balance API",
            }
        agent_id, adapter = candidates[0]
        result = adapter.provider_balance()
        amount = self._decimal(result.get("amount"), "provider balance")
        currency = str(result.get("currency", "USD")).upper()
        source = self._measurement_source(
            result.get("source"),
            MeasurementSource.PROVIDER_REPORTED,
        )
        snapshot_id = str(uuid4())
        details = result.get("details")
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO provider_balance_snapshots(
                    id, provider_id, amount, currency, source,
                    details_json, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    provider_id,
                    self._decimal_text(amount),
                    currency,
                    source.value,
                    json.dumps(
                        sanitize_for_storage(
                            details if isinstance(details, dict) else {}
                        ),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    utc_now(),
                ),
            )
        return {
            "id": snapshot_id,
            "provider_id": provider_id,
            "agent_id": agent_id,
            "status": "available",
            "amount": self._decimal_text(amount),
            "currency": currency,
            "source": source.value,
        }

    def balance_snapshots(
        self,
        provider_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM provider_balance_snapshots"
        params: tuple[Any, ...] = ()
        if provider_id:
            query += " WHERE provider_id = ?"
            params = (provider_id,)
        query += " ORDER BY checked_at DESC, id DESC"
        with self.store.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            result.append(item)
        return result

    @staticmethod
    def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
        token_sources = Counter(row["token_source"] for row in rows)
        cost_sources = Counter(row["cost_source"] for row in rows)
        statuses = Counter(row["status"] for row in rows)
        costs: dict[str, Decimal] = {}
        for row in rows:
            if row["cost_amount"] is not None and row["cost_currency"]:
                costs.setdefault(row["cost_currency"], Decimal(0))
                costs[row["cost_currency"]] += Decimal(row["cost_amount"])
        return {
            "calls": sum(row["request_count"] for row in rows),
            "duration_ms": sum(row["duration_ms"] for row in rows),
            "input_tokens": sum(
                row["input_tokens"] or 0 for row in rows
            ),
            "output_tokens": sum(
                row["output_tokens"] or 0 for row in rows
            ),
            "total_tokens": sum(
                row["total_tokens"] or 0 for row in rows
            ),
            "costs": {
                currency: UsageLedger._decimal_text(amount)
                for currency, amount in sorted(costs.items())
            },
            "token_sources": dict(sorted(token_sources.items())),
            "cost_sources": dict(sorted(cost_sources.items())),
            "statuses": dict(sorted(statuses.items())),
        }

    @staticmethod
    def _first_non_negative_int(
        data: dict[str, Any],
        *keys: str,
    ) -> int | None:
        for key in keys:
            value = data.get(key)
            if value is None or isinstance(value, bool):
                continue
            try:
                result = int(value)
            except (TypeError, ValueError):
                continue
            if result >= 0:
                return result
        return None

    @staticmethod
    def _estimate_tokens(character_count: int) -> int:
        if character_count <= 0:
            return 0
        return max(1, math.ceil(character_count / 4))

    @staticmethod
    def _measurement_source(
        value: Any,
        default: MeasurementSource,
    ) -> MeasurementSource:
        if value is None:
            return default
        try:
            return MeasurementSource(str(value))
        except ValueError:
            return default

    @staticmethod
    def _decimal(value: Any, label: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{label} must be numeric") from exc
        if not result.is_finite() or result < 0:
            raise ValueError(f"{label} must be a finite non-negative number")
        return result

    @classmethod
    def _optional_decimal_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        return cls._decimal_text(cls._decimal(value, "budget limit"))

    @staticmethod
    def _optional_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))

    @staticmethod
    def _decimal_text(value: Decimal) -> str:
        normalized = value.normalize()
        if normalized == normalized.to_integral():
            return str(normalized.quantize(Decimal(1)))
        return format(normalized, "f")
