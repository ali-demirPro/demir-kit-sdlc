"""Tests for the read-only gate guard."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("gate_ro", SCRIPTS / "gate.py")
gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gate)


def git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(project), check=True, capture_output=True)


class TrackedChangesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        git(self.project, "init", "-q")
        git(self.project, "config", "user.email", "t@example.com")
        git(self.project, "config", "user.name", "t")
        (self.project / "a.txt").write_text("one\n", encoding="utf-8")
        git(self.project, "add", ".")
        git(self.project, "commit", "-q", "-m", "init")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_clean_tree_has_no_changes(self) -> None:
        self.assertEqual(gate.tracked_changes(self.project), set())

    def test_modified_file_is_reported(self) -> None:
        (self.project / "a.txt").write_text("two\n", encoding="utf-8")
        self.assertEqual(gate.tracked_changes(self.project), {"a.txt"})

    def test_untracked_files_are_ignored(self) -> None:
        (self.project / "b.txt").write_text("new\n", encoding="utf-8")
        self.assertEqual(gate.tracked_changes(self.project), set())

    def test_skill_documents_read_only_gate(self) -> None:
        text = (ROOT / "skills" / "behavior-gate" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Salt-okur kapı", text)
        self.assertIn("--fix", text)


if __name__ == "__main__":
    unittest.main()
