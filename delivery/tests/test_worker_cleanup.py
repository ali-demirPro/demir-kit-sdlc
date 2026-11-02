"""Tests for the Orca worker terminal cleanup."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "worker_cleanup", SCRIPTS / "worker_cleanup.py"
)
cleanup = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cleanup)


def worker(dispatch, state, terminal, retained=None):
    return {
        "dispatchId": dispatch,
        "runId": "run_x",
        "workerState": state,
        "terminalState": terminal,
        "resource": {"retainedReason": retained},
    }


class WorkerCleanupTests(unittest.TestCase):
    def test_skip_reason(self) -> None:
        self.assertIn("bitmedi", cleanup.skip_reason(worker("a", "running", "running")))
        self.assertEqual(cleanup.skip_reason(worker("b", "succeeded", "released")), "zaten serbest")
        self.assertIn(
            "user_takeover",
            cleanup.skip_reason(worker("c", "succeeded", "retained", "user_takeover")),
        )
        self.assertIsNone(cleanup.skip_reason(worker("d", "succeeded", "reclaimable")))
        self.assertIn(
            "elle incele", cleanup.skip_reason(worker("e", "succeeded", "retained"))
        )
        self.assertIn(
            "bilinmiyor", cleanup.skip_reason(worker("f", "succeeded", ""))
        )

    def test_plan_marks_only_settled_workers(self) -> None:
        rows = [
            worker("ctx_a", "succeeded", "reclaimable"),
            worker("ctx_b", "running", "running"),
            worker("ctx_c", "failed", "retained", "user_takeover"),
            worker("ctx_d", "succeeded", "released"),
        ]
        with patch.object(cleanup, "workers", return_value=rows):
            plan = cleanup.plan_for("run_x")
        actions = {row["dispatch_id"]: row["action"] for row in plan}
        self.assertEqual(actions["ctx_a"], "release")
        self.assertEqual(actions["ctx_b"], "skip")
        self.assertEqual(actions["ctx_c"], "skip")
        self.assertEqual(actions["ctx_d"], "skip")

    def test_apply_releases_and_marks_failure(self) -> None:
        rows = [
            {"dispatch_id": "ctx_a", "action": "release", "reason": None},
            {"dispatch_id": "ctx_b", "action": "release", "reason": None},
            {"dispatch_id": "ctx_c", "action": "skip", "reason": "zaten serbest"},
        ]
        with patch.object(cleanup, "release", side_effect=[True, False]) as release:
            result = cleanup.apply(rows)
        self.assertEqual(release.call_count, 2)
        self.assertTrue(result[0]["released"])
        self.assertEqual(result[1]["action"], "failed")
        self.assertFalse(result[2].get("released", False))

    def test_main_exit_codes(self) -> None:
        with patch.object(cleanup, "plan_for", return_value=[]), patch.object(
            cleanup.sys, "argv", ["worker_cleanup.py", "--run", "run_x"]
        ):
            self.assertEqual(cleanup.main(), 1)

        failed = [{"dispatch_id": "ctx_a", "action": "failed", "reason": None}]
        started = [{"dispatch_id": "ctx_a", "action": "release", "reason": None}]
        with patch.object(cleanup, "plan_for", return_value=started), patch.object(
            cleanup, "apply", return_value=failed
        ), patch.object(
            cleanup.sys, "argv", ["worker_cleanup.py", "--run", "run_x", "--apply"]
        ):
            self.assertEqual(cleanup.main(), 1)

        planned = [{"dispatch_id": "ctx_a", "action": "release", "reason": None}]
        with patch.object(cleanup, "plan_for", return_value=planned), patch.object(
            cleanup.sys, "argv", ["worker_cleanup.py", "--run", "run_x"]
        ):
            self.assertEqual(cleanup.main(), 0)


if __name__ == "__main__":
    unittest.main()
