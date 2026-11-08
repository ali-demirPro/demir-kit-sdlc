"""Tests for the OpenCode usage collector."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("usage", SCRIPTS / "usage.py")
usage = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(usage)


def export(cost=0.01, input_tokens=100, output_tokens=20, messages=None) -> dict:
    return {
        "info": {
            "cost": cost,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "reasoning": 0,
                "cache": {"read": 50, "write": 0},
            },
            "model": {"id": "test"},
            "time": {"created": 1_000, "updated": 61_000},
        },
        "messages": messages or [],
    }


class UsageTests(unittest.TestCase):
    def test_session_total_when_no_window_messages(self) -> None:
        result = usage.summarize_export(export(), 0, 999_999)
        self.assertEqual(result["confidence"], "session_total")
        self.assertEqual(result["cost"], 0.01)
        self.assertEqual(result["tokens"]["input"], 100)
        self.assertEqual(result["duration_seconds"], 60)

    def test_exact_window_messages(self) -> None:
        messages = [
            {
                "time": {"created": 10_000},
                "cost": 0.02,
                "tokens": {"input": 200, "output": 30, "reasoning": 5, "cache": {"read": 70, "write": 1}},
            },
            {"time": {"created": 90_000}, "cost": 9.0, "tokens": {"input": 1}},
        ]
        result = usage.summarize_export(export(messages=messages), 0, 50_000)
        self.assertEqual(result["confidence"], "exact")
        self.assertEqual(result["cost"], 0.02)
        self.assertEqual(result["tokens"]["input"], 200)
        self.assertEqual(result["tokens"]["cache_read"], 70)

    def test_unavailable_is_explicit(self) -> None:
        result = usage.summarize_export({"info": {"time": {}}, "messages": []}, 0, 1)
        self.assertEqual(result["confidence"], "unavailable")
        self.assertIsNone(result["cost"])

    def test_current_session_prefers_main_duration(self) -> None:
        sessions = [
            {"id": "worker", "directory": "/p", "created": 1000, "updated": 2000},
            {"id": "main", "directory": "/p", "created": 1, "updated": 5000},
        ]
        with patch.object(usage, "run", return_value=json.dumps(sessions)), patch.dict(
            usage.os.environ, {}, clear=True
        ):
            session = usage.current_session(Path("/p"))
        self.assertEqual(session["id"], "main")

    def test_compute_delta(self) -> None:
        snap = {
            "session_id": "s",
            "cost": 0.5,
            "tokens": {"input": 100, "output": 10, "cache": {"read": 50, "write": 0}},
            "time": {"updated": 1000},
        }
        cur = {
            "id": "s",
            "cost": 0.6,
            "tokens": {"input": 150, "output": 20, "cache": {"read": 70, "write": 1}},
            "time": {"updated": 61_000},
        }
        delta = usage.compute_delta(snap, cur)
        self.assertEqual(delta["cost"], 0.1)
        self.assertEqual(delta["tokens"]["input"], 50)
        self.assertEqual(delta["tokens"]["output"], 10)
        self.assertEqual(delta["tokens"]["cache_read"], 20)
        self.assertEqual(delta["duration_seconds"], 60)

    def test_delta_session_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            usage.compute_delta({"session_id": "a"}, {"id": "b"})

    def test_snapshot_path(self) -> None:
        path = usage.snapshot_path(41, Path("/tmp/product"))
        self.assertEqual(path, Path("/tmp/product/.orchestration/usage-41.json"))

    def test_project_root_uses_cwd_with_kit_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text("kit:\n  root: demir-kit\n")
            self.assertEqual(usage.project_root(root), root)

    def test_render_session_total(self) -> None:
        data = {
            "totals": {
                "sessions": 2,
                "input": 10,
                "output": 2,
                "cache_read": 3,
                "cost": 0.01,
                "measured_sessions": 1,
                "session_total_cost": 0.5,
                "session_total_sessions": 1,
                "confidence": "exact",
            },
            "sessions": [],
            "unavailable": [],
        }
        text = usage.render(data)
        self.assertIn("Ana oturum toplamı: $0.5000", text)

    def test_render_marks_unavailable(self) -> None:
        data = {
            "totals": {"sessions": 1, "input": 10, "output": 2, "cache_read": 3, "cost": None, "measured_sessions": 0, "confidence": "partial"},
            "sessions": [
                {"title": "test", "cost": None, "confidence": "unavailable"}
            ],
            "unavailable": ["ses_x"],
        }
        text = usage.render(data)
        self.assertIn("Maliyet: ölçülemedi", text)
        self.assertNotIn("$0.0000", text)
        self.assertIn("Oturumlar: 1", text)


class WorkerUsageTests(unittest.TestCase):
    def test_session_for_window_picks_closest_to_start(self) -> None:
        sessions = [
            {"id": "late", "created": 9_000},
            {"id": "early", "created": 1_000},
            {"id": "outside", "created": 900_000},
        ]
        picked = usage.session_for_window(sessions, 0, 10_000)
        self.assertEqual(picked["id"], "early")
        self.assertIsNone(usage.session_for_window([{"id": "far", "created": 900_000}], 0, 2_000))

    def test_dispatch_usage_unavailable_without_session(self) -> None:
        record = {
            "dispatch": {
                "runId": "run_x",
                "status": "completed",
                "dispatchedAt": "2026-11-02 08:00:00",
                "completedAt": "2026-11-02 08:05:00",
            },
            "path": "/tmp/no-such-worktree",
        }
        with patch.object(usage, "dispatch_record", return_value=record), patch.object(
            usage, "sessions_in", return_value=[]
        ):
            row = usage.dispatch_usage("ctx_missing")
        self.assertEqual(row["confidence"], "unavailable")
        self.assertIsNone(row["cost"])
        self.assertEqual(row["tokens"]["input"], 0)
        self.assertEqual(row["duration_seconds"], 300.0)

    def test_dispatch_usage_matches_session_window(self) -> None:
        start = int(usage.parse_dispatch_time("2026-11-02 08:00:00").timestamp() * 1000)
        record = {
            "dispatch": {
                "runId": "run_x",
                "status": "completed",
                "dispatchedAt": "2026-11-02 08:00:00",
                "completedAt": "2026-11-02 08:05:00",
            },
            "path": "/tmp/worktree",
        }
        messages = [
            {
                "time": {"created": start + 10_000},
                "cost": 0.02,
                "tokens": {
                    "input": 200,
                    "output": 30,
                    "reasoning": 5,
                    "cache": {"read": 70, "write": 0},
                },
            }
        ]
        with patch.object(usage, "dispatch_record", return_value=record), patch.object(
            usage, "sessions_in", return_value=[{"id": "ses_w", "created": start}]
        ), patch.object(
            usage, "session_export", return_value=export(messages=messages)
        ):
            row = usage.dispatch_usage("ctx_w")
        self.assertEqual(row["confidence"], "exact")
        self.assertEqual(row["session_id"], "ses_w")
        self.assertEqual(row["cost"], 0.02)
        self.assertEqual(row["tokens"]["input"], 200)
        self.assertEqual(row["context_peak"], 270)

    def test_dispatch_usage_with_mapped_session_is_exact(self) -> None:
        start = int(usage.parse_dispatch_time("2026-11-02 08:00:00").timestamp() * 1000)
        record = {
            "dispatch": {
                "runId": "run_x",
                "status": "completed",
                "dispatchedAt": "2026-11-02 08:00:00",
                "completedAt": "2026-11-02 08:05:00",
            },
            "path": "/tmp/worktree",
        }
        messages = [
            {
                "time": {"created": start + 10_000},
                "cost": 0.02,
                "tokens": {
                    "input": 200, "output": 30, "reasoning": 0,
                    "cache": {"read": 70, "write": 0},
                },
            }
        ]
        with patch.object(usage, "dispatch_record", return_value=record), patch.object(
            usage, "mapped_session", return_value={"id": "ses_w"}
        ), patch.object(
            usage, "session_export", return_value=export(messages=messages)
        ):
            row = usage.dispatch_usage("ctx_w")
        self.assertEqual(row["confidence"], "exact")
        self.assertEqual(row["session_id"], "ses_w")

    def test_run_usage_without_mapping_is_unavailable(self) -> None:
        windows = [
            {
                "dispatch_id": "ctx_a",
                "dispatch": {
                    "runId": "run_x",
                    "status": "completed",
                    "dispatchedAt": "2026-11-02 08:00:00",
                    "completedAt": "2026-11-02 08:05:00",
                },
                "path": "/w",
                "start_ms": 0,
                "end_ms": 10_000,
            }
        ]
        with patch.object(
            usage, "run_workers", return_value=[{"dispatchId": "ctx_a"}]
        ), patch.object(usage, "worker_window", return_value=windows[0]), patch.object(
            usage, "mapped_session", return_value=None
        ), patch.object(usage, "sessions_in", return_value=[]):
            data = usage.run_usage("run_x")
        self.assertEqual(data["totals"]["unavailable"], 1)
        self.assertIsNone(data["totals"]["cost_usd"])

    def test_record_and_mapped_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.json"
            with patch.object(usage, "session_map_path", return_value=path):
                usage.record_session(
                    "ctx_a",
                    {"id": "s1", "title": "t", "created": 1, "updated": 2},
                )
                self.assertEqual(usage.mapped_session("ctx_a")["id"], "s1")

    def test_run_workers_paginates(self) -> None:
        pages = [
            {"workers": [{"dispatchId": "ctx_a"}], "page": {"nextCursor": "c1"}},
            {"workers": [{"dispatchId": "ctx_b"}], "page": {"nextCursor": None}},
        ]
        with patch.object(usage, "orca_result", side_effect=pages) as orca:
            rows = usage.run_workers("run_x")
        self.assertEqual([row["dispatchId"] for row in rows], ["ctx_a", "ctx_b"])
        self.assertEqual(orca.call_count, 2)
        first = orca.call_args_list[0].args[0]
        self.assertIn("--run", first)
        self.assertIn("run_x", first)
        self.assertIn("--cursor", orca.call_args.args[0])

    def test_run_usage_aggregates_workers(self) -> None:
        rows = [
            {
                "dispatch_id": "ctx_a",
                "confidence": "exact",
                "cost": 0.5,
                "context_peak": 1000,
                "tokens": {"input": 10, "output": 2, "cache_read": 100},
            },
            {
                "dispatch_id": "ctx_b",
                "confidence": "unavailable",
                "cost": None,
                "context_peak": 0,
                "tokens": {"input": 0, "output": 0, "cache_read": 0},
            },
        ]
        windows = [
            {"dispatch_id": "ctx_a", "path": "/w", "start_ms": 0, "end_ms": 10_000},
            {"dispatch_id": "ctx_b", "path": "/w", "start_ms": 10_000, "end_ms": 20_000},
        ]
        with patch.object(
            usage, "run_workers", return_value=[{"dispatchId": "ctx_a"}, {"dispatchId": "ctx_b"}]
        ), patch.object(usage, "worker_window", side_effect=windows), patch.object(
            usage, "dispatch_usage", side_effect=rows
        ):
            data = usage.run_usage("run_x")
        self.assertEqual(data["totals"]["worker_count"], 2)
        self.assertEqual(data["totals"]["measured"], 1)
        self.assertEqual(data["totals"]["unavailable"], 1)
        self.assertEqual(data["totals"]["tokens_in"], 10)
        self.assertEqual(data["totals"]["cost_usd"], 0.5)


    def test_sessions_in_filters_by_directory(self) -> None:
        with tempfile.TemporaryDirectory() as worktree:
            rows = [
                {"id": "right", "directory": worktree},
                {"id": "other", "directory": "/tmp/main"},
            ]
            with patch.object(usage, "run_in", return_value=json.dumps(rows)):
                picked = usage.sessions_in(worktree)
        self.assertEqual([row["id"] for row in picked], ["right"])

    def test_sessions_in_ignores_blank_directory(self) -> None:
        with tempfile.TemporaryDirectory() as worktree:
            old = Path.cwd()
            import os

            os.chdir(worktree)
            try:
                rows = [
                    {"id": "blank", "directory": ""},
                    {"id": "right", "directory": worktree},
                ]
                with patch.object(usage, "run_in", return_value=json.dumps(rows)):
                    picked = usage.sessions_in(worktree)
            finally:
                os.chdir(old)
        self.assertEqual([row["id"] for row in picked], ["right"])

    def test_ambiguous_window_returns_none(self) -> None:
        sessions = [
            {"id": "a", "created": 10_000},
            {"id": "b", "created": 12_000},
        ]
        self.assertIsNone(usage.session_for_window(sessions, 10_000, 300_000))

    def test_session_total_is_not_charged_to_dispatch(self) -> None:
        start = int(usage.parse_dispatch_time("2026-11-02 08:00:00").timestamp() * 1000)
        record = {
            "dispatch": {
                "runId": "run_x",
                "status": "completed",
                "dispatchedAt": "2026-11-02 08:00:00",
                "completedAt": "2026-11-02 08:05:00",
            },
            "path": "/tmp/worktree",
        }
        with patch.object(usage, "dispatch_record", return_value=record), patch.object(
            usage, "sessions_in", return_value=[{"id": "ses_w", "created": start}]
        ), patch.object(
            usage, "session_export", return_value=export()
        ):
            row = usage.dispatch_usage("ctx_w")
        self.assertEqual(row["confidence"], "unavailable")
        self.assertIsNone(row["cost"])

    def test_context_peak_uses_window_and_cache_write(self) -> None:
        start = int(usage.parse_dispatch_time("2026-11-02 08:00:00").timestamp() * 1000)
        record = {
            "dispatch": {
                "runId": "run_x",
                "status": "completed",
                "dispatchedAt": "2026-11-02 08:00:00",
                "completedAt": "2026-11-02 08:05:00",
            },
            "path": "/tmp/worktree",
        }
        messages = [
            {
                "time": {"created": start + 10_000},
                "cost": 0.02,
                "tokens": {
                    "input": 100,
                    "output": 10,
                    "reasoning": 0,
                    "cache": {"read": 50, "write": 10},
                },
            },
            {
                "time": {"created": start + 600_000},
                "cost": 9.0,
                "tokens": {
                    "input": 1,
                    "output": 1,
                    "reasoning": 0,
                    "cache": {"read": 99_999, "write": 0},
                },
            },
        ]
        with patch.object(usage, "dispatch_record", return_value=record), patch.object(
            usage, "sessions_in", return_value=[{"id": "ses_w", "created": start}]
        ), patch.object(
            usage, "session_export", return_value=export(messages=messages)
        ):
            row = usage.dispatch_usage("ctx_w")
        self.assertEqual(row["context_peak"], 160)

    def test_repeated_cursor_does_not_loop(self) -> None:
        pages = [
            {"workers": [{"dispatchId": "ctx_a"}], "page": {"nextCursor": "c1"}},
            {"workers": [{"dispatchId": "ctx_b"}], "page": {"nextCursor": "c1"}},
            {"workers": [{"dispatchId": "ctx_c"}], "page": {"nextCursor": None}},
        ]
        with patch.object(usage, "orca_result", side_effect=pages) as orca:
            rows = usage.run_workers("run_x")
        self.assertEqual(orca.call_count, 2)
        self.assertEqual([row["dispatchId"] for row in rows], ["ctx_a", "ctx_b"])


class ContextBudgetTests(unittest.TestCase):
    def test_warn_and_hard_limits(self) -> None:
        self.assertEqual(usage.context_state(120_000), (0, ""))
        warn_code, warn_text = usage.context_state(250_000)
        self.assertEqual(warn_code, 0)
        self.assertIn("200,000", warn_text)
        hard_code, hard_text = usage.context_state(320_000)
        self.assertEqual(hard_code, 1)
        self.assertIn("300,000", hard_text)

    def test_policy_matches_the_limits(self) -> None:
        text = (ROOT / "delivery" / "policies" / "context-budget.md").read_text(encoding="utf-8")
        self.assertIn("300k token", text)
        self.assertIn("200k token", text)

class CaptureSessionTests(unittest.TestCase):
    def test_new_session_is_recorded(self) -> None:
        session = {"id": "ses_new", "created": 1000}
        with patch.object(usage, "sessions_in", return_value=[session]), \
             patch.object(usage, "record_session") as record:
            picked = usage.capture_session("ctx_1", "/tmp/w", set(), 0, timeout=0.1)
        self.assertEqual(picked, session)
        record.assert_called_once_with("ctx_1", session)

    def test_ambiguous_sessions_are_not_mapped(self) -> None:
        sessions = [{"id": "a", "created": 1000}, {"id": "b", "created": 1001}]
        with patch.object(usage, "sessions_in", return_value=sessions), \
             patch.object(usage, "record_session") as record:
            picked = usage.capture_session("ctx_1", "/tmp/w", set(), 0, timeout=0.1)
        self.assertIsNone(picked)
        record.assert_not_called()

    def test_map_new_session_records_a_single_new_session(self) -> None:
        session = {"id": "ses_new", "created": 2000}
        with patch.object(usage, "sessions_in", return_value=[session]), \
             patch.object(usage, "record_session") as record:
            picked = usage.map_new_session("ctx_1", "/tmp/w", 1000)
        self.assertEqual(picked, session)
        record.assert_called_once_with("ctx_1", session)

    def test_map_new_session_ignores_old_or_ambiguous_sessions(self) -> None:
        old = [{"id": "ses_old", "created": 100}]
        with patch.object(usage, "sessions_in", return_value=old), \
             patch.object(usage, "record_session") as record:
            self.assertIsNone(usage.map_new_session("ctx_1", "/tmp/w", 5000))
        record.assert_not_called()

    def test_map_new_session_rejects_ambiguous_window(self) -> None:
        sessions = [
            {"id": "ses_a", "created": 1500},
            {"id": "ses_b", "created": 1600},
        ]
        with patch.object(usage, "sessions_in", return_value=sessions), \
             patch.object(usage, "record_session") as record:
            self.assertIsNone(usage.map_new_session("ctx_1", "/tmp/w", 1000))
        record.assert_not_called()

    def test_map_new_session_rejects_a_late_session(self) -> None:
        late = [{"id": "ses_late", "created": 10_000_000}]
        with patch.object(usage, "sessions_in", return_value=late), \
             patch.object(usage, "record_session") as record:
            self.assertIsNone(usage.map_new_session("ctx_1", "/tmp/w", 1000))
        record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
