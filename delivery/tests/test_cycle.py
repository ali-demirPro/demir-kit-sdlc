"""Tests for the cycle log (`.kit/cycle.jsonl`)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("DEMIR_KIT_CYCLE_ROOT", tempfile.mkdtemp(prefix="kit-cycle-"))
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("cycle", SCRIPTS / "cycle.py")
cycle = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cycle)

spec_t = importlib.util.spec_from_file_location("transition", SCRIPTS / "transition.py")
transition = importlib.util.module_from_spec(spec_t)
assert spec_t.loader is not None
spec_t.loader.exec_module(transition)


class CycleLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_make_row_carries_the_stage_fields(self) -> None:
        row = cycle.make_row(216, "executing", actor="developer", reason="claim")
        self.assertEqual(row["issue"], 216)
        self.assertEqual(row["stage"], "executing")
        self.assertEqual(row["actor"], "developer")
        self.assertEqual(row["reason"], "claim")
        self.assertTrue(row["ts"].endswith("+00:00"))

    def test_record_creates_the_directory_and_appends(self) -> None:
        cycle.record(self.root, cycle.make_row(216, "agent-approved"))
        cycle.record(self.root, cycle.make_row(216, "executing"))
        path = self.root / ".kit" / "cycle.jsonl"
        self.assertTrue(path.is_file())
        self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)

    def test_read_filters_by_issue_and_skips_broken_lines(self) -> None:
        cycle.record(self.root, cycle.make_row(1, "executing", ts="2026-11-07T10:00:00+00:00"))
        cycle.record(self.root, cycle.make_row(2, "executing", ts="2026-11-07T10:05:00+00:00"))
        path = self.root / ".kit" / "cycle.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write("{not json}\n\n")
        rows = cycle.read(self.root, 1)
        self.assertEqual([row["stage"] for row in rows], ["executing"])
        self.assertEqual(len(cycle.read(self.root)), 2)

    def test_summary_attributes_time_and_percentages(self) -> None:
        rows = [
            cycle.make_row(216, "agent-approved", ts="2026-11-07T10:00:00+00:00"),
            cycle.make_row(216, "executing", ts="2026-11-07T10:30:00+00:00"),
            cycle.make_row(216, "leaf-done", ts="2026-11-07T11:30:00+00:00"),
        ]
        data = cycle.summary(rows)
        self.assertEqual(data["total_minutes"], 90)
        self.assertEqual([phase["minutes"] for phase in data["phases"]], [30, 60])
        self.assertEqual([phase["percent"] for phase in data["phases"]], [33, 67])
        self.assertEqual([phase["key"] for phase in data["phases"]], ["claim", "exec"])

    def test_review_time_is_a_subset_of_exec(self) -> None:
        rows = [
            cycle.make_row(216, "executing", ts="2026-11-07T10:00:00+00:00"),
            cycle.make_row(216, "review", ts="2026-11-07T10:30:00+00:00"),
            cycle.make_row(216, "leaf-done", ts="2026-11-07T10:50:00+00:00"),
        ]
        data = cycle.summary(rows)
        self.assertEqual([phase["key"] for phase in data["phases"]], ["exec"])
        self.assertEqual(data["phases"][0]["minutes"], 50)
        self.assertEqual(data["review_minutes"], 20)
        self.assertIn("review 20 dk", cycle.section(rows, "#216"))

    def test_review_tail_stops_at_an_approval_wait(self) -> None:
        rows = [
            cycle.make_row(216, "executing", ts="2026-11-07T10:00:00+00:00"),
            cycle.make_row(216, "review", ts="2026-11-07T10:30:00+00:00"),
            cycle.make_row(216, "wait", ts="2026-11-07T10:40:00+00:00"),
            cycle.make_row(216, "wait-done", ts="2026-11-07T11:00:00+00:00"),
            cycle.make_row(216, "leaf-done", ts="2026-11-07T11:30:00+00:00"),
        ]
        data = cycle.summary(rows)
        self.assertEqual(data["phases"][0]["minutes"], 90)
        self.assertEqual(data["review_minutes"], 10)

    def test_review_wait_before_the_last_review_is_not_counted(self) -> None:
        rows = [
            cycle.make_row(216, "executing", ts="2026-11-07T10:00:00+00:00"),
            cycle.make_row(216, "review", ts="2026-11-07T10:30:00+00:00"),
            cycle.make_row(216, "wait", ts="2026-11-07T10:40:00+00:00"),
            cycle.make_row(216, "review", ts="2026-11-07T11:00:00+00:00"),
            cycle.make_row(216, "leaf-done", ts="2026-11-07T11:30:00+00:00"),
        ]
        self.assertEqual(cycle.review_minutes(rows), 30)

    def test_section_is_readable_and_empty_safe(self) -> None:
        self.assertIn("kayıt yok", cycle.section([]))
        rows = [
            cycle.make_row(216, "executing", ts="2026-11-07T10:00:00+00:00"),
            cycle.make_row(216, "leaf-done", ts="2026-11-07T10:45:00+00:00"),
        ]
        text = cycle.section(rows, "#216")
        self.assertIn("#216", text)
        self.assertIn("45 dk", text)
        self.assertIn("%100", text)


class TransitionCycleTests(unittest.TestCase):
    def test_cycle_row_helper_uses_the_transition_actor(self) -> None:
        row = transition.cycle_row(216, "executing", "developer", "claim", epic=215)
        self.assertEqual(row["stage"], "executing")
        self.assertEqual(row["actor"], "developer")
        self.assertEqual(row["epic"], 215)


class ReportCycleTests(unittest.TestCase):
    def test_cycle_text_reaches_the_report(self) -> None:
        spec_r = importlib.util.spec_from_file_location("report", SCRIPTS / "report.py")
        report = importlib.util.module_from_spec(spec_r)
        assert spec_r.loader is not None
        spec_r.loader.exec_module(report)
        issue = {
            "number": 216,
            "title": "t",
            "body": "",
            "labels": ["agent-approved"],
            "created_at": "2026-11-07T10:00:00Z",
            "updated_at": "2026-11-07T11:00:00Z",
            "comments": [],
            "evidence": [],
        }
        usage = {
            "totals": {"sessions": 0, "input": 0, "output": 0, "cache_read": 0,
                       "measured_sessions": 0},
            "unavailable": [],
        }
        text = report.build_report(
            issue, [], usage, [], None, None, None, orca=None,
            cycle_text="**Döngü:** #216 seal→executing 10 dk (%10)",
        )
        self.assertIn("#216 seal→executing 10 dk (%10)", text)

    def test_report_reads_two_issues_from_one_log(self) -> None:
        spec_r = importlib.util.spec_from_file_location("report2", SCRIPTS / "report.py")
        report = importlib.util.module_from_spec(spec_r)
        assert spec_r.loader is not None
        spec_r.loader.exec_module(report)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cycle.record(root, cycle.make_row(1, "executing", ts="2026-11-07T10:00:00+00:00"))
            cycle.record(root, cycle.make_row(1, "leaf-done", ts="2026-11-07T10:20:00+00:00"))
            cycle.record(root, cycle.make_row(2, "executing", ts="2026-11-07T10:00:00+00:00"))
            cycle.record(root, cycle.make_row(2, "leaf-done", ts="2026-11-07T11:40:00+00:00"))
            lines = report.cycle_lines([1, 2], root)
        self.assertEqual(len(lines), 2)
        self.assertIn("20 dk", lines[0])
        self.assertIn("100 dk", lines[1])

    def test_two_leaves_closed_in_the_same_minute_keep_their_own_durations(self) -> None:
        fast = [
            cycle.make_row(1, "executing", ts="2026-11-07T10:00:00+00:00"),
            cycle.make_row(1, "leaf-done", ts="2026-11-07T10:20:00+00:00"),
        ]
        slow = [
            cycle.make_row(2, "executing", ts="2026-11-07T10:00:00+00:00"),
            cycle.make_row(2, "leaf-done", ts="2026-11-07T11:40:00+00:00"),
        ]
        self.assertIn("20 dk", cycle.section(fast, "#1"))
        self.assertIn("100 dk", cycle.section(slow, "#2"))


if __name__ == "__main__":
    unittest.main()
