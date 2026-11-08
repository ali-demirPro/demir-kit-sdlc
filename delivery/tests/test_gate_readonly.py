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

    def test_untracked_files_count_as_dirty(self) -> None:
        (self.project / "b.txt").write_text("new\n", encoding="utf-8")
        self.assertEqual(gate.tracked_changes(self.project), set())
        self.assertEqual(gate.working_tree_changes(self.project), {"b.txt"})

    def test_skill_documents_read_only_gate(self) -> None:
        text = (ROOT / "skills" / "behavior-gate" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Salt-okur kapı", text)
        self.assertIn("--fix", text)

FIX_ECOSYSTEM = """
name: ornek
products:
  app:
    surfaces:
      ios:
        gates:
          fix: "sh -c 'printf x > fixed.txt'"
"""


class FixStepTests(unittest.TestCase):
    def test_fix_command_is_not_run_without_the_flag(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "ecosystem.yaml").write_text(FIX_ECOSYSTEM, encoding="utf-8")
            with mock.patch.object(gate, "changed_files", return_value=[]), \
                 mock.patch.object(gate, "doctor_command", return_value=["true"]):
                code = gate.main(["--checkpoint", "CP-1", "--project", directory])
            self.assertEqual(code, 0)
            self.assertFalse((project / "fixed.txt").exists())

    def test_fix_command_runs_with_the_flag(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "ecosystem.yaml").write_text(FIX_ECOSYSTEM, encoding="utf-8")
            with mock.patch.object(gate, "changed_files", return_value=[]), \
                 mock.patch.object(gate, "doctor_command", return_value=["true"]):
                code = gate.main(
                    ["--checkpoint", "CP-1", "--project", directory, "--fix"]
                )
            self.assertEqual(code, 0)
            self.assertTrue((project / "fixed.txt").exists())

class GateWiringTests(unittest.TestCase):
    def test_main_fails_when_the_gate_creates_a_new_file(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            git(project, "init", "-q")
            git(project, "config", "user.email", "t@example.com")
            git(project, "config", "user.name", "t")
            (project / "a.txt").write_text("one\n", encoding="utf-8")
            git(project, "add", ".")
            git(project, "commit", "-q", "-m", "init")
            with mock.patch.object(gate, "changed_files", return_value=[]), \
                 mock.patch.object(
                     gate,
                     "doctor_command",
                     return_value=["sh", "-c", "printf x > leaked.txt"],
                 ):
                code = gate.main(["--checkpoint", "CP-1", "--project", directory])
            self.assertEqual(code, 1)
            self.assertTrue((project / "leaked.txt").exists())

    def test_fix_skips_the_cache(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "ecosystem.yaml").write_text(FIX_ECOSYSTEM, encoding="utf-8")
            key = gate.cache_key(project, ["doctor"], "CP-1", None)
            gate.save_cache(project, {key: {"ts": 9_999_999_999, "code": 0}})
            with mock.patch.object(gate, "changed_files", return_value=[]), \
                 mock.patch.object(gate, "doctor_command", return_value=["true"]):
                code = gate.main(
                    ["--checkpoint", "CP-1", "--project", directory, "--cached", "--fix"]
                )
            self.assertEqual(code, 0)
            self.assertTrue((project / "fixed.txt").exists())


if __name__ == "__main__":
    unittest.main()
