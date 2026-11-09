"""Autonomy policy contract tests (delivery/policies/autonomy.md)."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "delivery" / "policies" / "autonomy.md"


class AutonomyPolicyTests(unittest.TestCase):
    def test_policy_is_registered(self) -> None:
        registry = yaml.safe_load(
            (ROOT / "delivery" / "registry.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            (registry.get("policies") or {}).get("autonomy"),
            "delivery/policies/autonomy.md",
        )
        self.assertTrue(POLICY.is_file())

    def test_contract_links_policy(self) -> None:
        contract = (ROOT / "delivery" / "CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("policies/autonomy.md", contract)

    def test_policy_defines_the_delegated_lane(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        for heading in (
            "## Eşikler",
            "## Durma koşulları",
            "## Delegated kabul sınırı",
            "## Dönüş özeti",
        ):
            self.assertIn(heading, text)
        self.assertIn("delegated: coordinator", text)
        self.assertIn("kabulü insanda kalır", text)


if __name__ == "__main__":
    unittest.main()
