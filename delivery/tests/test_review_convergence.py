"""Tests for review convergence: severity gates the verdict."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("review_wave_c", SCRIPTS / "review_wave.py")
wave = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(wave)

BLOCKING = """approved: false
findings:
- severity: blocking
  file: a.py:1
  problem: hata
- severity: nit
  file: b.py:2
  problem: küçük
"""

ONLY_NITS = """approved: true
findings:
- severity: nit
  file: b.py:2
  problem: küçük
"""

INVALID_SEVERITY = """approved: true
findings:
- severity: medium
  file: a.py:1
  problem: orta
"""

MISSING_SEVERITY = """approved: true
findings:
- file: a.py:1
  problem: etiketsiz
"""


class SeverityTests(unittest.TestCase):
    def test_findings_are_split_by_severity(self) -> None:
        findings = wave.parse_findings(BLOCKING)
        self.assertEqual([item["severity"] for item in findings], ["blocking", "nit"])
        self.assertIn("a.py", findings[0]["text"])

    def test_blocking_finding_blocks_approval(self) -> None:
        self.assertFalse(wave.parse_verdict(BLOCKING))
        self.assertEqual(wave.blocking_count(BLOCKING), 1)

    def test_only_nits_can_be_approved(self) -> None:
        self.assertTrue(wave.parse_verdict(ONLY_NITS))
        self.assertEqual(wave.blocking_count(ONLY_NITS), 0)

    def test_unlabelled_approval_is_unchanged(self) -> None:
        self.assertTrue(wave.parse_verdict("approved: true"))

    def test_invalid_severity_rejects_approval(self) -> None:
        self.assertFalse(wave.parse_verdict(INVALID_SEVERITY))
        self.assertEqual(len(wave.invalid_findings(INVALID_SEVERITY)), 1)

    def test_missing_severity_rejects_approval(self) -> None:
        self.assertFalse(wave.parse_verdict(MISSING_SEVERITY))
        self.assertEqual(len(wave.invalid_findings(MISSING_SEVERITY)), 1)

    def test_valid_findings_have_no_invalid_entries(self) -> None:
        self.assertEqual(wave.invalid_findings(ONLY_NITS), [])
        self.assertEqual(wave.invalid_findings(BLOCKING), [])

    def test_skill_documents_the_round_policy(self) -> None:
        text = (ROOT / "skills" / "adversarial-review" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("severity: blocking|nit", text)
        self.assertIn("Tur 3", text)


if __name__ == "__main__":
    unittest.main()
