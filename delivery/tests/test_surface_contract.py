"""Surface contract and ui-gate unchanged tests (issue #126).

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"

spec = importlib.util.spec_from_file_location("doctor", SCRIPTS / "doctor.py")
doctor = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(doctor)

TEMPLATE = ROOT / "delivery" / "templates" / "ecosystem-macos.yaml"
UI_GATE = ROOT / "skills" / "ui-gate" / "SKILL.md"
HEALTH = ROOT / "delivery" / "protocol" / "health-check.md"


class SurfaceGateTest(unittest.TestCase):
    def test_ui_surface_requires_snapshot(self) -> None:
        errors = doctor.surface_gate_errors(
            "app",
            "macos.app",
            {"gates": {"behavior": "./build.sh", "ui": True}},
        )
        self.assertTrue(any("snapshot" in item for item in errors), errors)

    def test_ui_surface_with_snapshot_passes(self) -> None:
        errors = doctor.surface_gate_errors(
            "app",
            "macos.app",
            {
                "gates": {
                    "behavior": "./build.sh",
                    "ui": True,
                    "snapshot": "./tools/snap.sh",
                }
            },
        )
        self.assertEqual(errors, [])

    def test_non_ui_surface_does_not_require_snapshot(self) -> None:
        errors = doctor.surface_gate_errors(
            "kit", "kit.docs", {"gates": {"behavior": "./doctor.sh", "ui": False}}
        )
        self.assertEqual(errors, [])

    def test_missing_behavior_is_an_error(self) -> None:
        errors = doctor.surface_gate_errors("app", "macos.app", {"gates": {}})
        self.assertTrue(any("behavior" in item for item in errors), errors)

    def test_snapshot_must_be_string(self) -> None:
        errors = doctor.surface_gate_errors(
            "app",
            "macos.app",
            {"gates": {"behavior": "./build.sh", "snapshot": ["x"]}},
        )
        self.assertTrue(any("string" in item for item in errors), errors)

    def test_ui_must_be_boolean(self) -> None:
        errors = doctor.surface_gate_errors(
            "app", "macos.app", {"gates": {"behavior": "./b", "ui": "true"}}
        )
        self.assertTrue(any("ui boolean" in item for item in errors), errors)

    def test_snapshot_pages_must_be_list(self) -> None:
        errors = doctor.surface_gate_errors(
            "app",
            "macos.app",
            {"gates": {"behavior": "./build.sh", "snapshot_pages": "main"}},
        )
        self.assertTrue(any("liste" in item for item in errors), errors)


class EcosystemWiringTest(unittest.TestCase):
    def test_check_ecosystem_reports_missing_snapshot(self) -> None:
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "ecosystem.yaml").write_text(
                "name: T\n"
                "products:\n"
                "  app:\n"
                "    surfaces:\n"
                "      macos.app:\n"
                "        path: .\n"
                "        gates: { behavior: './build.sh', ui: true }\n",
                encoding="utf-8",
            )
            (root / "kit.config.yaml").write_text(
                "kit:\n  protocol: '2'\n", encoding="utf-8"
            )
            doctor.ERRORS.clear()
            with patch.object(doctor, "ROOT", root):
                doctor.check_ecosystem()
        self.assertTrue(
            any("snapshot" in item for item in doctor.ERRORS), doctor.ERRORS
        )


class TemplatesAndDocsTest(unittest.TestCase):
    def test_macos_template_has_all_three_commands(self) -> None:
        data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
        surface = data["products"]["app"]["surfaces"]["macos.app"]
        gates = surface["gates"]
        for key in ("behavior", "selftest", "snapshot"):
            self.assertTrue(gates.get(key), key)
        self.assertIsInstance(gates.get("snapshot_pages"), list)
        self.assertEqual(doctor.surface_gate_errors("app", "macos.app", surface), [])

    def test_health_check_mentions_selftest_and_snapshot(self) -> None:
        text = HEALTH.read_text(encoding="utf-8")
        self.assertIn("gates.snapshot", text)
        self.assertIn("gates.selftest", text)

    def test_ui_gate_documents_unchanged_mode(self) -> None:
        text = UI_GATE.read_text(encoding="utf-8")
        self.assertIn("unchanged", text)
        self.assertIn("entry.kind: refactor", text)
        self.assertIn("comparison_valid", text)


if __name__ == "__main__":
    unittest.main()
