"""Tests for the fail-closed process gate."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "process_gate", SCRIPTS / "process_gate.py"
)
process_gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(process_gate)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def repo() -> Path:
    directory = Path(tempfile.mkdtemp())
    git(directory, "init", "-q")
    git(directory, "checkout", "-q", "-b", "main")
    (directory / "ecosystem.yaml").write_text(
        "products:\n  app:\n    surfaces:\n      app: {path: App}\n",
        encoding="utf-8",
    )
    return directory


class ProcessGateTests(unittest.TestCase):
    def test_dirty_sources_matches_app_paths(self) -> None:
        root = repo()
        (root / "App").mkdir()
        (root / "App" / "x.swift").write_text("x", encoding="utf-8")
        (root / "docs").mkdir()
        (root / "docs" / "note.md").write_text("x", encoding="utf-8")
        self.assertEqual(process_gate.dirty_sources(root), ["App/x.swift"])

    def test_clean_tree_has_no_dirty_sources(self) -> None:
        self.assertEqual(process_gate.dirty_sources(repo()), [])

    def test_install_hooks_is_idempotent(self) -> None:
        root = repo()
        first = process_gate.install_hooks(root, "")
        self.assertEqual(len(first["written"]), 2)
        pre_commit = process_gate.hooks_dir(root) / "pre-commit"
        self.assertTrue(pre_commit.is_file())
        self.assertTrue(os.access(pre_commit, os.X_OK))
        self.assertIn("# demir-kit:hook", pre_commit.read_text())
        second = process_gate.install_hooks(root, "")
        self.assertEqual(second["written"], [])
        self.assertEqual(process_gate.missing_hooks(root), [])

    def test_doctor_dirty_main_errors_epic_branch_warns(self) -> None:
        import doctor

        root = repo()
        (root / "App").mkdir()
        (root / "App" / "x.swift").write_text("x", encoding="utf-8")
        doctor.ERRORS.clear()
        doctor.WARNS.clear()
        doctor.check_unsealed_work(root)
        self.assertTrue(any("kirli" in item for item in doctor.ERRORS))

        git(root, "checkout", "-q", "-b", "epic-1")
        doctor.ERRORS.clear()
        doctor.WARNS.clear()
        doctor.check_unsealed_work(root)
        self.assertEqual(doctor.ERRORS, [])
        self.assertFalse(any("kirli" in item for item in doctor.WARNS))

    def test_git_error_is_fail_closed(self) -> None:
        with patch.object(process_gate, "_run", return_value=None):
            with self.assertRaises(RuntimeError):
                process_gate.dirty_sources(Path("/tmp"))
            errors, _ = process_gate.unsealed_report(Path("/tmp"))
        self.assertTrue(any("okunamadı" in item for item in errors))

    def test_init_apply_installs_hooks(self) -> None:
        import init

        root = repo()
        plan = {"project": str(root), "files": {}, "agents_prefix": ""}
        with patch.object(
            init.delivery_block,
            "inject",
            return_value={"changed": False, "applied": False},
        ):
            result = init.apply_plan(plan)
        self.assertTrue(
            any("pre-commit" in path for path in result["hooks"]["written"])
        )

    def test_foreign_hook_is_not_overwritten(self) -> None:
        root = repo()
        hooks = process_gate.hooks_dir(root)
        hooks.mkdir(parents=True, exist_ok=True)
        foreign = hooks / "pre-commit"
        foreign.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        result = process_gate.install_hooks(root, "")
        self.assertIn(str(foreign), result["skipped"])
        self.assertIn("exit 0", foreign.read_text())
        self.assertIn("pre-commit", process_gate.missing_hooks(root))


if __name__ == "__main__":
    unittest.main()
