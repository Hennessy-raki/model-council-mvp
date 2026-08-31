from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from model_council.artifacts import ArtifactStore
from model_council.backup import BackupError, BackupService
from model_council.registry import RegistryService
from model_council.store import CouncilStore


class BackupTests(unittest.TestCase):
    def _services(self, root: Path):
        store = CouncilStore(root / "runtime" / "council.db")
        registry = RegistryService(store)
        registry.set_setting("marker", "before")
        return store, registry, BackupService(store)

    def test_default_backup_excludes_artifacts_worktrees_and_env(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            store, _, backups = self._services(root)
            run_id = store.create_run("synthetic backup test")
            artifact = ArtifactStore(
                store.db_path.parent / "artifacts",
                store,
            ).put_text(run_id, None, "result.txt", "safe synthetic text")
            worktree_file = store.db_path.parent / "worktrees" / "private.txt"
            worktree_file.parent.mkdir(parents=True)
            worktree_file.write_text("private", encoding="utf-8")
            env_file = store.db_path.parent / ".env"
            env_file.write_text("SECRET=not-copied", encoding="utf-8")

            backup = backups.create()
            manifest = backup["manifest"]
            backup_dir = store.db_path.parent / "backups" / backup["id"]

            self.assertFalse(manifest["include_artifacts"])
            self.assertEqual(manifest["artifact_count"], 0)
            self.assertTrue((backup_dir / "council.db").is_file())
            self.assertFalse((backup_dir / "artifacts").exists())
            self.assertFalse((backup_dir / "worktrees").exists())
            self.assertFalse((backup_dir / ".env").exists())
            self.assertTrue(Path(artifact.path).is_file())
            manifest_text = (backup_dir / "manifest.json").read_text(
                encoding="utf-8"
            )
            self.assertNotIn(str(root), manifest_text)
            self.assertNotIn("not-copied", manifest_text)

    def test_artifact_backup_and_exact_restore_create_safety_copy(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            store, registry, backups = self._services(root)
            run_id = store.create_run("synthetic restore test")
            artifact = ArtifactStore(
                store.db_path.parent / "artifacts",
                store,
            ).put_text(run_id, None, "result.txt", "safe synthetic text")
            backup = backups.create(include_artifacts=True)
            self.assertEqual(backup["manifest"]["artifact_count"], 1)

            registry.set_setting("marker", "after")
            Path(artifact.path).unlink()
            approval = backups.request_restore(backup["id"])
            with self.assertRaisesRegex(BackupError, "exactly match"):
                backups.decide(
                    approval["id"],
                    approve=True,
                    confirmation="wrong",
                )
            approved = backups.decide(
                approval["id"],
                approve=True,
                confirmation=approval["scope_sha256"],
            )
            restored = backups.restore(approved["id"])

            self.assertEqual(restored["status"], "consumed")
            self.assertIsNotNone(restored["safety_backup_id"])
            restored_registry = RegistryService(CouncilStore(store.db_path))
            self.assertEqual(restored_registry.setting_value("marker"), "before")
            self.assertEqual(
                Path(artifact.path).read_text(encoding="utf-8"),
                "safe synthetic text",
            )
            backup_ids = {item["id"] for item in backups.backups()}
            self.assertIn(backup["id"], backup_ids)
            self.assertIn(restored["safety_backup_id"], backup_ids)

    def test_restore_becomes_stale_when_local_state_changes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            _, registry, backups = self._services(root)
            backup = backups.create()
            registry.set_setting("marker", "after")
            approval = backups.request_restore(backup["id"])
            approved = backups.decide(
                approval["id"],
                approve=True,
                confirmation=approval["scope_sha256"],
            )
            registry.set_setting("another", {"changed": True})
            with self.assertRaisesRegex(BackupError, "scope changed"):
                backups.restore(approved["id"])
            self.assertEqual(
                backups.approval(approved["id"])["status"],
                "stale",
            )

    def test_manifest_tampering_is_detected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            store, _, backups = self._services(root)
            backup = backups.create()
            database_path = (
                store.db_path.parent
                / "backups"
                / backup["id"]
                / "council.db"
            )
            database_path.write_bytes(b"tampered")
            with self.assertRaisesRegex(BackupError, "byte count changed"):
                backups.backup(backup["id"])


if __name__ == "__main__":
    unittest.main()
