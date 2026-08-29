from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import json
import unittest

from model_council.adapters import build_adapters
from model_council.config import load_config
from model_council.registry import RegistryService
from model_council.routing import RoutingError, RoutingService
from model_council.store import CouncilStore, utc_now


class RoutingTests(unittest.TestCase):
    def _write_config(
        self,
        root: Path,
        *,
        assignment: dict,
        worker_a_enabled: bool = True,
    ) -> Path:
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "project_name": "routing-test",
                    "state_dir": "runtime",
                    "manager": "manager",
                    "reviewer": "reviewer",
                    "providers": {
                        "provider-a": {
                            "kind": "mock",
                            "display_name": "Provider A",
                            "enabled": True,
                        },
                        "provider-b": {
                            "kind": "mock",
                            "display_name": "Provider B",
                            "enabled": True,
                        },
                    },
                    "models": {
                        "model-a": {
                            "provider": "provider-a",
                            "display_name": "Model A",
                            "capabilities": [],
                            "enabled": True,
                        },
                        "model-b": {
                            "provider": "provider-b",
                            "display_name": "Model B",
                            "capabilities": [],
                            "enabled": True,
                        },
                    },
                    "agents": {
                        "manager": {
                            "type": "mock",
                            "provider": "provider-a",
                            "model": "model-a",
                            "role": "manager",
                            "capabilities": ["planning"],
                        },
                        "worker_a": {
                            "type": "mock",
                            "provider": "provider-a",
                            "model": "model-a",
                            "role": "worker",
                            "enabled": worker_a_enabled,
                            "capabilities": ["coding"],
                        },
                        "worker_b": {
                            "type": "mock",
                            "provider": "provider-b",
                            "model": "model-b",
                            "role": "worker",
                            "capabilities": ["coding"],
                        },
                        "reviewer": {
                            "type": "mock",
                            "provider": "provider-a",
                            "model": "model-a",
                            "role": "reviewer",
                            "capabilities": ["review"],
                        },
                    },
                    "role_assignments": {
                        "decision_manager": {
                            "mode": "manual",
                            "agent": "manager",
                            "locked": True,
                        },
                        "worker_role": assignment,
                        "independent_reviewer": {
                            "mode": "manual",
                            "agent": "reviewer",
                            "locked": True,
                        },
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return config_path

    def _router(
        self,
        root: Path,
        *,
        assignment: dict,
        worker_a_enabled: bool = True,
    ) -> tuple[RoutingService, CouncilStore, RegistryService]:
        config = load_config(
            self._write_config(
                root,
                assignment=assignment,
                worker_a_enabled=worker_a_enabled,
            )
        )
        store = CouncilStore(config.state_dir / "council.db")
        registry = RegistryService(store)
        registry.sync_from_config(config)
        return (
            RoutingService(
                config=config,
                store=store,
                registry=registry,
                adapters=build_adapters(config),
            ),
            store,
            registry,
        )

    def test_manual_assignment_resolves_and_is_persisted(self):
        with TemporaryDirectory() as temp:
            router, store, _ = self._router(
                Path(temp),
                assignment={
                    "mode": "manual",
                    "agent": "worker_a",
                    "locked": True,
                    "constraints": {"required_capabilities": ["coding"]},
                },
            )
            run_id = store.create_run("manual")
            result = router.resolve(
                run_id=run_id,
                role_key="worker_role",
                task_key="work",
            )
            self.assertEqual(result.agent_id, "worker_a")
            self.assertEqual(result.reason_code, "manual_assignment")
            decision = router.decisions(run_id)[0]
            self.assertEqual(decision["status"], "resolved")
            self.assertEqual(decision["selected_agent_id"], "worker_a")

    def test_manual_assignment_fails_without_silent_fallback(self):
        with TemporaryDirectory() as temp:
            router, store, _ = self._router(
                Path(temp),
                assignment={
                    "mode": "manual",
                    "agent": "worker_a",
                    "locked": True,
                },
                worker_a_enabled=False,
            )
            run_id = store.create_run("manual failure")
            with self.assertRaisesRegex(RoutingError, "agent_disabled"):
                router.resolve(
                    run_id=run_id,
                    role_key="worker_role",
                )
            decisions = router.decisions(run_id)
            self.assertEqual(decisions[0]["status"], "failed")
            self.assertEqual(
                decisions[0]["rejected_candidates"][0]["agent_id"],
                "worker_a",
            )

    def test_auto_uses_capability_and_availability_evidence(self):
        with TemporaryDirectory() as temp:
            router, store, registry = self._router(
                Path(temp),
                assignment={
                    "mode": "auto",
                    "constraints": {"required_capabilities": ["coding"]},
                },
            )
            registry.upsert_discovery_record(
                record_id="configured:worker_a",
                agent_id="worker_a",
                display_name="worker_a",
                target_kind="configured_agent",
                adapter_type="mock",
                executable_status="missing",
                authentication_status="not_applicable",
                permission_status="not_applicable",
                connectivity_status="not_checked",
            )
            self.assertEqual(
                [item["role_key"] for item in router.worker_cards()],
                ["worker_role"],
            )
            run_id = store.create_run("auto")
            result = router.resolve(
                run_id=run_id,
                role_key="worker_role",
            )
            self.assertEqual(result.agent_id, "worker_b")
            rejected = router.decisions(run_id)[0]["rejected_candidates"]
            worker_a = next(
                item for item in rejected if item["agent_id"] == "worker_a"
            )
            self.assertIn("unavailable", worker_a["reason_codes"])

    def test_hybrid_falls_back_but_lock_disables_fallback(self):
        with TemporaryDirectory() as temp:
            router, store, registry = self._router(
                Path(temp),
                assignment={
                    "mode": "hybrid",
                    "agent": "worker_a",
                    "constraints": {"required_capabilities": ["coding"]},
                },
                worker_a_enabled=False,
            )
            run_id = store.create_run("hybrid")
            result = router.resolve(
                run_id=run_id,
                role_key="worker_role",
            )
            self.assertEqual(result.agent_id, "worker_b")
            self.assertEqual(result.reason_code, "hybrid_fallback")

            registry.assign_role(
                "worker_role",
                mode="hybrid",
                agent_id="worker_a",
                locked=True,
                constraints={"required_capabilities": ["coding"]},
            )
            locked_run = store.create_run("locked")
            with self.assertRaises(RoutingError):
                router.resolve(
                    run_id=locked_run,
                    role_key="worker_role",
                )
            rejected = router.decisions(locked_run)[0]["rejected_candidates"]
            self.assertEqual(
                {item["agent_id"] for item in rejected},
                {"worker_a"},
            )

    def test_cost_and_latency_constraints_use_history(self):
        with TemporaryDirectory() as temp:
            router, store, registry = self._router(
                Path(temp),
                assignment={
                    "mode": "auto",
                    "constraints": {
                        "required_capabilities": ["coding"],
                        "max_average_cost": 0.5,
                        "max_average_latency_ms": 250,
                    },
                },
            )
            history_run = store.create_run("history")
            self._insert_usage(
                store,
                history_run,
                agent_id="worker_a",
                provider_id="provider-a",
                model_id="model-a",
                duration_ms=20,
                cost="1",
            )
            self._insert_usage(
                store,
                history_run,
                agent_id="worker_b",
                provider_id="provider-b",
                model_id="model-b",
                duration_ms=200,
                cost="0.2",
            )
            run_id = store.create_run("cost latency")
            result = router.resolve(
                run_id=run_id,
                role_key="worker_role",
            )
            self.assertEqual(result.agent_id, "worker_b")
            rejected = router.decisions(run_id)[0]["rejected_candidates"]
            worker_a = next(
                item for item in rejected if item["agent_id"] == "worker_a"
            )
            self.assertIn("cost_limit_exceeded", worker_a["reason_codes"])

            registry.assign_role(
                "worker_role",
                mode="auto",
                constraints={
                    "required_capabilities": ["coding"],
                    "max_average_cost": 0.5,
                    "max_average_latency_ms": 100,
                },
            )
            failed_run = store.create_run("latency failure")
            with self.assertRaisesRegex(
                RoutingError,
                "cost_limit_exceeded|latency_limit_exceeded",
            ):
                router.resolve(
                    run_id=failed_run,
                    role_key="worker_role",
                )

    def test_unknown_cost_is_not_treated_as_zero(self):
        with TemporaryDirectory() as temp:
            router, store, _ = self._router(
                Path(temp),
                assignment={
                    "mode": "auto",
                    "constraints": {
                        "required_capabilities": ["coding"],
                        "max_average_cost": 1,
                    },
                },
            )
            run_id = store.create_run("unknown")
            with self.assertRaisesRegex(RoutingError, "cost_unknown"):
                router.resolve(
                    run_id=run_id,
                    role_key="worker_role",
                )

    def test_required_provider_separation_is_enforced(self):
        with TemporaryDirectory() as temp:
            router, store, _ = self._router(
                Path(temp),
                assignment={
                    "mode": "auto",
                    "constraints": {
                        "required_capabilities": ["coding"],
                        "separation": {
                            "roles": ["decision_manager"],
                            "dimensions": ["provider"],
                        },
                    },
                },
            )
            run_id = store.create_run("separation")
            router.resolve(
                run_id=run_id,
                role_key="decision_manager",
            )
            worker = router.resolve(
                run_id=run_id,
                role_key="worker_role",
            )
            self.assertEqual(worker.provider_id, "provider-b")
            rejected = router.decisions(run_id)[1]["rejected_candidates"]
            worker_a = next(
                item for item in rejected if item["agent_id"] == "worker_a"
            )
            self.assertIn(
                "provider_separation_violation",
                worker_a["reason_codes"],
            )

    def test_hard_budget_state_blocks_automatic_routing(self):
        with TemporaryDirectory() as temp:
            router, store, _ = self._router(
                Path(temp),
                assignment={
                    "mode": "auto",
                    "constraints": {
                        "required_capabilities": ["coding"],
                    },
                },
            )
            history_run = store.create_run("budget history")
            self._insert_usage(
                store,
                history_run,
                agent_id="worker_a",
                provider_id="provider-a",
                model_id="model-a",
                duration_ms=10,
                cost="0",
            )
            with store.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO budget_policies(
                        id, scope_type, scope_key, metric,
                        warning_limit, hard_limit, currency,
                        source, created_at, updated_at
                    ) VALUES (
                        'hard-project-tokens', 'project', 'routing-test',
                        'tokens', NULL, '10', NULL, 'user', ?, ?
                    )
                    """,
                    (utc_now(), utc_now()),
                )
            run_id = store.create_run("budget blocked")
            with self.assertRaisesRegex(RoutingError, "hard_budget_reached"):
                router.resolve(
                    run_id=run_id,
                    role_key="worker_role",
                )

    @staticmethod
    def _insert_usage(
        store: CouncilStore,
        run_id: str,
        *,
        agent_id: str,
        provider_id: str,
        model_id: str,
        duration_ms: int,
        cost: str,
    ) -> None:
        with store.connect() as conn:
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
                ) VALUES (?, ?, NULL, 'routing-test', ?, 'worker', ?, ?,
                    'work', 'completed', 1, 'actual',
                    5, 5, 10, 'estimated', ?, 'actual',
                    ?, 'USD', 'estimated', '{}', ?)
                """,
                (
                    str(uuid4()),
                    run_id,
                    agent_id,
                    provider_id,
                    model_id,
                    duration_ms,
                    cost,
                    utc_now(),
                ),
            )


if __name__ == "__main__":
    unittest.main()
