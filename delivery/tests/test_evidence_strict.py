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

doctor_spec = importlib.util.spec_from_file_location("doctor_not_run", SCRIPTS / "doctor.py")
doctor = importlib.util.module_from_spec(doctor_spec)
assert doctor_spec.loader is not None
doctor_spec.loader.exec_module(doctor)


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

    def test_offset_is_compared_as_time(self) -> None:
        # 08:26:59Z = 11:26:59+03:00 → kesmeden ÖNCE
        self.assertIsNone(
            evidence.placeholder_review_error("reviewer_a", "2026-11-08T11:26:59+03:00")
        )
        # 10:00:00Z = 05:00:00-05:00 → kesmeden SONRA
        self.assertIsNotNone(
            evidence.placeholder_review_error("reviewer_a", "2026-11-08T05:00:00-05:00")
        )

    def test_missing_timestamp_is_legacy(self) -> None:
        self.assertIsNone(evidence.placeholder_review_error("reviewer_a", ""))


class NotRunReportTests(unittest.TestCase):
    def setUp(self) -> None:
        doctor.NOTES.clear()

    def test_not_run_rows_and_counts_are_printed(self) -> None:
        summary = doctor.report_not_run(
            "CP-1",
            [
                {"case": "T-1", "result": "pass"},
                {"case": "T-2", "result": "not_run", "note": "araç PATH'te yok"},
            ],
        )
        self.assertEqual(summary["not_run"], 1)
        self.assertIn("CP-1 not_run: T-2 — araç PATH'te yok", doctor.NOTES)
        self.assertIn("CP-1: 1 koştu, 1 koşmadı", doctor.NOTES)

    def test_not_run_without_reason_is_loud(self) -> None:
        doctor.report_not_run("CP-2", [{"case": "T-9", "result": "not_run"}])
        self.assertIn("CP-2 not_run: T-9 — gerekçe yok", doctor.NOTES)

    def test_clean_tests_leave_no_note(self) -> None:
        doctor.report_not_run("CP-3", [{"case": "T-1", "result": "pass"}])
        self.assertEqual(doctor.NOTES, [])


if __name__ == "__main__":
    unittest.main()
