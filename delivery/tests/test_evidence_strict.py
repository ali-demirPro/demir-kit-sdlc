"""Tests for strict reviewer identity on new evidence."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("evidence_strict", SCRIPTS / "evidence.py")
evidence = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(evidence)


class StrictReviewerTests(unittest.TestCase):
    def test_placeholder_after_cutoff_is_rejected(self) -> None:
        message = evidence.placeholder_review_error("reviewer_a", "2026-11-08T09:00:01+00:00")
        self.assertIsNotNone(message)
        self.assertIn("yer tutucu", message)

    def test_placeholder_before_cutoff_is_allowed(self) -> None:
        self.assertIsNone(
            evidence.placeholder_review_error("reviewer_a", "2026-11-08T08:59:59+00:00")
        )

    def test_real_session_id_is_allowed(self) -> None:
        self.assertIsNone(
            evidence.placeholder_review_error("ses_e4a706487ffefaiRa22s7arUc5", "2026-11-09T00:00:00+00:00")
        )

    def test_missing_timestamp_is_legacy(self) -> None:
        self.assertIsNone(evidence.placeholder_review_error("reviewer_a", ""))


if __name__ == "__main__":
    unittest.main()
