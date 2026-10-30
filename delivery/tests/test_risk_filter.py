"""Tests for risk-glob path filtering."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
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
    def test_overlay_extends_registry_globs(self) -> None:
        registry = {
            "risk": {
                "auto_escalate": {
                    "critical": ["**/store/**"],
                    "high": ["**/auth/**"],
                }
            }
        }
        overlay = {
            "auto_escalate": {
                "high": ["RenderKit/Core/**", "**/auth/**"],
                "critical": ["**/Signing/**"],
            }
        }
        merged = risk_filter.merge_risk(registry, overlay)
        escalate = merged["risk"]["auto_escalate"]
        self.assertEqual(escalate["high"], ["**/auth/**", "RenderKit/Core/**"])
        self.assertEqual(escalate["critical"], ["**/store/**", "**/Signing/**"])
        self.assertEqual(
            risk_filter.risk_for_paths(["RenderKit/Core/Node.swift"], merged), "high"
        )
        self.assertEqual(
            risk_filter.risk_for_paths(["Signing/identity.swift"], merged), "critical"
        )
        # orijinal registry değişmez (ekleme sınıfı)
        self.assertEqual(registry["risk"]["auto_escalate"]["high"], ["**/auth/**"])

    def test_load_overlay_from_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".kit").mkdir()
            (root / ".kit" / "risk.yaml").write_text(
                "auto_escalate:\n  high: ['RenderKit/**']\n", encoding="utf-8"
            )
            overlay = risk_filter.load_overlay(root)
            self.assertEqual(overlay["auto_escalate"]["high"], ["RenderKit/**"])
            self.assertEqual(risk_filter.load_overlay(root / "missing"), {})

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
