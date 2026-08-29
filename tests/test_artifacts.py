from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from model_council.artifacts import ArtifactStore
from model_council.store import CouncilStore
from model_council.types import ArtifactIdentity


class ArtifactStoreTests(unittest.TestCase):
    def test_same_content_reuses_physical_file(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            store = CouncilStore(root / "council.db")
            run_id = store.create_run("test")
            artifacts = ArtifactStore(root / "artifacts", store)
            producer = ArtifactIdentity(
                agent_id="writer",
                provider_id="provider-a",
                model_id="model-a",
            )
            first = artifacts.put_text(
                run_id,
                None,
                "a.md",
                "same",
                producer=producer,
                contributors=[producer, producer],
            )
            second = artifacts.put_text(run_id, None, "b.md", "same")
            self.assertEqual(first.sha256, second.sha256)
            self.assertEqual(first.path, second.path)
            self.assertTrue(Path(first.path).exists())
            provenance = store.provenance_for_artifact(first.id)
            self.assertEqual(provenance["producer"]["agent_id"], "writer")
            self.assertEqual(provenance["producer"]["provider_id"], "provider-a")
            self.assertEqual(provenance["producer"]["model_id"], "model-a")
            self.assertEqual(len(provenance["contributors"]), 1)

    def test_existing_database_migrates_without_losing_artifacts(self):
        with TemporaryDirectory() as temp:
            db_path = Path(temp) / "legacy.db"
            with sqlite3.connect(db_path) as conn:
                conn.executescript(
                    """
                    CREATE TABLE runs (
                        id TEXT PRIMARY KEY,
                        goal TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        completed_at TEXT,
                        final_artifact_id TEXT,
                        error TEXT
                    );
                    CREATE TABLE artifacts (
                        id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        task_id TEXT,
                        name TEXT NOT NULL,
                        media_type TEXT NOT NULL,
                        sha256 TEXT NOT NULL,
                        path TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    INSERT INTO runs(id, goal, status, created_at)
                    VALUES ('legacy-run', 'legacy goal', 'completed', 'now');
                    INSERT INTO artifacts(
                        id, run_id, task_id, name, media_type, sha256, path, created_at
                    ) VALUES (
                        'legacy-artifact', 'legacy-run', NULL, 'old.md',
                        'text/markdown', 'abc', 'C:/legacy/old.md', 'now'
                    );
                    """
                )
            conn.close()

            store = CouncilStore(db_path)
            with store.connect() as conn:
                columns = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(artifacts)")
                }
                attribution_table = conn.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name = 'artifact_attributions'
                    """
                ).fetchone()
                discovery_table = conn.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name = 'agent_discovery'
                    """
                ).fetchone()
                ledger_tables = {
                    row["name"]
                    for row in conn.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table' AND name IN (
                            'usage_events',
                            'budget_policies',
                            'budget_alerts',
                            'provider_balance_snapshots'
                        )
                        """
                    ).fetchall()
                }
                routing_table = conn.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name = 'routing_decisions'
                    """
                ).fetchone()
            self.assertTrue(
                {
                    "producer_agent_id",
                    "producer_provider_id",
                    "producer_model_id",
                }
                <= columns
            )
            self.assertIsNotNone(attribution_table)
            self.assertIsNotNone(discovery_table)
            self.assertEqual(
                ledger_tables,
                {
                    "usage_events",
                    "budget_policies",
                    "budget_alerts",
                    "provider_balance_snapshots",
                },
            )
            self.assertIsNotNone(routing_table)
            migrated = store.artifacts_for_run("legacy-run")
            self.assertEqual(migrated[0]["id"], "legacy-artifact")
            self.assertIsNone(migrated[0]["provenance"]["producer"])


if __name__ == "__main__":
    unittest.main()
