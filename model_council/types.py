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


class ExecutableStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class AuthenticationStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"
    CONFIGURED = "configured"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class PermissionStatus(StrEnum):
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    UNRESTRICTED = "unrestricted"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class ConnectivityStatus(StrEnum):
    NOT_CHECKED = "not_checked"
    PASSED = "passed"
    FAILED = "failed"
    NOT_SUPPORTED = "not_supported"


class MeasurementSource(StrEnum):
    ACTUAL = "actual"
    PROVIDER_REPORTED = "provider_reported"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class BudgetScope(StrEnum):
    PROJECT = "project"
    RUN = "run"
    ROLE = "role"


class BudgetMetric(StrEnum):
    TOKENS = "tokens"
    COST = "cost"


class BudgetLevel(StrEnum):
    WARNING = "warning"
    HARD = "hard"
    UNAVAILABLE = "unavailable"


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
    role_key: str | None = None
