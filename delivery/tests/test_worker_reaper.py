"""Tests for the idle worker reaper."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("worker_reaper", SCRIPTS / "worker_reaper.py")
reaper = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(reaper)

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def stamp(minutes_ago: int) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


def worker(dispatch: str, state: str = "running", terminal: str = "active", retained: str = "") -> dict:
    return {
        "dispatchId": dispatch,
        "workerState": state,
        "terminalState": terminal,
        "resource": {"retainedReason": retained} if retained else {},
    }


def dispatch(heartbeat_ago: int | None = 0, status: str = "dispatched") -> dict:
    return {
        "status": status,
        "dispatchedAt": stamp(120),
        "lastHeartbeatAt": stamp(heartbeat_ago) if heartbeat_ago is not None else None,
    }


class PlanTests(unittest.TestCase):
    def test_idle_worker_is_released(self) -> None:
        with mock.patch.object(reaper.usage, "run_workers", return_value=[worker("d1")]), \
             mock.patch.object(reaper.usage, "dispatch_record", return_value={"dispatch": dispatch(30)}):
            rows = reaper.plan_for("run_x", idle_minutes=15, now=NOW)
        self.assertEqual(rows[0]["action"], "release")
        self.assertEqual(rows[0]["idle_minutes"], 30)

    def test_recent_worker_is_kept(self) -> None:
        with mock.patch.object(reaper.usage, "run_workers", return_value=[worker("d1")]), \
             mock.patch.object(reaper.usage, "dispatch_record", return_value={"dispatch": dispatch(3)}):
            rows = reaper.plan_for("run_x", idle_minutes=15, now=NOW)
        self.assertEqual(rows[0]["action"], "keep")

    def test_settled_and_user_takeover_are_kept(self) -> None:
        workers = [worker("d1", state="succeeded", terminal="released"), worker("d2", retained="user_takeover")]
        with mock.patch.object(reaper.usage, "run_workers", return_value=workers), \
             mock.patch.object(reaper.usage, "dispatch_record", return_value={"dispatch": dispatch(90)}):
            rows = reaper.plan_for("run_x", idle_minutes=15, now=NOW)
        self.assertEqual([row["action"] for row in rows], ["keep", "keep"])

    def test_unknown_activity_keeps_the_worker(self) -> None:
        record = {"dispatch": dispatch(None), "path": "/tmp/worktree"}
        record["dispatch"]["dispatchedAt"] = stamp(40)
        with mock.patch.object(reaper.usage, "run_workers", return_value=[worker("d1")]), \
             mock.patch.object(reaper.usage, "dispatch_record", return_value=record), \
             mock.patch.object(reaper.usage, "mapped_session", return_value=None), \
             mock.patch.object(reaper.usage, "sessions_in", return_value=[]):
            rows = reaper.plan_for("run_x", idle_minutes=15, now=NOW)
        self.assertEqual(rows[0]["action"], "keep")
        self.assertIn("zaman", rows[0]["reason"])

    def test_session_update_counts_as_activity(self) -> None:
        record = {"dispatch": dispatch(None), "path": "/tmp/worktree"}
        session = {"id": "ses_x", "updated": int(NOW.timestamp() * 1000) - 5 * 60_000}
        with mock.patch.object(reaper.usage, "run_workers", return_value=[worker("d1")]), \
             mock.patch.object(reaper.usage, "dispatch_record", return_value=record), \
             mock.patch.object(reaper.usage, "mapped_session", return_value={"id": "ses_x"}), \
             mock.patch.object(reaper.usage, "sessions_in", return_value=[session]):
            rows = reaper.plan_for("run_x", idle_minutes=15, now=NOW)
        self.assertEqual(rows[0]["action"], "keep")
        self.assertEqual(rows[0]["idle_minutes"], 5)

    def test_other_sessions_in_the_same_worktree_do_not_count(self) -> None:
        record = {"dispatch": dispatch(None), "path": "/tmp/worktree"}
        coordinator = {
            "id": "ses_coordinator",
            "updated": int(NOW.timestamp() * 1000) - 1 * 60_000,
        }
        with mock.patch.object(reaper.usage, "run_workers", return_value=[worker("d1")]), \
             mock.patch.object(reaper.usage, "dispatch_record", return_value=record), \
             mock.patch.object(reaper.usage, "mapped_session", return_value={"id": "ses_worker"}), \
             mock.patch.object(reaper.usage, "sessions_in", return_value=[coordinator]):
            rows = reaper.plan_for("run_x", idle_minutes=15, now=NOW)
        self.assertEqual(rows[0]["action"], "keep")
        self.assertIn("zaman", rows[0]["reason"])


class RunDiscoveryTests(unittest.TestCase):
    def test_runs_are_read_from_epic_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".orchestration").mkdir()
            (root / ".orchestration" / "epic-213.json").write_text(
                json.dumps({"run_id": "run_a"}), encoding="utf-8"
            )
            (root / ".orchestration" / "epic-215.json").write_text(
                json.dumps({"run_id": "run_a"}), encoding="utf-8"
            )
            self.assertEqual(reaper.runs(root), ["run_a"])


class ApplyTests(unittest.TestCase):
    def test_apply_releases_only_planned_rows(self) -> None:
        rows = [
            {"dispatch_id": "d1", "action": "release"},
            {"dispatch_id": "d2", "action": "keep"},
        ]
        with mock.patch.object(reaper.worker_cleanup, "release", return_value=True) as release:
            result = reaper.apply(rows)
        release.assert_called_once_with("d1")
        self.assertEqual(result[0]["released"], True)


class CliTests(unittest.TestCase):
    def test_dry_run_prints_plan_and_does_not_release(self) -> None:
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".orchestration").mkdir()
            (root / ".orchestration" / "epic-1.json").write_text(
                json.dumps({"run_id": "run_a"}), encoding="utf-8"
            )
            buffer = io.StringIO()
            with mock.patch.object(reaper.usage, "run_workers", return_value=[worker("d1")]), \
                 mock.patch.object(
                     reaper.usage,
                     "dispatch_record",
                     return_value={"dispatch": dispatch(30), "path": ""},
                 ), \
                 mock.patch.object(reaper.worker_cleanup, "release") as release, \
                 mock.patch.object(
                     sys, "argv", ["worker_reaper.py", "--project", str(root), "--dry-run", "--json"]
                 ), \
                 contextlib.redirect_stdout(buffer):
                code = reaper.main()
        self.assertEqual(code, 0)
        release.assert_not_called()
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["rows"][0]["action"], "release")
        self.assertEqual(payload["released"], 0)


if __name__ == "__main__":
    unittest.main()
