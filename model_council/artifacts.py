from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from .store import CouncilStore
from .types import ArtifactIdentity, ArtifactRef


class ArtifactStore:
    def __init__(self, root: Path, store: CouncilStore):
        self.root = root
        self.store = store
        self.root.mkdir(parents=True, exist_ok=True)

    def put_text(
        self,
        run_id: str,
        task_id: str | None,
        name: str,
        content: str,
        media_type: str = "text/markdown",
        producer: ArtifactIdentity | None = None,
        contributors: Iterable[ArtifactIdentity] = (),
        reviewer: ArtifactIdentity | None = None,
        final_integrator: ArtifactIdentity | None = None,
    ) -> ArtifactRef:
        raw = content.encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        suffix = Path(name).suffix or ".txt"
        target_dir = self.root / digest[:2]
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{digest}{suffix}"
        if not target.exists():
            target.write_bytes(raw)
        artifact_id = self.store.add_artifact(
            run_id=run_id,
            task_id=task_id,
            name=name,
            media_type=media_type,
            sha256=digest,
            path=str(target.resolve()),
            producer=producer,
            attributions=[
                *[("contributor", item) for item in contributors],
                *([("reviewer", reviewer)] if reviewer else []),
                *(
                    [("final_integrator", final_integrator)]
                    if final_integrator
                    else []
                ),
            ],
        )
        return ArtifactRef(
            id=artifact_id,
            name=name,
            media_type=media_type,
            sha256=digest,
            path=str(target.resolve()),
        )

    @staticmethod
    def read_text(ref: ArtifactRef, limit: int = 40_000) -> str:
        text = Path(ref.path).read_text(encoding="utf-8")
        if len(text) <= limit:
            return text
        return text[:limit] + "\n\n[内容已截断]"
