from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .base import AgentAdapter
from ..types import (
    AgentRequest,
    AgentResponse,
    AuthenticationStatus,
    ConnectivityStatus,
    ExecutableStatus,
    PermissionStatus,
)


class CliAdapter(AgentAdapter):
    def __init__(self, card, settings: dict[str, Any], config_dir: Path):
        super().__init__(card)
        self.settings = settings
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
        self.discovery_timeout_seconds = int(
            settings.get("discovery_timeout_seconds", 30)
        )
        self.auth_check_command = self._optional_command(
            settings,
            "auth_check_command",
        )
        self.model_discovery_command = self._optional_command(
            settings,
            "model_discovery_command",
        )

    def invoke(self, request: AgentRequest) -> AgentResponse:
        return self._invoke_in_cwd(request, self.cwd)

    def invoke_in_workspace(
        self,
        request: AgentRequest,
        workspace: str | Path,
    ) -> AgentResponse:
        cwd = Path(workspace).resolve(strict=True)
        if not cwd.is_dir():
            raise ValueError("workspace must be an existing directory")
        return self._invoke_in_cwd(request, cwd)

    def _invoke_in_cwd(
        self,
        request: AgentRequest,
        cwd: Path,
    ) -> AgentResponse:
        prompt = self.render_prompt(request)
        return self._run_prompt(prompt, cwd)

    def _run_prompt(
        self,
        prompt: str,
        cwd: Path,
    ) -> AgentResponse:
        started = time.perf_counter()
        completed = subprocess.run(
            self.command,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=cwd,
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

    def discovery_capabilities(self) -> dict[str, bool]:
        return {
            "executable_check": True,
            "authentication_check": True,
            "permission_check": True,
            "model_discovery": self.model_discovery_command is not None,
            "connectivity_test": True,
        }

    def check_executable(self) -> dict[str, Any]:
        executable = self.command[0]
        resolved = shutil.which(executable)
        if not resolved and Path(executable).is_file():
            resolved = str(Path(executable).resolve())
        return {
            "status": (
                ExecutableStatus.AVAILABLE.value
                if resolved
                else ExecutableStatus.MISSING.value
            ),
            "resolved_executable": resolved,
            "details": {
                "configured_executable": executable,
                "cwd_exists": self.cwd.is_dir(),
            },
        }

    def check_authentication(self) -> dict[str, Any]:
        if self.auth_check_command:
            try:
                with TemporaryDirectory(
                    prefix="model-council-auth-"
                ) as temp:
                    completed = subprocess.run(
                        self.auth_check_command,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        capture_output=True,
                        cwd=temp,
                        timeout=self.discovery_timeout_seconds,
                        shell=False,
                        check=False,
                    )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return {
                    "status": AuthenticationStatus.FAILED.value,
                    "details": {"error": type(exc).__name__},
                }
            return {
                "status": (
                    AuthenticationStatus.VERIFIED.value
                    if completed.returncode == 0
                    else AuthenticationStatus.FAILED.value
                ),
                "details": {
                    "check": "command",
                    "exit_code": completed.returncode,
                },
            }

        auth_env = self.settings.get("auth_env")
        if auth_env:
            names = [auth_env] if isinstance(auth_env, str) else list(auth_env)
            present = all(bool(os.environ.get(str(name))) for name in names)
            return {
                "status": (
                    AuthenticationStatus.CONFIGURED.value
                    if present
                    else AuthenticationStatus.MISSING.value
                ),
                "details": {
                    "check": "environment",
                    "variables": [str(name) for name in names],
                },
            }
        return {
            "status": AuthenticationStatus.UNKNOWN.value,
            "details": {"reason": "no non-interactive auth check configured"},
        }

    def check_permissions(self) -> dict[str, Any]:
        sandbox_mode: str | None = None
        if "--sandbox" in self.command:
            index = self.command.index("--sandbox")
            if index + 1 < len(self.command):
                sandbox_mode = self.command[index + 1]
        status = {
            "read-only": PermissionStatus.READ_ONLY.value,
            "workspace-write": PermissionStatus.WORKSPACE_WRITE.value,
            "danger-full-access": PermissionStatus.UNRESTRICTED.value,
        }.get(sandbox_mode, PermissionStatus.UNKNOWN.value)
        return {
            "status": status,
            "details": {
                "sandbox_mode": sandbox_mode,
                "cwd_exists": self.cwd.is_dir(),
                "cwd_readable": self.cwd.is_dir() and os.access(self.cwd, os.R_OK),
                "cwd_writable": self.cwd.is_dir() and os.access(self.cwd, os.W_OK),
            },
        }

    def discover_models(self) -> list[dict[str, Any]]:
        if not self.model_discovery_command:
            return super().discover_models()
        try:
            with TemporaryDirectory(prefix="model-council-models-") as temp:
                completed = subprocess.run(
                    self.model_discovery_command,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    cwd=temp,
                    timeout=self.discovery_timeout_seconds,
                    shell=False,
                    check=False,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(
                f"model discovery command failed: {type(exc).__name__}"
            ) from exc
        if completed.returncode != 0:
            raise RuntimeError(
                f"model discovery command exited with {completed.returncode}"
            )
        return self._parse_models(completed.stdout)

    def connectivity_probe(self) -> dict[str, Any]:
        if self.check_executable()["status"] != ExecutableStatus.AVAILABLE:
            return {
                "status": ConnectivityStatus.FAILED.value,
                "details": {"reason": "executable_missing"},
            }
        prompt = (
            "Reply with MODEL_COUNCIL_OK. This is a connectivity test. "
            "Do not inspect files, repositories, environment variables, "
            "conversation history, or any external project context."
        )
        try:
            with TemporaryDirectory(
                prefix="model-council-connectivity-"
            ) as temp:
                response = self._run_prompt(prompt, Path(temp))
        except Exception as exc:
            return {
                "status": ConnectivityStatus.FAILED.value,
                "details": {
                    "error": type(exc).__name__,
                    "isolated_workspace": True,
                },
            }
        safe_metadata = {
            key: response.metadata[key]
            for key in (
                "adapter",
                "command",
                "exit_code",
                "duration_ms",
                "output_format",
                "event_count",
                "thread_id",
                "usage",
            )
            if key in response.metadata
        }
        return {
            "status": ConnectivityStatus.PASSED.value,
            "details": {
                "isolated_workspace": True,
                "response_received": bool(response.content.strip()),
                "metadata": safe_metadata,
            },
        }

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
    def _optional_command(
        settings: dict[str, Any],
        key: str,
    ) -> list[str] | None:
        value = settings.get(key)
        if value is None:
            return None
        if not isinstance(value, list) or not value or not all(
            isinstance(item, str) and item for item in value
        ):
            raise ValueError(f"{key} must be a non-empty command array")
        return value

    @staticmethod
    def _parse_models(stdout: str) -> list[dict[str, Any]]:
        text = stdout.strip()
        if not text:
            return []
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            values = [line.strip() for line in text.splitlines() if line.strip()]
        else:
            if isinstance(payload, dict):
                values = payload.get("models", payload.get("data", []))
            else:
                values = payload
            if not isinstance(values, list):
                raise RuntimeError("model discovery output must contain a list")
        result = []
        seen: set[str] = set()
        for item in values:
            model_id = item.get("id") if isinstance(item, dict) else item
            if model_id is None:
                continue
            model_id = str(model_id).strip()
            if model_id and model_id not in seen:
                seen.add(model_id)
                result.append({"id": model_id, "source": "adapter"})
        return result

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
