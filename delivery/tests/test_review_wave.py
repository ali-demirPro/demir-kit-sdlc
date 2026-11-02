"""Tests for the parallel reviewer wave."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
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
            session = review_wave.capture_session("ctx", "/w", {"s_old"}, timeout=1)
        self.assertEqual(session["id"], "s_new")
        record.assert_called_once()

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
        ), patch.object(review_wave.worker_cleanup, "release"):
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
            review_wave.worker_cleanup, "release"
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


if __name__ == "__main__":
    unittest.main()
