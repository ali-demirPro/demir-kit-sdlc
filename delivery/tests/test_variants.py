"""Tests for agent capability → variant maps."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("variants", SCRIPTS / "variants.py")
variants = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(variants)

doctor_spec = importlib.util.spec_from_file_location("doctor", SCRIPTS / "doctor.py")
doctor = importlib.util.module_from_spec(doctor_spec)
assert doctor_spec.loader is not None
doctor_spec.loader.exec_module(doctor)

CAPABILITIES = (
    variants.load_yaml(ROOT / "delivery" / "capabilities" / "registry.yaml").get(
        "capabilities"
    )
    or {}
)
ROLES = set(
    (variants.load_yaml(ROOT / "delivery" / "registry.yaml").get("role_order_default") or [])
) | {"orchestrator"}
MATRIX = variants.load_yaml(ROOT / "delivery" / "capabilities" / "role-matrix.yaml")
SCHEMA = json.loads(
    (ROOT / "delivery" / "schemas" / "agent.schema.json").read_text()
)


class VariantTests(unittest.TestCase):
    def test_designer_and_tester_are_valid(self) -> None:
        for role in ("designer", "tester"):
            agent = variants.load_agent(role)
            self.assertEqual(doctor.validate_schema(agent, SCHEMA), [])
            self.assertEqual(
                variants.validate_agent(role, agent, CAPABILITIES, ROLES), []
            )

    def test_unknown_capability(self) -> None:
        agent = copy.deepcopy(variants.load_agent("designer"))
        agent["capabilities_required"].append("platform.unknown")
        agent["variants"]["platform.unknown"] = {
            "doc": "variants/web.md",
            "eval": "evals/web.md",
            "min_level": "expert",
        }
        errors = variants.validate_agent("designer", agent, CAPABILITIES, ROLES)
        self.assertTrue(any("bilinmeyen capability" in item for item in errors))

    def test_missing_variant_doc(self) -> None:
        agent = copy.deepcopy(variants.load_agent("designer"))
        agent["variants"]["platform.web"]["doc"] = "variants/missing.md"
        errors = variants.validate_agent("designer", agent, CAPABILITIES, ROLES)
        self.assertTrue(any("variant doc yok" in item for item in errors))

    def test_missing_eval_doc(self) -> None:
        agent = copy.deepcopy(variants.load_agent("tester"))
        agent["variants"]["platform.ios"]["eval"] = "evals/missing.md"
        errors = variants.validate_agent("tester", agent, CAPABILITIES, ROLES)
        self.assertTrue(any("eval doc yok" in item for item in errors))

    def test_id_mismatch(self) -> None:
        agent = copy.deepcopy(variants.load_agent("designer"))
        agent["id"] = "tester"
        errors = variants.validate_agent("designer", agent, CAPABILITIES, ROLES)
        self.assertTrue(any("id" in item and "eşleşmiyor" in item for item in errors))

    def test_authority_min_level_rejected(self) -> None:
        agent = copy.deepcopy(variants.load_agent("designer"))
        agent["variants"]["platform.web"]["min_level"] = "authority"
        errors = variants.validate_agent("designer", agent, CAPABILITIES, ROLES)
        self.assertTrue(any("authority olamaz" in item for item in errors))

    def test_min_level_below_role_matrix(self) -> None:
        agent = copy.deepcopy(variants.load_agent("designer"))
        agent["variants"]["platform.web"]["min_level"] = "practitioner"
        errors = variants.validate_agent(
            "designer", agent, CAPABILITIES, ROLES, matrix=MATRIX
        )
        self.assertTrue(any("rol matrisi" in item for item in errors))

    def test_unknown_handoff(self) -> None:
        agent = copy.deepcopy(variants.load_agent("tester"))
        agent["handoffs"].append("unknown-role")
        errors = variants.validate_agent("tester", agent, CAPABILITIES, ROLES)
        self.assertTrue(any("bilinmeyen handoff" in item for item in errors))

    def test_extra_variant(self) -> None:
        agent = copy.deepcopy(variants.load_agent("designer"))
        agent["variants"]["platform.api"] = {
            "doc": "variants/web.md",
            "eval": "evals/web.md",
            "min_level": "expert",
        }
        errors = variants.validate_agent("designer", agent, CAPABILITIES, ROLES)
        self.assertTrue(any("fazla variant" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
