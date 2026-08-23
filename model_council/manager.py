from __future__ import annotations

import json
import re
from typing import Any

from .adapters.base import AgentAdapter
from .types import AgentRequest, PlannedTask


PLAN_INSTRUCTION = """
请把总目标拆成适合不同专业模型执行的任务。
只返回一个 JSON 对象，不要加入解释或 Markdown 代码块。
格式：
{
  "tasks": [
    {
      "key": "唯一短键",
      "title": "任务标题",
      "instruction": "明确、可验收的任务指令",
      "agent": "必须是提供的工作模型名称之一",
      "depends_on": ["可选的上游任务key"]
    }
  ]
}
任务数应为 1 到工作模型数量之间。只有确实需要上游成果时才添加依赖。
"""


class Manager:
    def __init__(self, name: str, adapter: AgentAdapter):
        self.name = name
        self.adapter = adapter

    def plan(
        self,
        run_id: str,
        goal: str,
        workers: list[dict[str, Any]],
    ) -> list[PlannedTask]:
        response = self.adapter.invoke(
            AgentRequest(
                run_id=run_id,
                task_id="planning",
                mode="plan",
                goal=goal,
                instruction=PLAN_INSTRUCTION,
                sender="orchestrator",
                recipient=self.name,
                metadata={"workers": workers},
                context=json.dumps(workers, ensure_ascii=False, indent=2),
            )
        )
        data = self._parse_json_object(response.content)
        tasks_raw = data.get("tasks")
        if not isinstance(tasks_raw, list) or not tasks_raw:
            raise ValueError("manager plan must contain a non-empty tasks array")
        allowed = {worker["name"] for worker in workers}
        planned: list[PlannedTask] = []
        keys: set[str] = set()
        for item in tasks_raw:
            if not isinstance(item, dict):
                raise ValueError("each planned task must be an object")
            key = str(item.get("key", "")).strip()
            agent = str(item.get("agent", "")).strip()
            if not key or key in keys:
                raise ValueError(f"invalid or duplicate task key {key!r}")
            if agent not in allowed:
                raise ValueError(f"manager selected unknown worker {agent!r}")
            depends = tuple(str(x) for x in item.get("depends_on", []))
            planned.append(
                PlannedTask(
                    key=key,
                    title=str(item.get("title", key)).strip(),
                    instruction=str(item.get("instruction", "")).strip(),
                    agent=agent,
                    depends_on=depends,
                )
            )
            keys.add(key)
        for task in planned:
            unknown = set(task.depends_on) - keys
            if unknown:
                raise ValueError(
                    f"task {task.key!r} has unknown dependencies {sorted(unknown)}"
                )
            if task.key in task.depends_on:
                raise ValueError(f"task {task.key!r} cannot depend on itself")
        self._validate_acyclic(planned)
        return planned

    def synthesize(
        self,
        run_id: str,
        goal: str,
        context: str,
    ) -> str:
        response = self.adapter.invoke(
            AgentRequest(
                run_id=run_id,
                task_id="synthesis",
                mode="synthesize",
                goal=goal,
                instruction=(
                    "综合所有专业结果和独立审查。解决冲突，保留重要不确定性，"
                    "输出一份自洽、可执行的最终报告。"
                ),
                sender="orchestrator",
                recipient=self.name,
                context=context,
            )
        )
        return response.content

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any]:
        stripped = text.strip()
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
            if not match:
                raise ValueError("manager did not return a JSON object")
            data = json.loads(match.group(0))
        if not isinstance(data, dict):
            raise ValueError("manager response must be a JSON object")
        return data

    @staticmethod
    def _validate_acyclic(tasks: list[PlannedTask]) -> None:
        graph = {task.key: set(task.depends_on) for task in tasks}
        resolved: set[str] = set()
        while len(resolved) < len(graph):
            ready = {
                key
                for key, dependencies in graph.items()
                if key not in resolved and dependencies <= resolved
            }
            if not ready:
                raise ValueError("manager plan contains a dependency cycle")
            resolved.update(ready)
