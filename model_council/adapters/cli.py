from __future__ import annotations

import json
import shutil
import subprocess
import time
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
        self.output_format = str(settings.get("output_format", "text"))
        if self.output_format not in {"text", "codex_jsonl"}:
            raise ValueError(
                f"CLI agent {card.name!r} has unsupported output_format "
                f"{self.output_format!r}"
            )
        cwd_value = settings.get("cwd")
        if cwd_value:
            cwd = Path(str(cwd_value))
            self.cwd = (cwd if cwd.is_absolute() else config_dir / cwd).resolve()
        else:
            self.cwd = config_dir

    def invoke(self, request: AgentRequest) -> AgentResponse:
        prompt = self.render_prompt(request)
        started = time.perf_counter()
        completed = subprocess.run(
            self.command,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=self.cwd,
            timeout=self.timeout_seconds,
            shell=False,
            check=False,
        )
        duration_ms = round((time.perf_counter() - started) * 1000)
        metadata: dict[str, Any] = {
            "adapter": type(self).__name__,
            "command": self.command[0],
            "exit_code": completed.returncode,
            "duration_ms": duration_ms,
            "stderr_tail": completed.stderr[-2000:],
            "output_format": self.output_format,
        }
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise RuntimeError(
                f"CLI agent {self.card.name!r} exited with {completed.returncode}: "
                f"{stderr[-2000:]}"
            )
        if self.output_format == "codex_jsonl":
            content, event_metadata = self._parse_codex_jsonl(completed.stdout)
            metadata.update(event_metadata)
        else:
            content = completed.stdout.strip()
        if not content:
            raise RuntimeError(f"CLI agent {self.card.name!r} returned empty stdout")
        return AgentResponse(content=content, metadata=metadata)

    def diagnose(self) -> dict[str, Any]:
        executable = self.command[0]
        resolved = shutil.which(executable)
        if not resolved and Path(executable).is_file():
            resolved = str(Path(executable).resolve())
        return {
            "ok": resolved is not None and self.cwd.is_dir(),
            "adapter": type(self).__name__,
            "agent": self.card.name,
            "executable": executable,
            "resolved_executable": resolved,
            "cwd": str(self.cwd),
            "cwd_exists": self.cwd.is_dir(),
            "output_format": self.output_format,
            "timeout_seconds": self.timeout_seconds,
        }

    @staticmethod
    def _parse_codex_jsonl(stdout: str) -> tuple[str, dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for line_number, line in enumerate(stdout.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Codex JSONL contained invalid JSON on line {line_number}"
                ) from exc
            if not isinstance(event, dict):
                raise RuntimeError(
                    f"Codex JSONL line {line_number} was not an object"
                )
            events.append(event)

        messages: list[str] = []
        event_types: dict[str, int] = {}
        thread_id: str | None = None
        usage: dict[str, Any] | None = None
        for event in events:
            event_type = str(event.get("type", "unknown"))
            event_types[event_type] = event_types.get(event_type, 0) + 1
            if event_type == "thread.started":
                value = event.get("thread_id")
                if isinstance(value, str):
                    thread_id = value
            elif event_type == "item.completed":
                item = event.get("item")
                if isinstance(item, dict) and item.get("type") == "agent_message":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        messages.append(text.strip())
            elif event_type == "turn.completed":
                value = event.get("usage")
                if isinstance(value, dict):
                    usage = value

        if not messages:
            raise RuntimeError("Codex JSONL contained no completed agent message")
        metadata: dict[str, Any] = {
            "event_count": len(events),
            "event_types": event_types,
        }
        if thread_id:
            metadata["thread_id"] = thread_id
        if usage is not None:
            metadata["usage"] = usage
        return messages[-1], metadata
