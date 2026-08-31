from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


RELEASE_CANDIDATE_VERSION = "0.2.0rc1"
REQUIRED_RELEASE_FILES = (
    "AGENTS.md",
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/DEVELOPMENT_BOARDS.md",
    "docs/PRIVACY.md",
    "docs/PRIVACY_ISSUES.md",
    "docs/PROJECT_HANDOFF.md",
    "docs/ROADMAP.md",
    "docs/START_HERE_NEXT_SESSION.md",
    "docs/RELEASE.md",
    "docs/reports/2026-08-29-board-1-settings-registry.md",
    "docs/reports/2026-08-29-board-2-artifact-provenance.md",
    "docs/reports/2026-08-29-board-3-startup-discovery.md",
    "docs/reports/2026-08-29-board-4-usage-cost-ledger.md",
    "docs/reports/2026-08-29-board-5-routing-policy.md",
    "docs/reports/2026-08-30-board-6-local-settings-interface.md",
    "docs/reports/2026-08-30-board-7-persistent-remote-interoperability.md",
    "docs/reports/2026-08-30-board-8-controlled-live-pilot-plan.md",
    "docs/reports/2026-08-30-board-8-controlled-live-pilot.md",
    "docs/reports/2026-08-30-board-9-isolated-git-worktrees-plan.md",
    "docs/reports/2026-08-30-board-9-isolated-git-worktrees.md",
    "docs/reports/2026-08-30-board-10-bounded-repair-recovery-plan.md",
    "docs/reports/2026-08-30-board-10-bounded-repair-recovery.md",
    "docs/reports/2026-08-30-board-11-second-agent-evaluation-plan.md",
    "docs/reports/2026-08-30-board-11-second-agent-evaluation.md",
    "docs/reports/2026-08-31-board-12-product-release-plan.md",
    "docs/reports/2026-08-31-board-12-product-release.md",
)
FORBIDDEN_TRACKED_PARTS = (
    ".env",
    "council.db",
    "__pycache__",
    "runtime/",
    "runtime-",
    "worktrees/",
)


class ReleaseVerifier:
    """Repeatable, local release-candidate gate."""

    def __init__(self, repository: str | Path):
        self.repository = Path(repository).resolve()

    def verify(self) -> dict[str, Any]:
        checks = []
        branch = self._git(["branch", "--show-current"])
        checks.append(_check("branch_main", branch == "main", branch))

        status = self._git(["status", "--porcelain"])
        checks.append(_check("worktree_clean", status == "", status or "clean"))

        refs = {
            name: self._git(["rev-parse", name])
            for name in ("HEAD", "main", "origin/main")
        }
        checks.append(
            _check(
                "local_refs_agree",
                len(set(refs.values())) == 1,
                refs,
            )
        )

        email = self._git(["log", "-1", "--format=%ae"])
        checks.append(
            _check(
                "public_commit_email",
                email.endswith("@users.noreply.github.com"),
                email,
            )
        )

        tracked = self._git(["ls-files"]).splitlines()
        forbidden = [
            item
            for item in tracked
            if _forbidden_tracked(item)
        ]
        checks.append(
            _check(
                "no_runtime_or_credentials_tracked",
                not forbidden,
                forbidden,
            )
        )

        missing = [
            item
            for item in REQUIRED_RELEASE_FILES
            if not (self.repository / item).is_file()
        ]
        checks.append(_check("release_documents_present", not missing, missing))

        version = tomllib.loads(
            (self.repository / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["version"]
        package_version = _package_version(self.repository)
        checks.append(
            _check(
                "release_version",
                version == package_version == RELEASE_CANDIDATE_VERSION,
                {
                    "pyproject": version,
                    "package": package_version,
                    "expected": RELEASE_CANDIDATE_VERSION,
                },
            )
        )

        json_errors = []
        for relative in sorted(
            item for item in tracked if item.lower().endswith(".json")
        ):
            path = self.repository / relative
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                json_errors.append(
                    {"path": relative, "error": type(exc).__name__}
                )
        checks.append(
            _check("tracked_json_parses", not json_errors, json_errors)
        )

        for name, command in (
            (
                "offline_tests",
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            ),
            (
                "python_compile",
                [
                    sys.executable,
                    "-m",
                    "compileall",
                    "-q",
                    "model_council",
                    "tests",
                    "scripts",
                ],
            ),
            (
                "history_privacy_scan",
                [sys.executable, "scripts/privacy_scan.py", "--history"],
            ),
        ):
            result = self._run(command)
            checks.append(
                _check(
                    name,
                    result["exit_code"] == 0,
                    result,
                )
            )

        return {
            "version": RELEASE_CANDIDATE_VERSION,
            "repository": self.repository.name,
            "status": (
                "passed"
                if all(item["passed"] for item in checks)
                else "failed"
            ),
            "checks": checks,
        }

    def _git(self, arguments: list[str]) -> str:
        result = self._run(["git", *arguments])
        if result["exit_code"] != 0:
            raise RuntimeError(
                f"git {' '.join(arguments)} failed: {result['stderr']}"
            )
        return result["stdout"].strip()

    def _run(self, command: list[str]) -> dict[str, Any]:
        completed = subprocess.run(
            command,
            cwd=self.repository,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            shell=False,
            check=False,
        )
        return {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }


def _package_version(repository: Path) -> str:
    namespace: dict[str, Any] = {}
    exec(
        (repository / "model_council" / "__init__.py").read_text(
            encoding="utf-8"
        ),
        namespace,
    )
    return str(namespace["__version__"])


def _forbidden_tracked(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return any(
        normalized == part
        or normalized.endswith(f"/{part}")
        or normalized.startswith(part)
        for part in FORBIDDEN_TRACKED_PARTS
    )


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}
