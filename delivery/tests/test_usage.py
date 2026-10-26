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


if __name__ == "__main__":
    unittest.main()
