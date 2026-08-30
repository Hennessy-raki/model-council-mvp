from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import unittest

from model_council.adapters.base import AgentAdapter
from model_council.adapters.openai_compatible import OpenAICompatibleAdapter
from model_council.cli import main
from model_council.config import load_config
from model_council.ledger import BudgetExceededError, UsageLedger
from model_council.orchestrator import Orchestrator
from model_council.registry import RegistryService
from model_council.store import CouncilStore
from model_council.types import AgentCard, AgentRequest, AgentResponse


class StaticAdapter(AgentAdapter):
    def __init__(
        self,
        card,
        *,
        metadata=None,
        balance=None,
    ):
        super().__init__(card)
        self.metadata = metadata or {}
        self.balance = balance
        self.invoke_calls = 0
        self.balance_calls = 0

    def invoke(self, request):
        self.invoke_calls += 1
        return AgentResponse("ledger response", deepcopy(self.metadata))

    def billing_capabilities(self):
        return {"provider_balance": self.balance is not None}

    def provider_balance(self):
        self.balance_calls += 1
        if self.balance is None:
            return super().provider_balance()
        return deepcopy(self.balance)


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size=-1):
        data = json.dumps(self.payload).encode("utf-8")
        return data if size is None or size < 0 else data[:size]


class LedgerTests(unittest.TestCase):
    def _write_config(
        self,
        root: Path,
        *,
        estimation: bool = True,
        pricing: dict | None = None,
        budgets: dict | None = None,
        workflow: bool = False,
    ) -> Path:
        agents = {
            "manager": {
                "type": "mock",
                "provider": "provider-a",
                "model": "model-a",
                "role": "Manager",
            }
        }
        reviewer = None
        if workflow:
            agents["worker"] = {
                "type": "mock",
                "provider": "provider-a",
                "model": "model-a",
                "role": "Worker",
            }
            agents["reviewer"] = {
                "type": "mock",
                "provider": "provider-a",
                "model": "model-a",
                "role": "Reviewer",
            }
            reviewer = "reviewer"
        model = {
            "provider": "provider-a",
            "display_name": "Model A",
        }
        if pricing is not None:
            model["pricing"] = pricing
        payload = {
            "project_name": "ledger-project",
            "state_dir": "runtime",
            "manager": "manager",
            "providers": {
                "provider-a": {
                    "kind": "test",
                    "display_name": "Provider A",
                }
            },
            "models": {"model-a": model},
            "agents": agents,
            "settings": {"usage_estimation_enabled": estimation},
            "budgets": budgets or {},
        }
        if reviewer:
            payload["reviewer"] = reviewer
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return config_path

    def _ledger(self, config_path: Path):
        config = load_config(config_path)
        store = CouncilStore(config.state_dir / "council.db")
        registry = RegistryService(store)
        registry.sync_from_config(config)
        return config, store, registry, UsageLedger(config, store, registry)

    @staticmethod
    def _request(run_id: str):
        return AgentRequest(
            run_id=run_id,
            task_id="task",
            mode="work",
            goal="test",
            instruction="return a result",
            sender="manager",
            recipient="manager",
        )

    def test_provider_reported_usage_and_actual_cost_are_normalized(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(Path(temp))
            config, store, _, ledger = self._ledger(config_path)
            run_id = store.create_run("ledger")
            adapter = StaticAdapter(
                config.card("manager"),
                metadata={
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 8,
                    },
                    "cost": {
                        "amount": "0.25",
                        "currency": "USD",
                        "source": "actual",
                    },
                },
            )

            ledger.invoke("manager", adapter, self._request(run_id))

            event = ledger.events(run_id=run_id)[0]
            self.assertEqual(event["input_tokens"], 12)
            self.assertEqual(event["output_tokens"], 8)
            self.assertEqual(event["total_tokens"], 20)
            self.assertEqual(event["token_source"], "provider_reported")
            self.assertEqual(event["cost_amount"], "0.25")
            self.assertEqual(event["cost_source"], "actual")
            self.assertEqual(event["request_source"], "actual")
            self.assertEqual(event["duration_source"], "actual")

    def test_missing_usage_is_estimated_with_configured_pricing(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(
                Path(temp),
                pricing={
                    "input_per_million": 1,
                    "output_per_million": 2,
                    "per_request": "0.01",
                    "currency": "USD",
                },
            )
            config, store, _, ledger = self._ledger(config_path)
            run_id = store.create_run("ledger")
            adapter = StaticAdapter(config.card("manager"))

            ledger.invoke("manager", adapter, self._request(run_id))

            event = ledger.events(run_id=run_id)[0]
            self.assertEqual(event["token_source"], "estimated")
            self.assertGreater(event["total_tokens"], 0)
            self.assertEqual(event["cost_source"], "estimated")
            self.assertEqual(event["cost_currency"], "USD")

    def test_missing_usage_remains_unavailable_when_estimation_is_disabled(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(
                Path(temp),
                estimation=False,
            )
            config, store, _, ledger = self._ledger(config_path)
            run_id = store.create_run("ledger")

            ledger.invoke(
                "manager",
                StaticAdapter(config.card("manager")),
                self._request(run_id),
            )

            event = ledger.events(run_id=run_id)[0]
            self.assertEqual(event["token_source"], "unavailable")
            self.assertIsNone(event["total_tokens"])
            self.assertEqual(event["cost_source"], "unavailable")

    def test_full_workflow_records_project_and_role_totals(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(
                Path(temp),
                pricing={
                    "input_per_million": 0,
                    "output_per_million": 0,
                    "currency": "USD",
                },
                workflow=True,
            )
            orchestrator = Orchestrator(load_config(config_path))
            result = orchestrator.run("ledger workflow")

            summary = orchestrator.ledger.summary(run_id=result.run_id)

            self.assertEqual(summary["total"]["calls"], 4)
            self.assertGreater(summary["total"]["total_tokens"], 0)
            self.assertEqual(summary["total"]["costs"]["USD"], "0")
            self.assertEqual(
                {item["role"] for item in summary["roles"]},
                {"Manager", "Worker", "Reviewer"},
            )
            output = StringIO()
            with redirect_stdout(output):
                main(
                    [
                        "ledger",
                        "summary",
                        "--run",
                        result.run_id,
                        "--config",
                        str(config_path),
                    ]
                )
            self.assertEqual(
                json.loads(output.getvalue())["total"]["calls"],
                4,
            )

    def test_warning_and_hard_budget_block_followup_call(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(
                Path(temp),
                budgets={
                    "tiny-token-budget": {
                        "scope": "project",
                        "metric": "tokens",
                        "warning": 1,
                        "hard": 1,
                    }
                },
            )
            config, store, _, ledger = self._ledger(config_path)
            run_id = store.create_run("budget")
            adapter = StaticAdapter(config.card("manager"))

            ledger.invoke("manager", adapter, self._request(run_id))
            with self.assertRaises(BudgetExceededError):
                ledger.invoke("manager", adapter, self._request(run_id))

            self.assertEqual(adapter.invoke_calls, 1)
            self.assertEqual(
                {item["level"] for item in ledger.alerts(run_id)},
                {"warning", "hard"},
            )

    def test_hard_budget_blocks_when_prior_cost_is_unavailable(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(
                Path(temp),
                estimation=False,
                budgets={
                    "cost-budget": {
                        "scope": "project",
                        "metric": "cost",
                        "currency": "USD",
                        "hard": 1,
                    }
                },
            )
            config, store, _, ledger = self._ledger(config_path)
            run_id = store.create_run("budget")
            adapter = StaticAdapter(config.card("manager"))

            ledger.invoke("manager", adapter, self._request(run_id))
            with self.assertRaisesRegex(
                BudgetExceededError,
                "cannot be enforced",
            ):
                ledger.invoke("manager", adapter, self._request(run_id))

            self.assertEqual(adapter.invoke_calls, 1)
            self.assertEqual(ledger.alerts(run_id)[0]["level"], "unavailable")

    def test_user_budget_override_survives_config_sync(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(
                Path(temp),
                budgets={
                    "project-budget": {
                        "scope": "project",
                        "metric": "tokens",
                        "warning": 100,
                    }
                },
            )
            config, store, registry, ledger = self._ledger(config_path)
            ledger.set_budget_policy(
                policy_id="project-budget",
                scope="project",
                scope_key=config.project_name,
                metric="tokens",
                warning=10,
                hard=20,
            )

            UsageLedger(config, store, registry)
            policy = ledger.budget_policies()[0]

            self.assertEqual(policy["source"], "user")
            self.assertEqual(policy["warning_limit"], "10")
            self.assertEqual(policy["hard_limit"], "20")

    def test_provider_balance_is_queried_only_when_supported(self):
        with TemporaryDirectory() as temp:
            config_path = self._write_config(Path(temp))
            config, _, _, ledger = self._ledger(config_path)
            unsupported = StaticAdapter(config.card("manager"))

            unavailable = ledger.provider_balance(
                "provider-a",
                {"manager": unsupported},
            )

            self.assertEqual(unavailable["status"], "unavailable")
            self.assertEqual(unsupported.balance_calls, 0)

            supported = StaticAdapter(
                config.card("manager"),
                balance={
                    "amount": "12.50",
                    "currency": "USD",
                    "source": "provider_reported",
                },
            )
            available = ledger.provider_balance(
                "provider-a",
                {"manager": supported},
            )

            self.assertEqual(available["status"], "available")
            self.assertEqual(available["amount"], "12.5")
            self.assertEqual(supported.balance_calls, 1)
            self.assertEqual(
                ledger.balance_snapshots("provider-a")[0]["source"],
                "provider_reported",
            )

    def test_openai_balance_capability_requires_configured_endpoint(self):
        adapter = OpenAICompatibleAdapter(
            AgentCard("api", "API", "API"),
            {
                "base_url": "https://provider.example/v1",
                "model": "model-a",
                "api_key_env": "LEDGER_TEST_API_KEY",
                "balance_endpoint": "/account/balance",
                "balance_amount_field": "data.amount",
                "balance_currency_field": "data.currency",
            },
        )
        response = FakeHttpResponse(
            {"data": {"amount": "7.25", "currency": "eur"}}
        )
        with patch.dict(os.environ, {"LEDGER_TEST_API_KEY": "test-value"}):
            with patch(
                "model_council.adapters.openai_compatible."
                "_NO_REDIRECT_OPENER.open",
                return_value=response,
            ):
                balance = adapter.provider_balance()

        self.assertTrue(
            adapter.billing_capabilities()["provider_balance"]
        )
        self.assertEqual(balance["amount"], "7.25")
        self.assertEqual(balance["currency"], "EUR")


if __name__ == "__main__":
    unittest.main()
