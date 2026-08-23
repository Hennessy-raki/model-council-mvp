from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .base import AgentAdapter
from ..types import AgentRequest, AgentResponse


class CliAdapter(AgentAdapter):
    def __init__(self, card, settings: dict[str, Any], config_dir: Path):
        super().__init__(card)
        command = settings.get("command")
        if not isinstance(command, list) or not command or not all(
            isinstance(item, str) and item for item in command
        ):
            raise ValueError(f"CLI agent {card.name!r} requires a non-empty command array")
        self.command = command
        self.timeout_seconds = int(settings.get("timeout_seconds", 600))
        cwd_value = settings.get("cwd")
        if cwd_value:
            cwd = Path(str(cwd_value))
            self.cwd = (cwd if cwd.is_absolute() else config_dir / cwd).resolve()
        else:
            self.cwd = config_dir

    def invoke(self, request: AgentRequest) -> AgentResponse:
        prompt = self.render_prompt(request)
        completed = subprocess.run(
            self.command,
            input=prompt,
            text=True,
            capture_output=True,
            cwd=self.cwd,
            timeout=self.timeout_seconds,
            shell=False,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise RuntimeError(
                f"CLI agent {self.card.name!r} exited with {completed.returncode}: "
                f"{stderr[-2000:]}"
            )
        content = completed.stdout.strip()
        if not content:
            raise RuntimeError(f"CLI agent {self.card.name!r} returned empty stdout")
        return AgentResponse(
            content=content,
            metadata={"stderr_tail": completed.stderr[-2000:]},
        )
