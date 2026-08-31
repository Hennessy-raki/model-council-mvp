from __future__ import annotations

from pathlib import Path
import unittest

from model_council import __version__
from model_council.release import (
    RELEASE_CANDIDATE_VERSION,
    REQUIRED_RELEASE_FILES,
    _forbidden_tracked,
)


class ReleaseTests(unittest.TestCase):
    def test_release_candidate_versions_are_consistent(self):
        root = Path(__file__).resolve().parent.parent
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        self.assertEqual(__version__, RELEASE_CANDIDATE_VERSION)
        self.assertIn(
            f'version = "{RELEASE_CANDIDATE_VERSION}"',
            pyproject,
        )

    def test_required_release_documents_exist(self):
        root = Path(__file__).resolve().parent.parent
        missing = [
            item for item in REQUIRED_RELEASE_FILES
            if not (root / item).is_file()
        ]
        self.assertEqual(missing, [])
        self.assertIn(
            "docs/reports/2026-08-29-board-1-settings-registry.md",
            REQUIRED_RELEASE_FILES,
        )
        self.assertIn(
            "docs/reports/2026-08-30-board-11-second-agent-evaluation.md",
            REQUIRED_RELEASE_FILES,
        )

    def test_runtime_and_credential_paths_are_forbidden(self):
        for path in (
            "runtime/council.db",
            "runtime-board8-pilot/evidence.json",
            ".env",
            "private/.env",
            "runtime/worktrees/file.py",
        ):
            self.assertTrue(_forbidden_tracked(path), path)
        self.assertFalse(_forbidden_tracked("config.example.json"))


if __name__ == "__main__":
    unittest.main()
