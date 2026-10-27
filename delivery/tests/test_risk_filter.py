"""Tests for risk-glob path filtering."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("risk_filter", SCRIPTS / "risk_filter.py")
risk_filter = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(risk_filter)


class RiskFilterTests(unittest.TestCase):
    def test_registry_risk_classification(self) -> None:
        registry = {
            "risk": {
                "auto_escalate": {
                    "critical": ["**/store/**", "**/release/**"],
                    "high": ["**/auth/**", "**/payments/**"],
                }
            }
        }
        self.assertEqual(
            risk_filter.risk_for_paths(["src/auth/login.ts"], registry), "high"
        )
        self.assertEqual(
            risk_filter.risk_for_paths(["store/metadata.json"], registry), "critical"
        )
        self.assertEqual(
            risk_filter.risk_for_paths(["auth/login.ts"], registry), "high"
        )
        self.assertEqual(
            risk_filter.risk_for_paths(["src/web/page.ts"], registry), "none"
        )
    def test_agent_and_docs_are_excluded(self) -> None:
        paths = [
            "delivery/agents/security/ROLE.md",
            "delivery/capabilities/registry.yaml",
            "delivery/tests/test_x.py",
            "README.md",
        ]
        excluded = [
            "delivery/agents/**",
            "delivery/capabilities/**",
            "delivery/tests/**",
            "*.md",
            "**/*.md",
        ]
        self.assertEqual(risk_filter.filter_paths(paths, excluded), [])

    def test_code_paths_are_kept(self) -> None:
        paths = [
            "src/auth/login.ts",
            "infra/security/policy.yaml",
            "delivery/scripts/guard.sh",
        ]
        self.assertEqual(
            risk_filter.filter_paths(paths, ["delivery/agents/**"]),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
