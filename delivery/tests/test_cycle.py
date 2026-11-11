"""Tests for the cycle log (`.kit/cycle.jsonl`)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("DEMIR_KIT_CYCLE_ROOT", tempfile.mkdtemp(prefix="kit-cycle-"))
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from kitlib import root as kitroot  # noqa: E402
import routing  # noqa: E402

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


class ProjectRootWorktreeTests(unittest.TestCase):
    """T-1: a linked worktree resolves the main checkout, not itself."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.main = self.base / "main"
        self.main.mkdir()
        (self.main / "kit.config.yaml").write_text(
            "kit:\n  root: .\n", encoding="utf-8"
        )
        (self.main / "README.md").write_text("kit\n", encoding="utf-8")
        self.git(["init", "-q"])
        self.git(["add", "."])
        self.git(
            [
                "-c",
                "user.name=kit",
                "-c",
                "user.email=kit@example.com",
                "commit",
                "-qm",
                "init",
            ]
        )
        self.worktree = self.base / "epic-364"
        self.git(["worktree", "add", "-q", "-b", "epic-test", str(self.worktree)])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def git(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.main), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_main_and_worktree_resolve_to_the_same_project_root(self) -> None:
        from_main = kitroot.project_root(self.worktree, project=self.main)
        from_worktree = kitroot.project_root(self.worktree, project=self.worktree)
        self.assertEqual(from_main.resolve(), self.main.resolve())
        self.assertEqual(from_worktree.resolve(), self.main.resolve())

    def test_worktree_itself_is_not_the_state_root(self) -> None:
        resolved = kitroot.project_root(
            self.worktree, project=self.worktree
        ).resolve()
        self.assertNotEqual(resolved, self.worktree.resolve())
        self.assertTrue((resolved / "kit.config.yaml").is_file())

    def test_cycle_project_root_uses_the_same_contract(self) -> None:
        with patch.dict(os.environ, {"DEMIR_KIT_CYCLE_ROOT": ""}):
            resolved = cycle.project_root(self.worktree, self.worktree)
        self.assertEqual(resolved.resolve(), self.main.resolve())

    def test_checkout_root_is_the_worktree_not_the_main_checkout(self) -> None:
        self.assertEqual(
            routing.checkout_root(self.worktree).resolve(), self.worktree.resolve()
        )
        self.assertEqual(
            routing.project_root(self.worktree, self.worktree).resolve(),
            self.main.resolve(),
        )


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
