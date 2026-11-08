"""Tests for the issue-doctor workflow trigger."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        data = yaml.safe_load((ROOT / ".github" / "workflows" / "issue-doctor.yml").read_text(encoding="utf-8"))
        self.condition = str(data["jobs"]["doctor"]["if"])

    def test_labeled_events_check_the_added_label(self) -> None:
        self.assertIn("github.event.label.name", self.condition)
        for label in ("agent-approved", "leaf-done", "epic-done"):
            self.assertIn(label, self.condition)

    def test_reopened_and_closed_keep_the_label_check(self) -> None:
        self.assertIn("github.event.action != 'labeled'", self.condition)

    def test_issue_labels_still_gate_the_job(self) -> None:
        self.assertIn("github.event.issue.labels.*.name", self.condition)


if __name__ == "__main__":
    unittest.main()
