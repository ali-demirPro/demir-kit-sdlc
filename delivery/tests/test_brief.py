"""Tests for the compact per-checkpoint brief."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

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
        self.assertIn("gate.sh --issue 142 --checkpoint CP-1", text)
        self.assertIn("demir-kit-evidence", text)
        self.assertIn("tamamını okuma", text)

    def test_prefix_uses_vendored_gate(self) -> None:
        text = brief.render_cp_brief(
            {"issue": 35, "risk": "medium"}, SEAL, "CP-1", "demir-kit/"
        )
        self.assertIn(
            "./demir-kit/delivery/scripts/gate.sh --issue 35 --checkpoint CP-1",
            text,
        )

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


class RouteTests(unittest.TestCase):
    """sink/window/retrieved selection + index contract (issue 312)."""

    ROUTE_SEAL = {
        "demir_kit_version": "2",
        "epic": 288,
        "entry": {"kind": "feature"},
        "factory": {"profile": "kit-internal"},
        "intent": "route testi",
        "surfaces": ["kit.scripts", "kit.docs"],
        "reference": {"paths": ["delivery/scripts/brief.py"]},
        "acceptance_criteria": [{"id": "AC-1", "text": "route"}],
        "risk": {"level": "medium"},
        "tests_plan": [
            {
                "checkpoint_id": "CP-1",
                "cases": [
                    {
                        "id": "T-1",
                        "ac": "AC-1",
                        "text": "route",
                        "check": "unit",
                    }
                ],
            }
        ],
        "checkpoints": [
            {"id": "CP-1", "title": "route", "gates": {"behavior": True}}
        ],
    }

    def write_index(self, directory, entries, version=1) -> Path:
        path = Path(directory) / "index.yaml"
        path.write_text(
            yaml.safe_dump(
                {"version": version, "entries": entries}, sort_keys=False
            ),
            encoding="utf-8",
        )
        return path

    def issue_body(self) -> str:
        return (
            "```yaml demir-kit\n"
            + yaml.safe_dump(self.ROUTE_SEAL, sort_keys=False)
            + "```"
        )

    def run_route(self, argv, index_path):
        issue = json.dumps(
            {"title": "route", "body": self.issue_body(), "labels": []}
        )
        out = io.StringIO()
        err = io.StringIO()
        with patch.object(brief, "repo_name", return_value="x/y"), patch.object(
            brief, "gh", return_value=issue
        ), patch.object(brief, "index_file", return_value=index_path), patch.object(
            sys, "argv", ["brief.py", *argv]
        ), contextlib.redirect_stdout(
            out
        ), contextlib.redirect_stderr(
            err
        ):
            code = brief.main()
        return code, out.getvalue(), err.getvalue()

    def test_route_is_deterministic_and_labelled(self) -> None:
        seal = {
            "surfaces": ["kit.scripts", "kit.docs"],
            "reference": {"paths": ["delivery/scripts/brief.py"]},
        }
        docs = [
            "delivery/agents/developer/ROLE.md",
            "delivery/agents/developer/how.md",
        ]
        entries = [
            {
                "surface": "kit.docs",
                "path": "delivery/context/index.yaml",
                "tags": ["context"],
                "weight": 2,
            },
            {
                "surface": "kit.scripts",
                "path": "delivery/scripts/resolver.py",
                "tags": ["code"],
                "weight": 5,
            },
            {
                "surface": "kit.docs",
                "path": "delivery/plans/P2.yaml",
                "tags": ["plan"],
                "weight": 6,
            },
            {
                "surface": "web.app",
                "path": "delivery/scripts/routing.py",
                "tags": ["code"],
                "weight": 9,
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            index_path = self.write_index(tmp, entries)
            index = brief.routing.load_route_index(index_path, ROOT)
            self.assertIsNotNone(index)
            first, fallback = brief.routing.build_route(seal, docs, index)
            second, _ = brief.routing.build_route(seal, docs, index)
            self.assertEqual(first, second)
            self.assertIsNone(fallback)
            retrieved = [
                item["path"] for item in first if item["class"] == "retrieved"
            ]
            self.assertEqual(
                retrieved,
                [
                    "delivery/plans/P2.yaml",
                    "delivery/scripts/resolver.py",
                    "delivery/context/index.yaml",
                ],
            )
            self.assertNotIn("delivery/scripts/routing.py", retrieved)
            self.assertEqual(
                {item["class"] for item in first},
                {"sink", "window", "retrieved"},
            )
            for item in first:
                self.assertIn(item["source"], brief.routing.ROUTE_SOURCES)
                self.assertTrue(item["reason"])
                line = brief.routing.render_route([item]).strip()
                self.assertRegex(
                    line,
                    rf"^{item['class']} {re.escape(item['path'])} "
                    rf"\(source: {item['source']}, reason: .+\)$",
                )

            code, plain, _ = self.run_route(["312", "--route"], index_path)
            cp_code, cp_plain, _ = self.run_route(
                ["312", "--route", "--cp", "CP-1"], index_path
            )
            self.assertEqual((code, cp_code), (0, 0))
            self.assertEqual(plain, cp_plain)
            self.assertNotIn("fallback:", plain)
            self.assertIn("retrieved delivery/plans/P2.yaml", plain)
            self.assertIn("retrieved delivery/scripts/resolver.py", plain)
            self.assertTrue(
                all(
                    re.match(
                        r"^(sink|window|retrieved) \S+ "
                        r"\(source: (seal|resolver|index|static), reason: .+\)$",
                        line,
                    )
                    for line in plain.strip().splitlines()
                )
            )

    def test_invalid_index_exits_two(self) -> None:
        valid = {
            "surface": "kit.docs",
            "path": "delivery/scripts/brief.py",
            "tags": [],
            "weight": 1,
        }
        cases = {
            "unknown_key": {"version": 1, "entries": [], "bogus": True},
            "missing_key": {
                "version": 1,
                "entries": [
                    {
                        "surface": "kit.docs",
                        "path": "delivery/scripts/brief.py",
                        "tags": [],
                    }
                ],
            },
            "unresolved_path": {
                "version": 1,
                "entries": [{**valid, "path": "delivery/yok/boyle-dosya.md"}],
            },
            "invalid_weight": {
                "version": 1,
                "entries": [{**valid, "weight": "ağır"}],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, payload in cases.items():
                with self.subTest(name=name):
                    path = Path(tmp) / f"{name}.yaml"
                    path.write_text(
                        yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
                    )
                    code, _, err = self.run_route(["312", "--route"], path)
                    self.assertEqual(code, 2)
                    self.assertTrue(err.strip())

    def test_missing_index_reports_fallback(self) -> None:
        missing = ROOT / "delivery" / "context" / "yok-boyle-index.yaml"
        self.assertFalse(missing.exists())
        code, out, _ = self.run_route(["312", "--route"], missing)
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(lines[0], "fallback: index yok")
        self.assertTrue(
            any(
                line.startswith("retrieved ") and "(source: static," in line
                for line in lines[1:]
            )
        )
        self.assertTrue(
            any(
                line.startswith("window ") and "(source: resolver," in line
                for line in lines[1:]
            )
        )
        for line in lines[1:]:
            self.assertRegex(
                line,
                r"^(sink|window|retrieved) \S+ "
                r"\(source: (seal|resolver|index|static), reason: .+\)$",
            )

        json_code, json_out, _ = self.run_route(
            ["312", "--route", "--json"], missing
        )
        self.assertEqual(json_code, 0)
        payload = json.loads(json_out)
        self.assertEqual(payload["issue"], 312)
        self.assertEqual(payload["fallback"], "index yok")
        self.assertTrue(payload["route"])


if __name__ == "__main__":
    unittest.main()
