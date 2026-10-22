"""Verify persistent entry adapters without overwriting existing instructions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class EntryTests(unittest.TestCase):
    def test_adapters_and_preservation(self):
        script = Path(__file__).with_name("init_project.py")
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "project"
            command = [sys.executable, "-B", str(script), "--target", str(target),
                       "--name", "entry-test", "--profile", "research", "--scale", "L",
                       "--ai-entry", "agents", "--ai-entry", "claude"]
            preview = subprocess.run(command + ["--dry-run"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(preview.returncode, 0, preview.stderr + preview.stdout)
            self.assertFalse(target.exists())
            self.assertIn("AGENTS.md", json.loads(preview.stdout)["would_create"])
            created = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(created.returncode, 0, created.stderr + created.stdout)
            for name in ("AGENTS.md", "CLAUDE.md"):
                self.assertIn("AI_CONTRACT.md", (target / name).read_text(encoding="utf-8"))
            contract = (target / "AI_CONTRACT.md").read_text(encoding="utf-8")
            self.assertNotIn("{{SKILL_PATH}}", contract)
            self.assertIn(str(script.resolve().parents[1]), contract)
            (target / "AGENTS.md").write_text("existing project rules", encoding="utf-8")
            again = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
            self.assertEqual((target / "AGENTS.md").read_text(encoding="utf-8"), "existing project rules")


if __name__ == "__main__":
    unittest.main()
