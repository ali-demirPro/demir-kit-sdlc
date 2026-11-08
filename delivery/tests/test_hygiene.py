"""Tests for safe cleanup."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("hygiene", SCRIPTS / "hygiene.py")
hygiene = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(hygiene)


def aged(path: Path, days: float) -> Path:
    stamp = time.time() - days * 86400
    os.utime(path, (stamp, stamp))
    return path


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.derived = self.root / "DerivedData"
        self.derived.mkdir()
        
    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_old_derived_dirs_are_selected_and_newest_kept(self) -> None:
        old = self.derived / "votum-old"
        (old / "x").mkdir(parents=True)
        aged(old, 30)
        new = self.derived / "votum-new"
        (new / "x").mkdir(parents=True)
        aged(new, 1)
        result = hygiene.plan(self.derived, keep_days=7)
        paths = [item["path"] for item in result["items"]]
        self.assertIn(str(old), paths)
        self.assertNotIn(str(new), paths)

    def test_guard_rejects_paths_outside_the_allowlist(self) -> None:
        result = {"items": [{"kind": "derived", "path": "/tmp/evil", "bytes": 1}], "bytes": 1}
        problems = hygiene.guards(result, free=100 * 1024**3, roots=(self.derived,))
        self.assertTrue(any("allowlist" in problem for problem in problems))

    def test_guard_rejects_low_disk_and_big_runs(self) -> None:
        result = {"items": [], "bytes": 0}
        self.assertTrue(any("disk" in p for p in hygiene.guards(result, free=1, roots=(self.derived,))))
        big = {"items": [], "bytes": 30 * 1024**3}
        self.assertTrue(any("GB" in p for p in hygiene.guards(big, free=100 * 1024**3, roots=(self.derived,))))

    def test_apply_deletes_selected_directories(self) -> None:
        old = self.derived / "votum-old"
        (old / "x").mkdir(parents=True)
        aged(old, 30)
        new = self.derived / "votum-new"
        new.mkdir()
        aged(new, 1)
        result = hygiene.plan(self.derived, keep_days=7)
        hygiene.apply(result)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())
class NoSimulatorLifecycleTests(unittest.TestCase):
    def test_apply_never_shells_out(self) -> None:
        import subprocess
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            derived = root / "DerivedData"
            old = derived / "ornek-old"
            (old / "x").mkdir(parents=True)
            aged(old, 30)
            (derived / "ornek-new").mkdir()
            aged(derived / "ornek-new", 1)
            result = hygiene.plan(derived, keep_days=7)
            with mock.patch.object(subprocess, "run") as run:
                hygiene.apply(result)
            run.assert_not_called()
            self.assertFalse(old.exists())


if __name__ == "__main__":
    unittest.main()
