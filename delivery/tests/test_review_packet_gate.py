"""Tests for the gate result carried in the review packet."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("review_packet_g", SCRIPTS / "review_packet.py")
packet = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(packet)


class GateSummaryTests(unittest.TestCase):
    def test_cache_wins_over_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / ".kit").mkdir()
            (project / ".kit" / "gate-cache.json").write_text(
                json.dumps({"abc": {"ts": 10, "code": 0}, "def": {"ts": 20, "code": 1}}),
                encoding="utf-8",
            )
            (project / ".kit" / "cycle.jsonl").write_text(
                json.dumps({"ts": "2026-11-08T10:00:00+00:00", "issue": 1, "stage": "gate"}),
                encoding="utf-8",
            )
            data = packet.gate_summary(project)
        self.assertEqual(data["source"], "cache")
        self.assertEqual(data["key"], "def")
        self.assertEqual(data["exit"], 1)
        self.assertEqual(data["ts"], 20)

    def test_cycle_is_the_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / ".kit").mkdir()
            (project / ".kit" / "cycle.jsonl").write_text(
                json.dumps(
                    {
                        "ts": "2026-11-08T10:00:00+00:00",
                        "issue": 1,
                        "stage": "gate",
                        "reason": "CP-1 exit=0",
                    }
                ),
                encoding="utf-8",
            )
            data = packet.gate_summary(project)
        self.assertEqual(data["source"], "cycle")
        self.assertEqual(data["reason"], "CP-1 exit=0")

    def test_missing_artifacts_report_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(packet.gate_summary(Path(directory))["source"], "none")


class SkillTests(unittest.TestCase):
    def test_skill_tells_reviewers_not_to_run_the_gate(self) -> None:
        text = (ROOT / "skills" / "adversarial-review" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Kapıyı yeniden koşma", text)
        self.assertIn("Kapı:", text)


if __name__ == "__main__":
    unittest.main()
