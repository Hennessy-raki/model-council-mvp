from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from .interoperability import InteroperabilityError
from .store import CouncilStore, utc_now
from .types import AgentRequest


OUTBOUND_CONTEXT_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "consumed",
    "blocked",
}
DEFAULT_EXCLUDED_PATTERNS = (
    r"(?i)(api[_-]?key|authorization|bearer|password|secret|token)\s*[:=]",
    r"(?i)-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----",
    r"(?i)[a-z]:\\users\\[^\\\s]+",
    r"(?i)/(?:home|users)/[^/\s]+",
)


class OutboundContextError(InteroperabilityError):
    pass


class OutboundContextApprovalRequired(OutboundContextError):
    def __init__(self, manifest_id: str):
        super().__init__(
            "outbound context requires a one-time human approval; "
            f"preview and approve manifest {manifest_id!r} locally before "
            "starting the Codex App Server"
        )
        self.manifest_id = manifest_id


@dataclass(frozen=True)
class OutboundContextPolicy:
    max_files: int
    max_total_bytes: int
    max_artifacts: int
    max_artifact_bytes: int
    allowed_sources: tuple[str, ...]
    excluded_patterns: tuple[str, ...]

    @classmethod
    def from_settings(cls, value: dict[str, Any]) -> "OutboundContextPolicy":
        return cls(
            max_files=int(value.get("max_files", 0)),
            max_total_bytes=int(value.get("max_total_bytes", 0)),
            max_artifacts=int(value.get("max_artifacts", 0)),
            max_artifact_bytes=int(value.get("max_artifact_bytes", 0)),
            allowed_sources=tuple(
                str(item) for item in value.get("allowed_sources", [])
            ),
            excluded_patterns=tuple(
                str(item)
                for item in value.get(
                    "excluded_patterns",
                    DEFAULT_EXCLUDED_PATTERNS,
                )
            ),
        )


class OutboundContextService:
    """Local, one-time consent records for exact App Server prompt bytes."""

    def __init__(self, store: CouncilStore):
        self.store = store

    def prepare(
        self,
        *,
        endpoint_id: str,
        agent_id: str,
        request: AgentRequest,
        prompt: str,
        source: str,
        policy: OutboundContextPolicy,
    ) -> dict[str, Any]:
        if source not in policy.allowed_sources:
            return self._blocked(
                endpoint_id=endpoint_id,
                agent_id=agent_id,
                request=request,
                prompt=prompt,
                source=source,
                reason=f"source {source!r} is not permitted",
            )
        if request.artifacts and len(request.artifacts) > policy.max_artifacts:
            return self._blocked(
                endpoint_id=endpoint_id,
                agent_id=agent_id,
                request=request,
                prompt=prompt,
                source=source,
                reason=(
                    f"artifact count {len(request.artifacts)} exceeds "
                    f"limit {policy.max_artifacts}"
                ),
            )
        artifact_items = []
        for artifact in request.artifacts:
            path = Path(artifact.path)
            try:
                size = path.stat().st_size
            except OSError:
                return self._blocked(
                    endpoint_id=endpoint_id,
                    agent_id=agent_id,
                    request=request,
                    prompt=prompt,
                    source=source,
                    reason=f"artifact {artifact.name!r} is unavailable locally",
                )
            if size > policy.max_artifact_bytes:
                return self._blocked(
                    endpoint_id=endpoint_id,
                    agent_id=agent_id,
                    request=request,
                    prompt=prompt,
                    source=source,
                    reason=(
                        f"artifact {artifact.name!r} is {size} bytes, exceeding "
                        f"limit {policy.max_artifact_bytes}"
                    ),
                )
            artifact_items.append(
                {
                    "name": artifact.name,
                    "media_type": artifact.media_type,
                    "sha256": artifact.sha256,
                    "bytes": size,
                }
            )
        prompt_bytes = prompt.encode("utf-8")
        if len(prompt_bytes) > policy.max_total_bytes:
            return self._blocked(
                endpoint_id=endpoint_id,
                agent_id=agent_id,
                request=request,
                prompt=prompt,
                source=source,
                reason=(
                    f"prompt is {len(prompt_bytes)} bytes, exceeding "
                    f"limit {policy.max_total_bytes}"
                ),
            )
        matches = _excluded_matches(prompt, policy.excluded_patterns)
        if matches:
            return self._blocked(
                endpoint_id=endpoint_id,
                agent_id=agent_id,
                request=request,
                prompt=prompt,
                source=source,
                reason=f"excluded context pattern matched: {matches[0]}",
            )
        items = _prompt_items(request, prompt, artifact_items)
        manifest = {
            "version": 1,
            "source": source,
            "prompt_sha256": sha256(prompt_bytes).hexdigest(),
            "total_bytes": len(prompt_bytes),
            "files": [],
            "artifacts": artifact_items,
            "items": items,
            "limits": {
                "max_files": policy.max_files,
                "max_total_bytes": policy.max_total_bytes,
                "max_artifacts": policy.max_artifacts,
                "max_artifact_bytes": policy.max_artifact_bytes,
            },
            "excluded_patterns": list(policy.excluded_patterns),
        }
        manifest_id = str(uuid4())
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO outbound_context_manifests(
                    id, endpoint_id, agent_id, run_id, task_id, source,
                    prompt_sha256, total_bytes, manifest_json, prompt_text,
                    status, reason, requested_at, decided_at, consumed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, ?, NULL, NULL)
                """,
                (
                    manifest_id,
                    endpoint_id,
                    agent_id,
                    request.run_id,
                    request.task_id,
                    source,
                    manifest["prompt_sha256"],
                    manifest["total_bytes"],
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    prompt,
                    utc_now(),
                ),
            )
        return self.manifest(manifest_id)

    def require_approved(
        self,
        *,
        manifest_id: str | None,
        endpoint_id: str,
        prompt: str,
    ) -> dict[str, Any]:
        if not manifest_id:
            prepared = self._latest_pending(endpoint_id, prompt)
            raise OutboundContextApprovalRequired(prepared["id"])
        item = self.manifest(manifest_id)
        if item["endpoint_id"] != endpoint_id:
            raise OutboundContextError(
                f"outbound context manifest {manifest_id!r} targets a different endpoint"
            )
        if item["status"] != "approved" or item["consumed_at"] is not None:
            raise OutboundContextError(
                f"outbound context manifest {manifest_id!r} is not approved and unused"
            )
        digest = sha256(prompt.encode("utf-8")).hexdigest()
        if digest != item["prompt_sha256"]:
            raise OutboundContextError(
                f"outbound context manifest {manifest_id!r} does not match the exact prompt"
            )
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE outbound_context_manifests
                SET status = 'consumed', consumed_at = ?
                WHERE id = ? AND status = 'approved' AND consumed_at IS NULL
                """,
                (utc_now(), manifest_id),
            ).rowcount
        if not updated:
            raise OutboundContextError(
                f"outbound context manifest {manifest_id!r} is not approved and unused"
            )
        return self.manifest(manifest_id)

    def decide(self, manifest_id: str, *, approve: bool, confirmation: str) -> None:
        item = self.manifest(manifest_id)
        if item["status"] != "pending":
            raise OutboundContextError(
                f"outbound context manifest {manifest_id!r} is not pending"
            )
        if approve and confirmation != item["prompt_sha256"]:
            raise OutboundContextError(
                "approval confirmation must exactly match the displayed prompt SHA-256"
            )
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE outbound_context_manifests
                SET status = ?, decided_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                ("approved" if approve else "rejected", utc_now(), manifest_id),
            )

    def manifest(self, manifest_id: str, *, include_prompt: bool = False) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM outbound_context_manifests WHERE id = ?",
                (manifest_id,),
            ).fetchone()
        if row is None:
            raise OutboundContextError(
                f"outbound context manifest {manifest_id!r} not found"
            )
        result = dict(row)
        result["manifest"] = json.loads(result.pop("manifest_json"))
        prompt = result.pop("prompt_text")
        if include_prompt:
            result["prompt"] = prompt
        return result

    def manifests(self, *, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM outbound_context_manifests"
        params: tuple[Any, ...] = ()
        if status:
            if status not in OUTBOUND_CONTEXT_STATUSES:
                raise ValueError(f"unsupported outbound context status {status!r}")
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY requested_at DESC, id DESC"
        with self.store.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["manifest"] = json.loads(item.pop("manifest_json"))
            item.pop("prompt_text")
            result.append(item)
        return result

    def _latest_pending(self, endpoint_id: str, prompt: str) -> dict[str, Any]:
        digest = sha256(prompt.encode("utf-8")).hexdigest()
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM outbound_context_manifests
                WHERE endpoint_id = ? AND prompt_sha256 = ? AND status = 'pending'
                ORDER BY requested_at DESC, id DESC LIMIT 1
                """,
                (endpoint_id, digest),
            ).fetchone()
        if row is not None:
            return self.manifest(str(row["id"]))
        raise OutboundContextError(
            "outbound context was not prepared before invocation"
        )

    def _blocked(
        self,
        *,
        endpoint_id: str,
        agent_id: str,
        request: AgentRequest,
        prompt: str,
        source: str,
        reason: str,
    ) -> dict[str, Any]:
        prompt_bytes = prompt.encode("utf-8")
        manifest_id = str(uuid4())
        manifest = {
            "version": 1,
            "source": source,
            "prompt_sha256": sha256(prompt_bytes).hexdigest(),
            "total_bytes": len(prompt_bytes),
            "items": _prompt_items(request, prompt, []),
            "artifacts": [],
        }
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO outbound_context_manifests(
                    id, endpoint_id, agent_id, run_id, task_id, source,
                    prompt_sha256, total_bytes, manifest_json, prompt_text,
                    status, reason, requested_at, decided_at, consumed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'blocked', ?, ?, NULL, NULL)
                """,
                (
                    manifest_id,
                    endpoint_id,
                    agent_id,
                    request.run_id,
                    request.task_id,
                    source,
                    manifest["prompt_sha256"],
                    manifest["total_bytes"],
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    prompt,
                    reason,
                    utc_now(),
                ),
            )
        raise OutboundContextError(reason)


def _prompt_items(
    request: AgentRequest,
    prompt: str,
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    values = (
        ("system_and_request", prompt),
        ("goal", request.goal),
        ("instruction", request.instruction),
        ("context", request.context),
    )
    items = [
        {
            "kind": kind,
            "bytes": len(value.encode("utf-8")),
            "sha256": sha256(value.encode("utf-8")).hexdigest(),
        }
        for kind, value in values
        if value
    ]
    if artifacts:
        items.append(
            {
                "kind": "artifacts",
                "count": len(artifacts),
                "bytes": sum(int(item["bytes"]) for item in artifacts),
            }
        )
    return items


def _excluded_matches(text: str, patterns: tuple[str, ...]) -> list[str]:
    matched = []
    for pattern in patterns:
        try:
            if re.search(pattern, text):
                matched.append(pattern)
        except re.error as exc:
            raise ValueError(
                f"invalid outbound context excluded pattern {pattern!r}"
            ) from exc
    return matched


def validate_controlled_pilot(
    config,
    manifest: dict[str, Any],
) -> str:
    """Validate the Board 8 one-role synthetic pilot before a resumed run."""
    codex_agents = [
        agent_id
        for agent_id, item in config.agents.items()
        if item.get("type") == "codex_app_server"
    ]
    if len(codex_agents) != 1:
        raise OutboundContextError(
            "controlled pilot requires exactly one Codex App Server agent"
        )
    agent_id = codex_agents[0]
    settings = config.agents[agent_id]
    if manifest["agent_id"] != agent_id:
        raise OutboundContextError(
            "outbound context manifest does not belong to the configured pilot agent"
        )
    if settings.get("sandbox") != "read-only":
        raise OutboundContextError(
            "controlled pilot requires a read-only Codex App Server sandbox"
        )
    policy = settings["outbound_context"]
    if policy.get("source") != "synthetic":
        raise OutboundContextError(
            "Board 8 permits only synthetic context; repository context is excluded"
        )
    if config.agents[config.manager].get("type", "mock") != "mock":
        raise OutboundContextError(
            "controlled pilot requires the manager to remain on mock"
        )
    if (
        not config.reviewer
        or config.agents[config.reviewer].get("type", "mock") != "mock"
    ):
        raise OutboundContextError(
            "controlled pilot requires the reviewer to remain on mock"
        )
    for other_id, item in config.agents.items():
        if other_id != agent_id and item.get("type") in {
            "codex_app_server",
            "a2a",
        } and bool(item.get("invoke_enabled", False)):
            raise OutboundContextError(
                f"controlled pilot forbids another enabled remote agent {other_id!r}"
            )
    if any(
        bool(item.get("invoke_enabled", False))
        for item in config.mcp_servers.values()
    ):
        raise OutboundContextError(
            "controlled pilot forbids enabled MCP tool execution"
        )
    return agent_id
