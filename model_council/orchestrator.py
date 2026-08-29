from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .adapters import build_adapters
from .artifacts import ArtifactStore
from .config import CouncilConfig
from .discovery import DiscoveryService
from .ledger import UsageLedger
from .manager import Manager
from .registry import RegistryService
from .routing import RoutingService
from .store import CouncilStore
from .types import AgentRequest, ArtifactRef, PlannedTask, RunStatus, TaskStatus


@dataclass(frozen=True)
class RunResult:
    run_id: str
    final_artifact: ArtifactRef
    final_text: str


class Orchestrator:
    def __init__(self, config: CouncilConfig):
        self.config = config
        self.store = CouncilStore(config.state_dir / "council.db")
        self.registry = RegistryService(self.store)
        self.registry.sync_from_config(config)
        self.artifacts = ArtifactStore(config.state_dir / "artifacts", self.store)
        self.adapters = build_adapters(config)
        self.ledger = UsageLedger(config, self.store, self.registry)
        self.router = RoutingService(
            config=config,
            store=self.store,
            registry=self.registry,
            adapters=self.adapters,
        )
        if bool(
            self.registry.setting_value(
                "auto_discovery_on_start",
                False,
            )
        ):
            DiscoveryService(
                config=config,
                registry=self.registry,
                adapters=self.adapters,
            ).scan()
        self.manager = Manager(
            config.manager,
            self.adapters[config.manager],
            invoke=lambda request: self._invoke_agent(
                config.manager,
                request,
            ),
        )

    def run(self, goal: str) -> RunResult:
        run_id = self.store.create_run(goal)
        try:
            manager_route = self.router.resolve(
                run_id=run_id,
                role_key="decision_manager",
                task_key="planning",
                preferred_agent=self.config.manager,
            )
            manager_id = manager_route.agent_id
            manager = Manager(
                manager_id,
                self.adapters[manager_id],
                invoke=lambda request: self._invoke_agent(
                    manager_id,
                    request,
                ),
            )
            workers = self._worker_cards()
            plan = manager.plan(run_id, goal, workers)
            plan = self._resolve_plan(run_id, plan)
            task_ids: dict[str, str] = {}
            for item in plan:
                task_ids[item.key] = self.store.add_task(
                    run_id=run_id,
                    task_key=item.key,
                    title=item.title,
                    instruction=item.instruction,
                    agent=item.agent,
                    depends_on=list(item.depends_on),
                )
            self.store.add_message(
                run_id=run_id,
                task_id=None,
                sender=manager_id,
                recipient="orchestrator",
                message_type="decision",
                body={
                    "event": "plan_accepted",
                    "tasks": [
                        {
                            "key": item.key,
                            "role": item.role_key,
                            "agent": item.agent,
                            "depends_on": list(item.depends_on),
                        }
                        for item in plan
                    ],
                },
            )
            outputs = self._execute_plan(
                run_id,
                goal,
                plan,
                task_ids,
                manager_id,
            )
            review_ref, reviewer_id = self._review(
                run_id,
                goal,
                outputs,
                manager_id,
            )
            context = self._render_context(outputs, review_ref)
            final_text = manager.synthesize(run_id, goal, context)
            final_ref = self.artifacts.put_text(
                run_id=run_id,
                task_id=None,
                name="final-report.md",
                content=final_text,
                producer=self.store.identity_for_agent(manager_id),
                contributors=self.store.contributor_identities(
                    [
                        *(ref.id for ref in outputs.values()),
                        *([review_ref.id] if review_ref else []),
                    ]
                ),
                final_integrator=self.store.identity_for_agent(
                    manager_id
                ),
                reviewer=(
                    self.store.identity_for_agent(reviewer_id)
                    if review_ref and reviewer_id
                    else None
                ),
            )
            self.store.add_message(
                run_id=run_id,
                task_id=None,
                sender=manager_id,
                recipient="user",
                message_type="decision",
                body={"event": "final_synthesis"},
                artifact_ids=[final_ref.id],
            )
            self.store.finish_run(
                run_id,
                RunStatus.COMPLETED,
                final_artifact_id=final_ref.id,
            )
            return RunResult(run_id, final_ref, final_text)
        except Exception as exc:
            self.store.finish_run(run_id, RunStatus.FAILED, error=str(exc))
            raise

    def _worker_cards(self) -> list[dict[str, Any]]:
        return self.router.worker_cards()

    def _resolve_plan(
        self,
        run_id: str,
        plan: list[PlannedTask],
    ) -> list[PlannedTask]:
        resolved = []
        for item in plan:
            role_key = item.role_key or f"agent:{item.agent}"
            route = self.router.resolve(
                run_id=run_id,
                role_key=role_key,
                task_key=item.key,
                preferred_agent=item.agent or None,
            )
            resolved.append(
                replace(
                    item,
                    agent=route.agent_id,
                    role_key=role_key,
                )
            )
        return resolved

    def _execute_plan(
        self,
        run_id,
        goal,
        plan,
        task_ids,
        manager_id,
    ) -> dict[str, ArtifactRef]:
        outputs: dict[str, ArtifactRef] = {}
        pending = {item.key: item for item in plan}
        failed: set[str] = set()
        while pending:
            blocked = [
                item for item in pending.values() if set(item.depends_on) & failed
            ]
            for item in blocked:
                self.store.set_task_status(
                    task_ids[item.key],
                    TaskStatus.BLOCKED,
                    error="upstream task failed",
                )
                failed.add(item.key)
                pending.pop(item.key)

            ready = [
                item
                for item in pending.values()
                if set(item.depends_on) <= set(outputs)
            ]
            if not ready and pending:
                raise RuntimeError("no runnable tasks remain; dependency graph is stuck")
            with ThreadPoolExecutor(max_workers=self.config.max_parallel) as pool:
                futures = {
                    pool.submit(
                        self._execute_one,
                        run_id,
                        goal,
                        item,
                        task_ids[item.key],
                        outputs,
                        manager_id,
                    ): item
                    for item in ready
                }
                for future in as_completed(futures):
                    item = futures[future]
                    try:
                        outputs[item.key] = future.result()
                    except Exception as exc:
                        failed.add(item.key)
                        self.store.set_task_status(
                            task_ids[item.key],
                            TaskStatus.FAILED,
                            error=str(exc),
                        )
                        self.store.add_message(
                            run_id=run_id,
                            task_id=task_ids[item.key],
                            sender=item.agent,
                            recipient=manager_id,
                            message_type="error",
                            body={"error": str(exc)},
                        )
                    finally:
                        pending.pop(item.key, None)
        if not outputs:
            raise RuntimeError("all worker tasks failed")
        return outputs

    def _execute_one(
        self,
        run_id,
        goal,
        item,
        task_id,
        prior_outputs: dict[str, ArtifactRef],
        manager_id: str,
    ) -> ArtifactRef:
        self.store.set_task_status(task_id, TaskStatus.RUNNING)
        dependencies = [prior_outputs[key] for key in item.depends_on]
        context_parts = []
        for ref in dependencies:
            context_parts.append(
                f"## 上游Artifact：{ref.name}\n\n{self.artifacts.read_text(ref)}"
            )
        self.store.add_message(
            run_id=run_id,
            task_id=task_id,
            sender=manager_id,
            recipient=item.agent,
            message_type="task_assignment",
            body={
                "title": item.title,
                "instruction": item.instruction,
                "depends_on": list(item.depends_on),
                "role": item.role_key,
            },
            artifact_ids=[ref.id for ref in dependencies],
        )
        response = self._invoke_agent(
            item.agent,
            AgentRequest(
                run_id=run_id,
                task_id=task_id,
                mode="work",
                goal=goal,
                instruction=item.instruction,
                sender=manager_id,
                recipient=item.agent,
                context="\n\n".join(context_parts),
                artifacts=dependencies,
            )
        )
        ref = self.artifacts.put_text(
            run_id=run_id,
            task_id=task_id,
            name=f"{item.key}-{item.agent}.md",
            content=response.content,
            producer=self.store.identity_for_agent(item.agent),
            contributors=self.store.contributor_identities(
                [ref.id for ref in dependencies]
            ),
        )
        self.store.set_task_status(
            task_id,
            TaskStatus.COMPLETED,
            output_artifact_id=ref.id,
        )
        self.store.add_message(
            run_id=run_id,
            task_id=task_id,
            sender=item.agent,
            recipient=manager_id,
            message_type="task_result",
            body={"title": item.title, "metadata": response.metadata},
            artifact_ids=[ref.id],
        )
        return ref

    def _review(
        self,
        run_id: str,
        goal: str,
        outputs: dict[str, ArtifactRef],
        manager_id: str,
    ) -> tuple[ArtifactRef | None, str | None]:
        role_keys = {
            item["role_key"] for item in self.registry.snapshot()["roles"]
        }
        if (
            not self.config.reviewer
            and "independent_reviewer" not in role_keys
        ):
            return None, None
        reviewer_route = self.router.resolve(
            run_id=run_id,
            role_key="independent_reviewer",
            task_key="independent_review",
            preferred_agent=self.config.reviewer,
        )
        reviewer = reviewer_route.agent_id
        task_id = self.store.add_task(
            run_id=run_id,
            task_key="independent_review",
            title="独立交叉审查",
            instruction="检查所有专业成果的冲突、遗漏、不可验证假设和执行风险。",
            agent=reviewer,
            depends_on=list(outputs),
        )
        self.store.set_task_status(task_id, TaskStatus.RUNNING)
        context = self._render_outputs(outputs)
        self.store.add_message(
            run_id=run_id,
            task_id=task_id,
            sender=manager_id,
            recipient=reviewer,
            message_type="task_assignment",
            body={"event": "independent_review"},
            artifact_ids=[ref.id for ref in outputs.values()],
        )
        try:
            response = self._invoke_agent(
                reviewer,
                AgentRequest(
                    run_id=run_id,
                    task_id=task_id,
                    mode="review",
                    goal=goal,
                    instruction=(
                        "检查所有专业成果的冲突、遗漏、不可验证假设和执行风险。"
                    ),
                    sender=manager_id,
                    recipient=reviewer,
                    context=context,
                    artifacts=list(outputs.values()),
                )
            )
            ref = self.artifacts.put_text(
                run_id=run_id,
                task_id=task_id,
                name="independent-review.md",
                content=response.content,
                producer=self.store.identity_for_agent(reviewer),
                contributors=self.store.contributor_identities(
                    [item.id for item in outputs.values()]
                ),
                reviewer=self.store.identity_for_agent(reviewer),
            )
            self.store.set_task_status(
                task_id,
                TaskStatus.COMPLETED,
                output_artifact_id=ref.id,
            )
            self.store.add_message(
                run_id=run_id,
                task_id=task_id,
                sender=reviewer,
                recipient=manager_id,
                message_type="review",
                body={"event": "review_completed"},
                artifact_ids=[ref.id],
            )
            return ref, reviewer
        except Exception as exc:
            self.store.set_task_status(task_id, TaskStatus.FAILED, error=str(exc))
            return None, reviewer

    def _invoke_agent(
        self,
        agent_id: str,
        request: AgentRequest,
    ):
        return self.ledger.invoke(
            agent_id,
            self.adapters[agent_id],
            request,
        )

    def _render_outputs(self, outputs: dict[str, ArtifactRef]) -> str:
        parts = []
        for key, ref in outputs.items():
            parts.append(f"# 专业成果：{key}\n\n{self.artifacts.read_text(ref)}")
        return "\n\n".join(parts)

    def _render_context(
        self,
        outputs: dict[str, ArtifactRef],
        review_ref: ArtifactRef | None,
    ) -> str:
        parts = [self._render_outputs(outputs)]
        if review_ref:
            parts.append(
                f"# 独立审查\n\n{self.artifacts.read_text(review_ref)}"
            )
        return "\n\n".join(parts)
