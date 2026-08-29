from pathlib import Path
import importlib.util
import sys
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "privacy_scan.py"
)
SPEC = importlib.util.spec_from_file_location("privacy_scan", SCRIPT_PATH)
privacy_scan = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = privacy_scan
SPEC.loader.exec_module(privacy_scan)


class PrivacyScanTests(unittest.TestCase):
    def test_detects_personal_paths_without_echoing_values(self):
        findings = privacy_scan.scan_text(
            "sample.txt",
            "workspace=C:" + "\\Users" + "\\alice\\private-project",
        )
        self.assertEqual(findings[0].kind, "windows_user_path")
        self.assertNotIn("alice", repr(findings[0]))

    def test_detects_high_confidence_secret_formats(self):
        findings = privacy_scan.scan_text(
            "sample.txt",
            "value=sk-" + "A" * 24,
        )
        self.assertEqual(findings[0].kind, "openai_style_secret")

    def test_allows_placeholders_and_github_noreply_email(self):
        findings = privacy_scan.scan_text(
            "sample.txt",
            "C:" + "\\Users\\<username> user@users.noreply.github.com",
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
