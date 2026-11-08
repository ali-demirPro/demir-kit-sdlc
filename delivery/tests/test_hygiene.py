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
        self.sims = self.root / "Devices"
        self.derived.mkdir()
        self.sims.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_old_derived_dirs_are_selected_and_newest_kept(self) -> None:
        old = self.derived / "votum-old"
        (old / "x").mkdir(parents=True)
        aged(old, 30)
        new = self.derived / "votum-new"
        (new / "x").mkdir(parents=True)
        aged(new, 1)
        result = hygiene.plan(self.derived, self.sims, keep_days=7, booted=set())
        paths = [item["path"] for item in result["items"]]
        self.assertIn(str(old), paths)
        self.assertNotIn(str(new), paths)

    def test_booted_and_recent_simulators_are_kept(self) -> None:
        old = self.sims / "OLD-DEVICE"
        old.mkdir()
        aged(old, 30)
        (self.sims / "BOOTED").mkdir()
        aged(self.sims / "BOOTED", 30)
        result = hygiene.plan(self.derived, self.sims, sim_days=14, booted={"BOOTED"})
        paths = [item["path"] for item in result["items"]]
        self.assertIn(str(old), paths)
        self.assertNotIn(str(self.sims / "BOOTED"), paths)

    def test_guard_rejects_paths_outside_the_allowlist(self) -> None:
        result = {"items": [{"kind": "derived", "path": "/tmp/evil", "bytes": 1}], "bytes": 1, "booted": []}
        problems = hygiene.guards(result, free=100 * 1024**3, roots=(self.derived, self.sims))
        self.assertTrue(any("allowlist" in problem for problem in problems))

    def test_guard_rejects_low_disk_and_big_runs(self) -> None:
        result = {"items": [], "bytes": 0, "booted": []}
        self.assertTrue(any("disk" in p for p in hygiene.guards(result, free=1, roots=(self.derived,))))
        big = {"items": [], "bytes": 30 * 1024**3, "booted": []}
        self.assertTrue(any("GB" in p for p in hygiene.guards(big, free=100 * 1024**3, roots=(self.derived,))))

    def test_apply_deletes_selected_directories(self) -> None:
        old = self.derived / "votum-old"
        (old / "x").mkdir(parents=True)
        aged(old, 30)
        new = self.derived / "votum-new"
        new.mkdir()
        aged(new, 1)
        result = hygiene.plan(self.derived, self.sims, keep_days=7, booted=set())
        hygiene.apply(result)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())


if __name__ == "__main__":
    unittest.main()
