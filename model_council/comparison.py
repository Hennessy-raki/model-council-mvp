from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

from .ledger import UsageLedger
from .routing import RoutingService
from .store import CouncilStore


class RunComparisonService:
    """Deterministic local summaries and pairwise run comparison."""

    def __init__(
        self,
        store: CouncilStore,
        ledger: UsageLedger,
        routing: RoutingService,
    ):
        self.store = store
        self.ledger = ledger
        self.routing = routing

    def summarize(self, run_id: str) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        if run is None:
            raise ValueError(f"run {run_id!r} not found")
        tasks = self.store.tasks_for_run(run_id)
        artifacts = self.store.artifacts_for_run(run_id)
        messages = self.store.messages_for_run(run_id)
        ledger = self.ledger.summary(run_id=run_id)
        alerts = self.ledger.alerts(run_id)
        routing = self.routing.decisions(run_id)
        with self.store.connect() as conn:
            evaluations = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, agent_id, agent_family, role, case_id, status,
                           created_at, completed_at, error
                    FROM evaluation_runs
                    WHERE run_id = ?
                    ORDER BY created_at, id
                    """,
                    (run_id,),
                ).fetchall()
            ]
        total = ledger["total"]
        cost_known = not total["cost_sources"].get("unavailable", 0)
        return {
            "run": run,
            "task_statuses": dict(
                sorted(Counter(item["status"] for item in tasks).items())
            ),
            "task_count": len(tasks),
            "artifact_count": len(artifacts),
            "message_count": len(messages),
            "usage": {
                "calls": total["calls"],
                "duration_ms": total["duration_ms"],
                "input_tokens": total["input_tokens"],
                "output_tokens": total["output_tokens"],
                "total_tokens": total["total_tokens"],
                "token_sources": total["token_sources"],
                "cost_known": cost_known,
                "costs": total["costs"] if cost_known else None,
                "cost_sources": total["cost_sources"],
            },
            "budget_alert_count": len(alerts),
            "routing_decision_count": len(routing),
            "evaluations": evaluations,
        }

    def compare(self, left_run_id: str, right_run_id: str) -> dict[str, Any]:
        left = self.summarize(left_run_id)
        right = self.summarize(right_run_id)
        return {
            "left": left,
            "right": right,
            "delta": {
                "task_count": right["task_count"] - left["task_count"],
                "artifact_count": (
                    right["artifact_count"] - left["artifact_count"]
                ),
                "message_count": right["message_count"] - left["message_count"],
                "calls": right["usage"]["calls"] - left["usage"]["calls"],
                "duration_ms": (
                    right["usage"]["duration_ms"]
                    - left["usage"]["duration_ms"]
                ),
                "total_tokens": (
                    right["usage"]["total_tokens"]
                    - left["usage"]["total_tokens"]
                ),
                "budget_alert_count": (
                    right["budget_alert_count"]
                    - left["budget_alert_count"]
                ),
                "routing_decision_count": (
                    right["routing_decision_count"]
                    - left["routing_decision_count"]
                ),
                "costs": self._cost_delta(left["usage"], right["usage"]),
            },
        }

    @staticmethod
    def _cost_delta(
        left: dict[str, Any],
        right: dict[str, Any],
    ) -> dict[str, Any]:
        if not left["cost_known"] or not right["cost_known"]:
            return {
                "known": False,
                "reason": "one or both runs contain unavailable cost evidence",
                "values": None,
            }
        currencies = sorted(
            set(left["costs"] or {}) | set(right["costs"] or {})
        )
        return {
            "known": True,
            "values": {
                currency: _decimal_text(
                    Decimal((right["costs"] or {}).get(currency, "0"))
                    - Decimal((left["costs"] or {}).get(currency, "0"))
                )
                for currency in currencies
            },
        }


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal(1)))
    return format(normalized, "f")
