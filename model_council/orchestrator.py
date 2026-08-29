from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import build_adapters
from .artifacts import ArtifactStore
from .config import CouncilConfig
from .manager import Manager
from .registry import RegistryService
from .store import CouncilStore
from .types import AgentRequest, ArtifactRef, RunStatus, TaskStatus


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
        self.manager = Manager(config.manager, self.adapters[config.manager])

    def run(self, goal: str) -> RunResult:
        run_id = self.store.create_run(goal)
        try:
            workers = self._worker_cards()
            plan = self.manager.plan(run_id, goal, workers)
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
                sender=self.config.manager,
                recipient="orchestrator",
                message_type="decision",
                body={
                    "event": "plan_accepted",
                    "tasks": [
                        {
                            "key": item.key,
                            "agent": item.agent,
                            "depends_on": list(item.depends_on),
                        }
                        for item in plan
                    ],
                },
            )
            outputs = self._execute_plan(run_id, goal, plan, task_ids)
            review_ref = self._review(run_id, goal, outputs)
            context = self._render_context(outputs, review_ref)
            final_text = self.manager.synthesize(run_id, goal, context)
            final_ref = self.artifacts.put_text(
                run_id=run_id,
                task_id=None,
                name="final-report.md",
                content=final_text,
                producer=self.store.identity_for_agent(self.config.manager),
                contributors=self.store.contributor_identities(
                    [
                        *(ref.id for ref in outputs.values()),
                        *([review_ref.id] if review_ref else []),
                    ]
                ),
                final_integrator=self.store.identity_for_agent(
                    self.config.manager
                ),
                reviewer=(
                    self.store.identity_for_agent(self.config.reviewer)
                    if review_ref and self.config.reviewer
                    else None
                ),
            )
            self.store.add_message(
                run_id=run_id,
                task_id=None,
                sender=self.config.manager,
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
        excluded = {self.config.manager}
        if self.config.reviewer:
            excluded.add(self.config.reviewer)
        result = []
        for name in self.config.agents:
            if name in excluded:
                continue
            card = self.config.card(name)
            result.append(
                {
                    "name": card.name,
                    "role": card.role,
                    "description": card.description,
                    "capabilities": list(card.capabilities),
                    "boundaries": list(card.boundaries),
                }
            )
        if not result:
            raise ValueError("at least one worker agent is required")
        return result

    def _execute_plan(self, run_id, goal, plan, task_ids) -> dict[str, ArtifactRef]:
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
                            recipient=self.config.manager,
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
            sender=self.config.manager,
            recipient=item.agent,
            message_type="task_assignment",
            body={
                "title": item.title,
                "instruction": item.instruction,
                "depends_on": list(item.depends_on),
            },
            artifact_ids=[ref.id for ref in dependencies],
        )
        response = self.adapters[item.agent].invoke(
            AgentRequest(
                run_id=run_id,
                task_id=task_id,
                mode="work",
                goal=goal,
                instruction=item.instruction,
                sender=self.config.manager,
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
            recipient=self.config.manager,
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
    ) -> ArtifactRef | None:
        if not self.config.reviewer:
            return None
        reviewer = self.config.reviewer
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
            sender=self.config.manager,
            recipient=reviewer,
            message_type="task_assignment",
            body={"event": "independent_review"},
            artifact_ids=[ref.id for ref in outputs.values()],
        )
        try:
            response = self.adapters[reviewer].invoke(
                AgentRequest(
                    run_id=run_id,
                    task_id=task_id,
                    mode="review",
                    goal=goal,
                    instruction=(
                        "检查所有专业成果的冲突、遗漏、不可验证假设和执行风险。"
                    ),
                    sender=self.config.manager,
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
                recipient=self.config.manager,
                message_type="review",
                body={"event": "review_completed"},
                artifact_ids=[ref.id],
            )
            return ref
        except Exception as exc:
            self.store.set_task_status(task_id, TaskStatus.FAILED, error=str(exc))
            return None

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
