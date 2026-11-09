"""Tests for the parallel reviewer wave."""

from __future__ import annotations

import importlib.util
import os
import io
import json
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "review_wave", SCRIPTS / "review_wave.py"
)
review_wave = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(review_wave)


class ReviewWaveTests(unittest.TestCase):
    def test_parse_verdict(self) -> None:
        self.assertTrue(review_wave.parse_verdict("approved: true\nnot: ok"))
        self.assertFalse(review_wave.parse_verdict("approved: false"))
        self.assertIsNone(review_wave.parse_verdict("findings: []"))
        self.assertTrue(
            review_wave.parse_verdict("CP-1 review: approved (1 low finding)")
        )
        self.assertFalse(review_wave.parse_verdict("CP-1 review: rejected"))
        self.assertIsNone(review_wave.parse_verdict("approved: true|false"))
        self.assertFalse(review_wave.parse_verdict("not yet approved"))
        self.assertFalse(review_wave.parse_verdict("approved:false."))
        self.assertIsNone(
            review_wave.parse_verdict("The approved plan has a bug")
        )

    def test_reviewer_spec_contains_packet_and_format(self) -> None:
        text = review_wave.reviewer_spec("adversarial-a", "PACKET", 156, "CP-1")
        self.assertIn("PACKET", text)
        self.assertIn("approved: true|false", text)
        self.assertIn("dosya değiştirme", text)

    def test_capture_session_records_new(self) -> None:
        with patch.object(
            review_wave.usage, "sessions_in", return_value=[{"id": "s_new"}]
        ), patch.object(review_wave.usage, "record_session") as record:
            session = review_wave.capture_session("ctx", "/w", {"s_old"}, 0, timeout=1)
        self.assertEqual(session["id"], "s_new")
        record.assert_called_once()

    def test_capture_session_ambiguous_or_timeout(self) -> None:
        with patch.object(
            review_wave.usage, "sessions_in",
            return_value=[{"id": "a"}, {"id": "b"}],
        ), patch.object(review_wave.usage, "record_session") as record:
            self.assertIsNone(
                review_wave.capture_session("ctx", "/w", set(), 0, timeout=1)
            )
        record.assert_not_called()
        with patch.object(
            review_wave.usage, "sessions_in", return_value=[]
        ), patch.object(review_wave.usage, "record_session") as record:
            self.assertIsNone(
                review_wave.capture_session("ctx", "/w", set(), 0, timeout=0)
            )
        record.assert_not_called()

    def test_start_worker(self) -> None:
        responses = [
            {"task": {"id": "task_1"}},
            {"dispatchId": "ctx_1"},
        ]
        with patch.object(
            review_wave, "capture_session", return_value=None
        ), patch.object(review_wave, "orca", side_effect=responses) as orca:
            worker = review_wave.start_worker("a", "SPEC", "run_1", "/tmp")
        self.assertEqual(worker["dispatch_id"], "ctx_1")
        self.assertEqual(orca.call_count, 2)

    def test_start_worker_passes_model_only_when_set(self) -> None:
        responses = [{"task": {"id": "t1"}}, {"dispatchId": "ctx"}]
        with patch.object(
            review_wave, "capture_session", return_value=None
        ), patch.object(review_wave, "orca", side_effect=responses) as orca:
            review_wave.start_worker("a", "SPEC", "run", "/tmp", "p/m")
        args = orca.call_args_list[1].args[0]
        self.assertIn("--model", args)
        self.assertIn("p/m", args)

        with patch.object(
            review_wave, "capture_session", return_value=None
        ), patch.object(review_wave, "orca", side_effect=responses) as orca:
            review_wave.start_worker("a", "SPEC", "run", "/tmp")
        self.assertNotIn("--model", orca.call_args_list[1].args[0])

    def test_wait_workers_settles(self) -> None:
        workers = [
            {"name": "a", "dispatch_id": "ctx_a", "state": "dispatched"},
            {"name": "b", "dispatch_id": "ctx_b", "state": "dispatched"},
        ]
        shows = [
            {"worker": {"state": "running"}},
            {"worker": {"state": "failed"}},
            {"worker": {"state": "succeeded"}},
        ]
        with patch.object(review_wave, "orca", side_effect=shows), patch.object(
            review_wave.time, "sleep"
        ) as sleep:
            result = review_wave.wait_workers(workers, timeout=60)
        self.assertEqual(result[0]["state"], "succeeded")
        self.assertEqual(result[1]["state"], "failed")
        sleep.assert_called()

    def test_wait_workers_settles_flat_state(self) -> None:
        # Orca 1.4 answers worker-show flat: {state, liveness}, no worker wrapper.
        workers = [
            {"name": "a", "dispatch_id": "ctx_a", "state": "dispatched"},
            {"name": "b", "dispatch_id": "ctx_b", "state": "dispatched"},
        ]
        shows = [
            {"state": "running", "liveness": "live"},
            {"state": "running", "liveness": "live"},
            {"state": "succeeded"},
            {"state": "stopped"},
        ]
        with patch.object(review_wave, "orca", side_effect=shows), patch.object(
            review_wave.time, "sleep"
        ):
            result = review_wave.wait_workers(workers, timeout=60)
        self.assertEqual(result[0]["state"], "succeeded")
        self.assertEqual(result[1]["state"], "stopped")

    def test_wait_workers_flat_state_wins_over_nested(self) -> None:
        workers = [{"name": "a", "dispatch_id": "ctx_a", "state": "dispatched"}]
        shows = [{"state": "stopped", "worker": {"state": "running"}}]
        with patch.object(review_wave, "orca", side_effect=shows):
            result = review_wave.wait_workers(workers, timeout=5)
        self.assertEqual(result[0]["state"], "stopped")

    def test_wait_workers_returns_at_deadline(self) -> None:
        workers = [{"name": "a", "dispatch_id": "ctx_a", "state": "dispatched"}]
        calls: list[dict] = []

        def fake_orca(args, timeout=None):
            calls.append({"args": args, "timeout": timeout})
            return {"state": "running"}

        started = time.monotonic()
        with patch.object(review_wave, "orca", side_effect=fake_orca):
            review_wave.wait_workers(workers, timeout=1, poll=5)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 3.0)
        self.assertEqual(workers[0]["state"], "dispatched")
        self.assertTrue(calls)
        self.assertTrue(
            all(call["timeout"] is not None and call["timeout"] <= 15 for call in calls)
        )

    def test_collect_reads_worker_done_message(self) -> None:
        workers = [{"name": "a", "dispatch_id": "ctx_a", "state": "succeeded"}]
        responses = [
            {
                "messages": [
                    {
                        "from_handle": "term_a",
                        "subject": "CP-1 review: approved (1 low)",
                        "body": "",
                    }
                ],
                "deliveryId": "d1",
            },
            {"worker": {"agentTerminalHandle": "term_a"}},
            {"ok": True},
        ]
        with patch.object(review_wave, "orca", side_effect=responses) as orca, patch.object(
            review_wave, "read_output", return_value="no verdict"
        ), patch.object(review_wave, "release_worker"):
            result = review_wave.collect(workers, "run_1")
        self.assertTrue(result[0]["verdict"])
        self.assertEqual(orca.call_args.args[0][-1], "d1")

    def test_collect_releases_and_parses(self) -> None:
        workers = [
            {"name": "a", "dispatch_id": "ctx_a", "state": "succeeded"},
            {"name": "b", "dispatch_id": "ctx_b", "state": "failed"},
        ]
        with patch.object(
            review_wave, "read_output", side_effect=["approved: true", "no verdict"]
        ), patch.object(
            review_wave, "release_worker"
        ) as release:
            result = review_wave.collect(workers)
        self.assertTrue(result[0]["verdict"])
        self.assertIsNone(result[1]["verdict"])
        self.assertIn("approved: true", result[0]["summary"])
        self.assertEqual(release.call_count, 2)


class ReviewWaveCliTests(unittest.TestCase):
    def run_main(self, argv: list[str]):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(
            review_wave.review_packet, "packet_for", return_value="PACKET"
        ), patch.object(sys, "argv", ["review_wave.py", *argv]), redirect_stdout(
            out
        ), redirect_stderr(err):
            code = review_wave.main()
        return code, out.getvalue(), err.getvalue()

    def test_plan_does_not_start(self) -> None:
        with patch.object(review_wave, "start_worker") as start:
            code, out, _ = self.run_main(
                ["--issue", "156", "--cp", "CP-1", "--reviewers", "a,b"]
            )
        self.assertEqual(code, 0)
        self.assertIn("Reviewer wave", out)
        start.assert_not_called()

    def test_apply_requires_run(self) -> None:
        with patch.object(review_wave, "epic_of", return_value=None):
            with self.assertRaises(SystemExit):
                self.run_main(["--issue", "156", "--cp", "CP-1", "--apply"])

    def test_apply_all_approved(self) -> None:
        workers = [
            {"name": "a", "dispatch_id": "ctx_a", "state": "succeeded"},
            {"name": "b", "dispatch_id": "ctx_b", "state": "succeeded"},
        ]
        with patch.object(review_wave, "start_worker", side_effect=workers), patch.object(
            review_wave, "wait_workers", return_value=workers
        ), patch.object(
            review_wave,
            "collect",
            side_effect=lambda items, run_id: [
                {**items[0], "verdict": True},
                {**items[1], "verdict": True},
            ],
        ):
            code, out, _ = self.run_main(
                [
                    "--issue", "156", "--cp", "CP-1", "--reviewers", "a,b",
                    "--run", "run_1", "--apply",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("approved", out)

    def test_apply_one_rejected(self) -> None:
        workers = [{"name": "a", "dispatch_id": "ctx_a", "state": "succeeded"}]
        with patch.object(review_wave, "start_worker", side_effect=workers), patch.object(
            review_wave, "wait_workers", return_value=workers
        ), patch.object(
            review_wave,
            "collect",
            side_effect=lambda items, run_id: [{**items[0], "verdict": False}],
        ):
            code, _, _ = self.run_main(
                ["--issue", "156", "--cp", "CP-1", "--run", "run_1", "--apply"]
            )
        self.assertEqual(code, 1)

class ReleaseWorkerTests(unittest.TestCase):
    def test_release_uses_orca_worker_release(self) -> None:
        with patch.object(review_wave, "orca", return_value="{}") as orca:
            review_wave.release_worker("ctx_1")
        self.assertEqual(
            orca.call_args.args[0],
            ["orchestration", "worker-release", "--dispatch", "ctx_1", "--json"],
        )

    def test_release_never_raises(self) -> None:
        with patch.object(review_wave, "orca", side_effect=RuntimeError("boom")):
            review_wave.release_worker("ctx_1")

    def test_no_reaper_references_remain(self) -> None:
        for name in ("orca_wave.py", "review_wave.py", "transition.py"):
            source = (ROOT / "delivery" / "scripts" / name).read_text(encoding="utf-8")
            self.assertNotIn("worker_reaper", source, name)
            self.assertNotIn("worker_cleanup", source, name)

class ReviewBatchTests(unittest.TestCase):
    def test_reviewers_are_split_into_bounded_batches(self) -> None:
        names = ["a", "b", "c", "d", "e"]
        self.assertEqual(
            review_wave.review_batches(names, {"reviewers": 2}),
            [["a", "b"], ["c", "d"], ["e"]],
        )

    def test_default_cap_is_two(self) -> None:
        self.assertEqual(
            review_wave.review_batches(["a", "b", "c"], {}), [["a", "b"], ["c"]]
        )

    def test_non_positive_cap_falls_back_to_default(self) -> None:
        self.assertEqual(
            review_wave.review_batches(["a", "b"], {"reviewers": -1}),
            [["a", "b"]],
        )

    def test_main_uses_bounded_batches(self) -> None:
        source = (ROOT / "delivery" / "scripts" / "review_wave.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("for batch in review_batches(", source)

class SettleBatchTests(unittest.TestCase):
    def test_dispatched_stragglers_are_stopped(self) -> None:
        workers = [
            {"name": "a", "dispatch_id": "ctx_a", "state": "dispatched"},
            {"name": "b", "dispatch_id": "ctx_b", "state": "succeeded"},
        ]
        with patch.object(review_wave, "stop_worker") as stop:
            review_wave.settle_batch(workers)
        stop.assert_called_once_with("ctx_a")


if __name__ == "__main__":
    unittest.main()
