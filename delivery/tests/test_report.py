"""Tests for the human work report."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("report", SCRIPTS / "report.py")
report = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(report)

EPIC_BODY = """```yaml demir-kit-epic
demir_kit_version: "2"
children: [23, 24]
```
"""


def issue(number=22, title="Epic", body=EPIC_BODY, labels=None):
    return {
        "number": number,
        "title": title,
        "body": body,
        "labels": labels or ["scope-confirmed", "human-qa"],
        "created_at": "2026-10-26T15:22:00Z",
        "updated_at": "2026-10-26T15:31:00Z",
        "comments": [
            {
                "body": "## Özet — 15:31\n\n**Ne bitti:** İş raporu eklendi.\n**Karar:** Issue yorumu.\n**Sorun:** Yok.\n**Onay:** gerekiyor",
                "created_at": "2026-10-26T15:31:00Z",
            }
        ],
        "evidence": [],
    }


class ReportTests(unittest.TestCase):
    def test_parse_children(self) -> None:
        self.assertEqual(report.parse_children(EPIC_BODY), [23, 24])
        self.assertEqual(report.parse_children("no block"), [])

    def test_extract_progress(self) -> None:
        result = report.extract_progress(
            [{"body": "**Karar:** A\n**Sorun:** B\n**Ne bitti:** C"}]
        )
        self.assertEqual(result["decisions"], ["A"])
        self.assertEqual(result["problems"], ["B"])
        self.assertEqual(result["done"], ["C"])

    def test_minutes(self) -> None:
        start = datetime(2026, 10, 26, 15, 22, tzinfo=timezone.utc)
        end = datetime(2026, 10, 26, 15, 31, tzinfo=timezone.utc)
        self.assertEqual(report.minutes(start, end), "9 dk")

    def test_build_report_sections(self) -> None:
        child = issue(23, "Child", labels=["leaf-done"])
        child["evidence"] = [
            {
                "agent": "developer",
                "reviews": {"adversarial": {"reviewer_a": "approved"}},
                "worker": {
                    "run_id": "run_x",
                    "task_id": "task_x",
                    "dispatch_id": "ctx_x",
                    "agent": "opencode2",
                    "outcome": "succeeded",
                },
            }
        ]
        usage = {
            "totals": {"sessions": 2, "input": 1000, "output": 50, "cache_read": 200, "cost": 0.01},
            "sessions": [],
            "unavailable": [],
        }
        text = report.build_report(issue(), [child], usage, ["abc123 test commit"])
        self.assertIn("## İş Raporu — #22 Epic", text)
        self.assertIn("1 ana agent (roller:", text)
        self.assertIn("1 Orca worker", text)
        self.assertIn("**Süre:**", text)
        self.assertIn("**Maliyet:** 2 oturum", text)
        self.assertIn("<details>", text)
        self.assertIn("abc123 test commit", text)
        self.assertIn("**Onay:** gerekiyor", text)
        self.assertNotIn("```yaml", text)

    def test_repo_name_uses_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ecosystem.yaml").write_text("tracker:\n  repo: owner/product\n")
            with patch.object(report, "PROJECT", root):
                self.assertEqual(report.repo_name(), "owner/product")

    def test_collect_commits_uses_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            captured = {}

            def fake(args, **kwargs):
                captured.update(kwargs)
                return "abc commit"

            with patch.object(report, "PROJECT", root), patch.object(
                report.subprocess, "check_output", fake
            ):
                commits = report.collect_commits(
                    datetime(2026, 10, 26, tzinfo=timezone.utc),
                    datetime(2026, 10, 27, tzinfo=timezone.utc),
                )
            self.assertEqual(commits, ["abc commit"])
            self.assertEqual(captured["cwd"], root)

    def test_build_report_uses_explicit_window(self) -> None:
        start = datetime(2026, 10, 26, 16, 5, tzinfo=timezone.utc)
        end = datetime(2026, 10, 26, 16, 20, tzinfo=timezone.utc)
        usage = {
            "totals": {"sessions": 1, "input": 10, "output": 2, "cache_read": 3, "cost": 0.01, "measured_sessions": 1, "confidence": "exact"},
            "sessions": [],
            "unavailable": [],
        }
        text = report.build_report(issue(), [], usage, [], start, end)
        self.assertIn("**Süre:** 16:05–16:20 UTC · 15 dk", text)

    def test_report_marks_unavailable_cost(self) -> None:
        usage = {
            "totals": {"sessions": 1, "input": 0, "output": 0, "cache_read": 0, "cost": 0},
            "sessions": [],
            "unavailable": ["ses_x"],
        }
        text = report.build_report(issue(), [], usage, [])
        self.assertIn("maliyeti ölçülemedi", text)


if __name__ == "__main__":
    unittest.main()
