"""Tests for cycle replay and approval-wait closing."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("cycle_replay", SCRIPTS / "cycle.py")
cycle = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cycle)


def labeled(name: str, stamp: str) -> dict:
    return {"event": "labeled", "label": {"name": name}, "created_at": stamp}


class ReplayTests(unittest.TestCase):
    def test_only_missing_label_events_are_replayed(self) -> None:
        events = [
            labeled("agent-approved", "2026-11-08T10:00:00Z"),
            labeled("executing", "2026-11-08T10:05:00Z"),
            labeled("leaf-done", "2026-11-08T10:40:00Z"),
            labeled("wave/1", "2026-11-08T09:00:00Z"),
        ]
        existing = [{"stage": "executing", "ts": "2026-11-08T10:05:00+00:00"}]
        rows = cycle.replay_rows(events, existing)
        self.assertEqual([row["stage"] for row in rows], ["agent-approved", "leaf-done"])
        self.assertEqual(rows[0]["ts"], "2026-11-08T10:00:00Z")
        self.assertEqual(rows[0]["actor"], "replay")

    def test_events_without_timestamp_are_ignored(self) -> None:
        self.assertEqual(cycle.replay_rows([{"label": {"name": "leaf-done"}}], []), [])


class WaitTests(unittest.TestCase):
    def test_close_wait_marks_the_open_wait_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            cycle.record(project, cycle.make_row(240, "wait", actor="human-qa"))
            self.assertTrue(cycle.close_wait(project, 240, ts="2026-11-08T11:00:00+00:00"))
            self.assertFalse(cycle.close_wait(project, 240))
            stages = [row["stage"] for row in cycle.read(project, 240)]
            self.assertEqual(stages, ["wait", "wait-done"])

    def test_close_wait_without_a_wait_is_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(cycle.close_wait(Path(directory), 240))


if __name__ == "__main__":
    unittest.main()
