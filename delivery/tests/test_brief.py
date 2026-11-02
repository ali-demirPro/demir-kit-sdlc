"""Tests for the compact per-checkpoint brief."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("brief", SCRIPTS / "brief.py")
brief = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(brief)

SEAL = {
    "epic": 141,
    "intent": "Bağlam bütçesi ve CP brief.",
    "surfaces": ["kit.docs"],
    "reference": {"paths": ["delivery/scripts/brief.py"]},
    "acceptance_criteria": [
        {"id": "AC-1", "text": "Politika eklenir."},
        {"id": "AC-2", "text": "Spec kısalır."},
        {"id": "AC-3", "text": "Yalnız ikinci CP."},
    ],
    "risk": {"level": "medium"},
    "tests_plan": [
        {
            "checkpoint_id": "CP-1",
            "cases": [
                {"id": "T-1", "ac": "AC-1", "text": "Dosya var.", "check": "doc"},
                {"id": "T-2", "ac": "AC-2", "text": "Spec kısa.", "check": "unit"},
            ],
        },
        {
            "checkpoint_id": "CP-2",
            "cases": [
                {"id": "T-3", "ac": "AC-3", "text": "İkinci CP.", "check": "unit"},
            ],
        },
    ],
    "checkpoints": [
        {"id": "CP-1", "title": "Politika", "gates": {"behavior": True}},
        {
            "id": "CP-2",
            "title": "Spec",
            "depends_on": ["CP-1"],
            "gates": {"behavior": True, "ui": True},
        },
    ],
}


class CpBriefTests(unittest.TestCase):
    def test_brief_is_compact_and_scoped(self) -> None:
        text = brief.render_cp_brief(
            {"issue": 142, "risk": "medium"}, SEAL, "CP-1"
        )
        self.assertLess(len(text), 6000)
        self.assertIn("CP brief — CP-1", text)
        self.assertIn("AC-1", text)
        self.assertNotIn("AC-3: Yalnız ikinci CP", text)
        self.assertIn("T-1 (AC-1, doc)", text)
        self.assertNotIn("T-3", text)
        self.assertIn("delivery/scripts/brief.py", text)
        self.assertIn("doctor.sh --issue 142 --checkpoint CP-1", text)
        self.assertIn("demir-kit-evidence", text)
        self.assertIn("tamamını okuma", text)

    def test_designer_role_for_ui_gate(self) -> None:
        text = brief.render_cp_brief(
            {"issue": 142, "risk": "medium"}, SEAL, "CP-2"
        )
        self.assertIn("Rol: designer", text)
        self.assertIn("ui_visual", text)

    def test_unknown_checkpoint_fails(self) -> None:
        with self.assertRaises(ValueError):
            brief.render_cp_brief({"issue": 142}, SEAL, "CP-9")


if __name__ == "__main__":
    unittest.main()
