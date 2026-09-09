import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model_council.cli import main


class DoctorCliPrivacyTests(unittest.TestCase):
    def test_doctor_redacts_absolute_executable_and_cwd_paths(self):
        with tempfile.TemporaryDirectory(prefix="model-council-doctor-") as temp:
            root = Path(temp)
            executable = root / "private-agent.exe"
            executable.write_text("", encoding="utf-8")
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "project_name": "doctor-privacy-test",
                        "state_dir": "runtime",
                        "manager": "manager",
                        "agents": {
                            "manager": {
                                "type": "mock",
                                "role": "manager",
                            },
                            "private_cli": {
                                "type": "cli",
                                "role": "architect",
                                "command": [str(executable)],
                                "cwd": str(root),
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with patch.object(sys, "stdout", output):
                main(["doctor", "--config", str(config)])

            rendered = output.getvalue()
            self.assertNotIn(str(root), rendered)
            payload = json.loads(rendered)
            diagnostic = payload["private_cli"]
            self.assertEqual(
                diagnostic["executable"],
                {"configured": True, "name": executable.name},
            )
            self.assertEqual(
                diagnostic["resolved_executable"],
                {"available": True},
            )
            self.assertEqual(
                diagnostic["cwd"],
                {"configured": True, "exists": True},
            )


if __name__ == "__main__":
    unittest.main()
