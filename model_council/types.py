from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProvenanceDisplayMode(StrEnum):
    COMPACT = "compact"
    DETAILED = "detailed"
    HIDDEN = "hidden"


@dataclass(frozen=True)
class AgentCard:
    name: str
    role: str
    description: str
    capabilities: tuple[str, ...] = ()
    boundaries: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtifactIdentity:
    """Immutable Agent/Provider/Model identity captured at production time."""

    agent_id: str
    provider_id: str | None = None
    model_id: str | None = None


@dataclass(frozen=True)
class ArtifactRef:
    id: str
    name: str
    media_type: str
    sha256: str
    path: str


@dataclass
class AgentRequest:
    run_id: str
    task_id: str
    mode: str
    goal: str
    instruction: str
    sender: str
    recipient: str
    context: str = ""
    artifacts: list[ArtifactRef] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlannedTask:
    key: str
    title: str
    instruction: str
    agent: str
    depends_on: tuple[str, ...] = ()
