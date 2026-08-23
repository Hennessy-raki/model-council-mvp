from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from model_council.artifacts import ArtifactStore
from model_council.store import CouncilStore


class ArtifactStoreTests(unittest.TestCase):
    def test_same_content_reuses_physical_file(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            store = CouncilStore(root / "council.db")
            run_id = store.create_run("test")
            artifacts = ArtifactStore(root / "artifacts", store)
            first = artifacts.put_text(run_id, None, "a.md", "same")
            second = artifacts.put_text(run_id, None, "b.md", "same")
            self.assertEqual(first.sha256, second.sha256)
            self.assertEqual(first.path, second.path)
            self.assertTrue(Path(first.path).exists())


if __name__ == "__main__":
    unittest.main()
