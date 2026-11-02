"""Tests for the compact per-checkpoint brief."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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
        {"id": "CP-3", "title": "Case yok", "gates": {"behavior": True}},
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

    def test_high_risk_skeleton_follows_reviewers(self) -> None:
        text = brief.render_cp_brief(
            {"issue": 142, "risk": "high"},
            SEAL,
            "CP-1",
            gates={"behavior": True, "architect": True, "commercial": True},
            risk="high",
        )
        self.assertIn("reviewer_a: approved, reviewer_b: approved", text)
        self.assertIn("architect: approved", text)
        self.assertIn("commercial: approved", text)
        self.assertIn("human: approved", text)
        self.assertIn("Gate: behavior, architect, commercial", text)

    def test_critical_cp_platform_gate_adds_human_second(self) -> None:
        text = brief.render_cp_brief(
            {"issue": 142, "risk": "critical"},
            SEAL,
            "CP-1",
            gates={"behavior": True, "platform": True},
            risk="critical",
        )
        self.assertIn("platform: pass", text)
        self.assertIn("human_second: approved", text)
        self.assertIn("platform", text.split("Kanıt")[0])

    def test_profile_platform_gate_at_medium(self) -> None:
        text = brief.render_cp_brief(
            {"issue": 142, "risk": "medium"},
            SEAL,
            "CP-1",
            gates={"behavior": True},
            risk="medium",
            profile_gates={"platform": True},
        )
        self.assertIn("platform: pass", text)
        self.assertNotIn("platform: approved", text)

    def test_profile_gates_follow_project_packs(self) -> None:
        with patch.object(
            brief.profiles, "compose", return_value={"platform_packs": ["apple"]}
        ):
            gates = brief.profiles.gates_for(Path("/tmp"), "kit-internal")
        self.assertTrue(gates.get("platform"))

    def test_profile_gates_from_seal_packs_and_extra_gates(self) -> None:
        with patch.object(
            brief.profiles,
            "load_profile",
            return_value={"platform_packs": ["apple"], "extra_gates": ["architect"]},
        ), patch.object(brief.profiles, "compose", return_value={}):
            gates = brief.profiles.gates_for(Path("/tmp"), "ios-app")
        self.assertTrue(gates.get("platform"))
        self.assertTrue(gates.get("architect"))

    def test_profile_gates_from_project_extra_gates(self) -> None:
        with patch.object(
            brief.profiles,
            "compose",
            return_value={"platform_packs": [], "extra_gates": ["human"]},
        ):
            gates = brief.profiles.gates_for(Path("/tmp"))
        self.assertTrue(gates.get("human"))
        self.assertTrue(gates.get("platform"))

    def test_brief_without_evidence_for_review(self) -> None:
        text = brief.render_cp_brief(
            {"issue": 142, "risk": "medium"},
            SEAL,
            "CP-1",
            include_evidence=False,
        )
        self.assertNotIn("demir-kit-evidence", text)
        self.assertIn("AC (bu CP)", text)

    def test_case_less_cp_does_not_invent_tests(self) -> None:
        text = brief.render_cp_brief(
            {"issue": 142, "risk": "medium"}, SEAL, "CP-3"
        )
        self.assertNotIn("AC-1:", text)
        self.assertNotIn("T-1", text)
        self.assertNotIn("demir-kit-evidence", text)
        self.assertIn("seal'i düzelt", text)

    def test_medium_human_gate_adds_human(self) -> None:
        text = brief.render_cp_brief(
            {"issue": 142, "risk": "medium"},
            SEAL,
            "CP-1",
            gates={"behavior": True, "human": True},
            risk="medium",
        )
        self.assertIn("human: approved", text)

    def test_ui_gate_adds_ui_pass(self) -> None:
        text = brief.render_cp_brief(
            {"issue": 142, "risk": "medium"}, SEAL, "CP-2"
        )
        self.assertIn("ui: pass", text)

    def test_skeleton_matches_routing_reviewers(self) -> None:
        gates = {"behavior": True, "ui": True}
        text = brief.render_cp_brief(
            {"issue": 142, "risk": "medium"},
            SEAL,
            "CP-2",
            gates=gates,
            risk="medium",
        )
        for role in brief.routing.evidence_reviewers(gates, "medium"):
            self.assertIn(role, text)

    def test_unknown_checkpoint_fails(self) -> None:
        with self.assertRaises(ValueError):
            brief.render_cp_brief({"issue": 142}, SEAL, "CP-9")


if __name__ == "__main__":
    unittest.main()
