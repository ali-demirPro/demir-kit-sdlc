"""Tests for the Orca wave runner."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("orca_wave", SCRIPTS / "orca_wave.py")
orca_wave = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(orca_wave)


class WaveTests(unittest.TestCase):
    def test_ready_tasks_skips_dependencies(self) -> None:
        plan = {
            "tasks": [
                {"id": "CP-1", "spec": "a", "deps": []},
                {"id": "CP-2", "spec": "b", "deps": ["task:CP-1"]},
                {"id": "CP-3", "spec": "c"},
            ]
        }
        ready = [task["id"] for task in orca_wave.ready_tasks(plan)]
        self.assertEqual(ready, ["CP-1", "CP-3"])

    def test_done_dispatches_matches_dispatch_ids(self) -> None:
        messages = [
            {
                "type": "worker_done",
                "subject": "A",
                "payload": {"dispatchId": "ctx_a", "outcome": "succeeded"},
            },
            {
                "type": "worker_done",
                "subject": "B",
                "payload": '{"dispatchId": "ctx_b", "outcome": "succeeded"}',
            },
            {"type": "question", "payload": {"dispatchId": "ctx_c"}},
        ]
        done = orca_wave.done_dispatches(messages, {"ctx_a", "ctx_b"})
        self.assertEqual(set(done), {"ctx_a", "ctx_b"})
        self.assertEqual(done["ctx_a"]["subject"], "A")

    def test_done_dispatches_ignores_unknown(self) -> None:
        messages = [
            {"type": "worker_done", "payload": {"dispatchId": "ctx_other"}},
        ]
        self.assertEqual(orca_wave.done_dispatches(messages, {"ctx_a"}), {})

    def test_start_command(self) -> None:
        command = orca_wave.start_command(
            {"spec": "do work"}, agent="opencode2", worktree="current"
        )
        self.assertEqual(command[:4], ["orca", "orchestration", "worker-start", "--spec"])
        self.assertIn("opencode2", command)
        self.assertIn("current", command)

    def test_dry_run_json_has_commands(self) -> None:
        plan = {
            "tasks": [
                {"id": "CP-1", "spec": "A", "deps": []},
                {"id": "CP-2", "spec": "B", "deps": []},
            ]
        }
        args = argparse.Namespace(
            dry_run=True,
            json=True,
            objective="wave",
            agent="opencode2",
            worktree="current",
            timeout_ms=1000,
        )
        summary = orca_wave.execute_wave(plan, args)
        self.assertTrue(summary["dry_run"])
        self.assertEqual(len(summary["commands"]), 3)
        self.assertEqual(len(summary["tasks"]), 2)

    def _args(self) -> argparse.Namespace:
        return argparse.Namespace(
            dry_run=False,
            json=True,
            objective="wave",
            agent="opencode2",
            worktree="current",
            timeout_ms=1000,
        )

    def test_attention_blocks_ack_and_release(self) -> None:
        calls: list[list[str]] = []
        state = {"started": 0}

        def fake(args):
            calls.append(args)
            if args[0] == "orchestration" and args[1] == "run-create":
                return json.dumps({"result": {"run": {"id": "run_x"}}})
            if args[0] == "orchestration" and args[1] == "worker-start":
                state["started"] += 1
                idx = state["started"]
                return json.dumps(
                    {
                        "ok": True,
                        "result": {
                            "taskId": f"task_{idx}",
                            "dispatchId": f"ctx_{idx}",
                            "effects": [],
                        },
                    }
                )
            if args[0] == "orchestration" and args[1] == "check" and "--ack" not in args:
                return json.dumps(
                    {
                        "result": {
                            "deliveryId": "delivery_x",
                            "messages": [
                                {"type": "question", "subject": "Need input"}
                            ],
                        }
                    }
                )
            return json.dumps({"ok": True, "result": {}})

        original = orca_wave.orca
        orca_wave.orca = fake
        try:
            plan = {
                "tasks": [
                    {"id": "CP-1", "spec": "A", "deps": []},
                    {"id": "CP-2", "spec": "B", "deps": []},
                ]
            }
            summary = orca_wave.execute_wave(plan, self._args())
        finally:
            orca_wave.orca = original

        self.assertEqual(len(summary["attention"]), 1)
        self.assertEqual(len(summary["missing"]), 2)
        self.assertNotIn("--ack", [item for call in calls for item in call])
        self.assertNotIn("worker-release", [item for call in calls for item in call])

    def test_ack_and_release_after_full_batch(self) -> None:
        calls: list[list[str]] = []
        state = {"started": 0}

        def fake(args):
            calls.append(args)
            if args[0] == "orchestration" and args[1] == "run-create":
                return json.dumps({"result": {"run": {"id": "run_x"}}})
            if args[0] == "orchestration" and args[1] == "worker-start":
                state["started"] += 1
                idx = state["started"]
                return json.dumps(
                    {
                        "ok": True,
                        "result": {
                            "taskId": f"task_{idx}",
                            "dispatchId": f"ctx_{idx}",
                            "effects": [],
                        },
                    }
                )
            if args[0] == "orchestration" and args[1] == "check" and "--ack" not in args:
                return json.dumps(
                    {
                        "result": {
                            "deliveryId": "delivery_x",
                            "messages": [
                                {"type": "worker_done", "payload": {"dispatchId": "ctx_1"}},
                                {"type": "worker_done", "payload": {"dispatchId": "ctx_2"}},
                            ],
                        }
                    }
                )
            return json.dumps({"ok": True, "result": {}})

        original = orca_wave.orca
        orca_wave.orca = fake
        try:
            plan = {
                "tasks": [
                    {"id": "CP-1", "spec": "A", "deps": []},
                    {"id": "CP-2", "spec": "B", "deps": []},
                ]
            }
            summary = orca_wave.execute_wave(plan, self._args())
        finally:
            orca_wave.orca = original

        self.assertEqual(summary["missing"], [])
        self.assertEqual(len(summary["done"]), 2)
        self.assertTrue(any("--ack" in call for call in calls))
        self.assertEqual(
            sum(1 for call in calls if "worker-release" in call), 2
        )


if __name__ == "__main__":
    unittest.main()
