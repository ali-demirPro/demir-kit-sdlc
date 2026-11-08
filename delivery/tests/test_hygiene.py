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

BOOTED_OUTPUT = """== Devices ==
-- iOS 18.0 --
    iPhone 15 (11111111-2222-3333-4444-555555555555) (Booted)
"""


class BootedTests(unittest.TestCase):
    def test_booted_returns_uuids(self) -> None:
        import subprocess
        from unittest import mock

        with mock.patch.object(
            hygiene.subprocess, "check_output", return_value=BOOTED_OUTPUT
        ):
            booted = hygiene._booted()
        self.assertEqual(booted, {"11111111-2222-3333-4444-555555555555"})

    def test_booted_simulator_is_not_planned(self) -> None:
        import subprocess
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sims = root / "Devices"
            sims.mkdir()
            device = sims / "11111111-2222-3333-4444-555555555555"
            device.mkdir()
            aged(device, 40)
            with mock.patch.object(
                hygiene, "_booted", return_value={"11111111-2222-3333-4444-555555555555"}
            ):
                result = hygiene.plan(root / "none", sims, sim_days=14)
        self.assertEqual(result["items"], [])


class ApplyTests(unittest.TestCase):
    def test_failed_simctl_delete_is_not_counted(self) -> None:
        from unittest import mock

        items = [{"kind": "simulator", "path": "/tmp/DEVICE-UUID", "bytes": 1}]
        failed = mock.Mock(returncode=1, stdout="", stderr="boom")
        with mock.patch.object(hygiene.subprocess, "run", return_value=failed):
            result = hygiene.apply({"items": items})
        self.assertEqual(result["deleted"], 0)
        self.assertEqual(result["failed"], 1)

    def test_successful_simctl_delete_is_counted(self) -> None:
        from unittest import mock

        items = [{"kind": "simulator", "path": "/tmp/DEVICE-UUID", "bytes": 1}]
        done = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(hygiene.subprocess, "run", return_value=done):
            result = hygiene.apply({"items": items})
        self.assertEqual(result["deleted"], 1)


if __name__ == "__main__":
    unittest.main()
