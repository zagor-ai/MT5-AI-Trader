import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.auto_research_reporter as reporter


class AutoResearchReporterSmokeTest(unittest.TestCase):
    def test_fingerprint_changes_when_result_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ranked_strategies.json"
            path.write_text("[]", encoding="utf-8")
            with patch.object(reporter, "INPUT", path):
                first = reporter._fingerprint()
                path.write_text("[1]", encoding="utf-8")
                second = reporter._fingerprint()
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertNotEqual(first, second)

    def test_publish_once_calls_existing_compact_publisher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "ranked_strategies.json"
            publisher = root / "large_result_publisher.py"
            input_path.write_text("[]", encoding="utf-8")
            publisher.write_text("# publisher", encoding="utf-8")
            with patch.object(reporter, "INPUT", input_path), patch.object(reporter, "PUBLISHER", publisher), patch.object(reporter.subprocess, "run") as run:
                run.return_value.returncode = 0
                self.assertEqual(reporter.publish_once(), 0)
                args = run.call_args.args[0]
                self.assertIn("--once", args)
                self.assertIn("--input", args)


if __name__ == "__main__":
    unittest.main()
