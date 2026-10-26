"""Tests for the Orca wave runner."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import sys
import types
import unittest
from unittest.mock import patch
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

    def test_summary_text_all_done(self) -> None:
        summary = {
            "tasks": [{"id": "A"}, {"id": "B"}],
            "done": ["ctx_a", "ctx_b"],
            "missing": [],
            "attention": [],
            "duration_seconds": 12,
        }
        text = orca_wave.summary_text(summary)
        self.assertIn("2 worker", text)
        self.assertIn("12s", text)
        self.assertNotIn("ctx_", text)

    def test_summary_text_failed(self) -> None:
        summary = {
            "tasks": [{"id": "A"}],
            "done": ["ctx_a"],
            "missing": [],
            "attention": [],
            "failed": ["ctx_a"],
            "duration_seconds": 1,
        }
        text = orca_wave.summary_text(summary)
        self.assertIn("başarısız", text)
        self.assertNotIn("hepsi tamamlandı", text)
        command = orca_wave.notify_command(25, summary)
        self.assertIn("--approval", command)

    def test_summary_text_missing(self) -> None:
        summary = {
            "tasks": [{"id": "A"}, {"id": "B"}],
            "done": ["ctx_a"],
            "missing": ["ctx_b"],
            "attention": [],
            "duration_seconds": 5,
        }
        text = orca_wave.summary_text(summary)
        self.assertIn("1 eksik", text)
        command = orca_wave.notify_command(25, summary)
        self.assertIn("update.py", " ".join(command))
        self.assertIn("--approval", command)
        self.assertNotIn("ctx_b", " ".join(command))

    def test_notify_command_no_ids(self) -> None:
        summary = {
            "tasks": [{"id": "A"}],
            "done": ["ctx_a"],
            "missing": [],
            "attention": [],
            "duration_seconds": 3,
        }
        command = orca_wave.notify_command(25, summary)
        joined = " ".join(command)
        self.assertIn("--issue", command)
        self.assertIn("25", command)
        self.assertIn("--kind", command)
        self.assertIn("summary", command)
        self.assertNotIn("ctx_a", joined)


class NotifyTests(unittest.TestCase):
    SUMMARY = {
        "dry_run": False,
        "run_id": "run_x",
        "tasks": [{"id": "A"}],
        "done": ["ctx_a"],
        "missing": [],
        "attention": [],
        "commands": [],
        "duration_seconds": 3,
    }

    def run_main(self, argv, summary=None):
        original_load = orca_wave.load_plan
        original_execute = orca_wave.execute_wave
        original_run = orca_wave.subprocess.run
        original_argv = sys.argv
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        orca_wave.load_plan = lambda args: {"tasks": [{"id": "A"}]}
        orca_wave.execute_wave = lambda plan, args: summary or self.SUMMARY
        orca_wave.subprocess.run = fake_run
        sys.argv = ["orca_wave.py", *argv]
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(
                io.StringIO()
            ):
                code = orca_wave.main()
        finally:
            orca_wave.load_plan = original_load
            orca_wave.execute_wave = original_execute
            orca_wave.subprocess.run = original_run
            sys.argv = original_argv
        return code, calls, out.getvalue()

    def test_notify_off_by_default(self) -> None:
        code, calls, _ = self.run_main(["--issue", "25", "--execute", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])

    def test_notify_posts_one_summary(self) -> None:
        code, calls, _ = self.run_main(["--issue", "25", "--execute", "--notify", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        command = calls[0]
        self.assertIn("update.py", " ".join(command))
        self.assertIn("--kind", command)
        self.assertIn("summary", command)

    def test_notify_requires_issue(self) -> None:
        with self.assertRaises(SystemExit):
            self.run_main(["--notify", "--execute", "--json"])

    def test_notify_dry_run_does_not_post(self) -> None:
        code, calls, _ = self.run_main(
            ["--issue", "25", "--notify", "--dry-run", "--json"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])

    def test_notify_uses_project_cwd(self) -> None:
        calls = []
        original = (orca_wave.load_plan, orca_wave.execute_wave, orca_wave.subprocess.run)
        original_argv = sys.argv

        def fake_run(command, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        orca_wave.load_plan = lambda args: {"tasks": [{"id": "A"}]}
        orca_wave.execute_wave = lambda plan, args: self.SUMMARY
        orca_wave.subprocess.run = fake_run
        sys.argv = ["orca_wave.py", "--issue", "25", "--execute", "--notify", "--json"]
        try:
            with patch.object(orca_wave, "PROJECT", Path("/tmp/product")):
                with contextlib.redirect_stdout(io.StringIO()):
                    orca_wave.main()
        finally:
            orca_wave.load_plan, orca_wave.execute_wave, orca_wave.subprocess.run = original
            sys.argv = original_argv
        self.assertEqual(calls[0]["cwd"], Path("/tmp/product"))

    def test_notify_json_stdout_is_clean(self) -> None:
        _, _, output = self.run_main(["--issue", "25", "--execute", "--notify", "--json"])
        json.loads(output)
        self.assertNotIn("[notify", output)

    def test_load_plan_uses_project_cwd(self) -> None:
        captured = {}

        def fake(args, **kwargs):
            captured.update(kwargs)
            return json.dumps({"tasks": []})

        with patch.object(orca_wave, "PROJECT", Path("/tmp/product")), patch.object(
            orca_wave.subprocess, "check_output", fake
        ):
            orca_wave.load_plan(argparse.Namespace(from_json=None, issue=33))
        self.assertEqual(captured["cwd"], Path("/tmp/product"))

    def test_topological_waves(self) -> None:
        tasks = [
            {"id": "A", "deps": []},
            {"id": "B", "deps": ["task:A"]},
            {"id": "C", "deps": ["task:A"]},
            {"id": "D", "deps": ["task:B", "task:C"]},
        ]
        self.assertEqual(
            orca_wave.topological_waves(tasks), [["A"], ["B", "C"], ["D"]]
        )

    def test_topological_waves_cycle(self) -> None:
        with self.assertRaises(ValueError):
            orca_wave.topological_waves(
                [{"id": "A", "deps": ["task:B"]}, {"id": "B", "deps": ["task:A"]}]
            )

    def test_topological_waves_unknown(self) -> None:
        with self.assertRaises(ValueError):
            orca_wave.topological_waves([{"id": "A", "deps": ["task:Z"]}])

    def test_dag_dry_run(self) -> None:
        plan = {
            "tasks": [
                {"id": "A", "spec": "A", "deps": []},
                {"id": "B", "spec": "B", "deps": ["task:A"]},
                {"id": "C", "spec": "C", "deps": ["task:A"]},
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
        summary = orca_wave.execute_dag(plan, args)
        self.assertEqual([wave["tasks"] for wave in summary["waves"]], [["A"], ["B", "C"]])
        self.assertEqual(len(summary["commands"]), 4)

    def test_dag_executes_waves(self) -> None:
        calls = []
        started = []

        def fake(args):
            calls.append(args)
            if args[0] == "orchestration" and args[1] == "run-create":
                return json.dumps({"result": {"run": {"id": "run_x"}}})
            if args[0] == "orchestration" and args[1] == "worker-start":
                task_id = args[args.index("--spec") + 1]
                started.append(task_id)
                return json.dumps(
                    {
                        "ok": True,
                        "result": {
                            "taskId": f"task_{task_id}",
                            "dispatchId": f"ctx_{task_id}",
                            "effects": [],
                        },
                    }
                )
            if args[0] == "orchestration" and args[1] == "check" and "--ack" not in args:
                messages = [
                    {"type": "worker_done", "payload": {"dispatchId": f"ctx_{task_id}"}}
                    for task_id in started
                ]
                return json.dumps(
                    {"result": {"deliveryId": "delivery_x", "messages": messages}}
                )
            return json.dumps({"ok": True, "result": {}})

        original = orca_wave.orca
        orca_wave.orca = fake
        try:
            plan = {
                "tasks": [
                    {"id": "A", "spec": "A", "deps": []},
                    {"id": "B", "spec": "B", "deps": ["task:A"]},
                    {"id": "C", "spec": "C", "deps": ["task:A"]},
                    {"id": "D", "spec": "D", "deps": ["task:B", "task:C"]},
                ]
            }
            args = argparse.Namespace(
                dry_run=False,
                json=True,
                objective="wave",
                agent="opencode2",
                worktree="current",
                timeout_ms=5000,
            )
            summary = orca_wave.execute_dag(plan, args)
        finally:
            orca_wave.orca = original

        self.assertEqual(started, ["A", "B", "C", "D"])
        self.assertEqual(summary["missing"], [])
        self.assertEqual(len(summary["waves"]), 3)
        self.assertEqual(sum(1 for call in calls if "worker-release" in call), 4)

    def test_failed_prerequisite_stops_dag(self) -> None:
        started = []

        def fake(args):
            if args[0] == "orchestration" and args[1] == "run-create":
                return json.dumps({"result": {"run": {"id": "run_x"}}})
            if args[0] == "orchestration" and args[1] == "worker-start":
                task_id = args[args.index("--spec") + 1]
                started.append(task_id)
                return json.dumps(
                    {
                        "ok": True,
                        "result": {
                            "taskId": f"task_{task_id}",
                            "dispatchId": f"ctx_{task_id}",
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
                                {
                                    "type": "worker_done",
                                    "payload": {"dispatchId": "ctx_A", "outcome": "failed"},
                                }
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
                    {"id": "A", "spec": "A", "deps": []},
                    {"id": "B", "spec": "B", "deps": ["task:A"]},
                ]
            }
            summary = orca_wave.execute_dag(
                plan,
                argparse.Namespace(
                    dry_run=False,
                    json=True,
                    objective="wave",
                    agent="opencode2",
                    worktree="current",
                    timeout_ms=5000,
                ),
            )
        finally:
            orca_wave.orca = original
        self.assertEqual(started, ["A"])
        self.assertEqual(summary["failed"], ["ctx_A"])

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
