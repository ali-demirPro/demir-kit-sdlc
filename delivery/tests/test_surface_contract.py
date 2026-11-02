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
    def test_ui_surface_requires_snapshot_when_comparison_declared(self) -> None:
        errors = doctor.surface_gate_errors(
            "app",
            "macos.app",
            {
                "gates": {
                    "behavior": "./build.sh",
                    "ui": True,
                    "ui_compare": "screenshot",
                }
            },
        )
        self.assertTrue(any("snapshot" in item for item in errors), errors)

    def test_ui_surface_without_comparison_warns_only(self) -> None:
        spec = {"gates": {"behavior": "./build.sh", "ui": True}}
        errors = doctor.surface_gate_errors("app", "macos.app", spec)
        warnings = doctor.surface_gate_warnings("app", "macos.app", spec)
        self.assertEqual(errors, [])
        self.assertTrue(any("ui_compare" in item for item in warnings), warnings)

    def test_valid_waiver_turns_error_into_warning(self) -> None:
        from datetime import date

        spec = {
            "gates": {
                "behavior": "./build.sh",
                "ui": True,
                "ui_compare": "screenshot",
                "ui_waiver": {
                    "reason": "snapshot aracı hazırlanıyor",
                    "until": "2026-12-15",
                    "issue": 7,
                },
            }
        }
        today = date(2026, 11, 2)
        self.assertEqual(
            doctor.surface_gate_errors("app", "macos.app", spec, today=today), []
        )
        warnings = doctor.surface_gate_warnings("app", "macos.app", spec, today=today)
        self.assertTrue(any("muafiyeti" in item for item in warnings), warnings)

    def test_expired_waiver_is_an_error(self) -> None:
        from datetime import date

        spec = {
            "gates": {
                "behavior": "./build.sh",
                "ui": True,
                "ui_compare": "screenshot",
                "ui_waiver": {
                    "reason": "geçici",
                    "until": "2026-10-01",
                    "issue": 7,
                },
            }
        }
        errors = doctor.surface_gate_errors(
            "app", "macos.app", spec, today=date(2026, 11, 2)
        )
        self.assertTrue(any("süresi doldu" in item for item in errors), errors)

    def test_waiver_requires_a_positive_issue(self) -> None:
        for issue in (None, "7", True, 0, -1):
            with self.subTest(issue=issue):
                waiver = {"reason": "x", "until": "2026-12-01"}
                if issue is not None:
                    waiver["issue"] = issue
                spec = {
                    "gates": {
                        "behavior": "./b",
                        "ui": True,
                        "ui_compare": "screenshot",
                        "ui_waiver": waiver,
                    }
                }
                errors = doctor.surface_gate_errors("app", "macos.app", spec)
                self.assertTrue(any("ui_waiver" in item for item in errors), errors)

    def test_waiver_horizon_is_capped(self) -> None:
        from datetime import date

        spec = {
            "gates": {
                "behavior": "./b",
                "ui": True,
                "ui_compare": "screenshot",
                "ui_waiver": {
                    "reason": "sonsuz",
                    "until": "9999-12-31",
                    "issue": 1,
                },
            }
        }
        errors = doctor.surface_gate_errors(
            "app", "macos.app", spec, today=date(2026, 11, 2)
        )
        self.assertTrue(any("en fazla" in item for item in errors), errors)

    def test_expired_waiver_is_an_error_even_with_snapshot(self) -> None:
        from datetime import date

        spec = {
            "gates": {
                "behavior": "./b",
                "ui": True,
                "ui_compare": "screenshot",
                "snapshot": "./snap.sh",
                "ui_waiver": {
                    "reason": "eski",
                    "until": "2026-10-01",
                    "issue": 1,
                },
            }
        }
        errors = doctor.surface_gate_errors(
            "app", "macos.app", spec, today=date(2026, 11, 2)
        )
        self.assertTrue(any("süresi doldu" in item for item in errors), errors)

    def test_stale_waiver_next_to_snapshot_warns(self) -> None:
        from datetime import date

        spec = {
            "gates": {
                "behavior": "./b",
                "ui": True,
                "ui_compare": "screenshot",
                "snapshot": "./snap.sh",
                "ui_waiver": {
                    "reason": "artık gereksiz",
                    "until": "2026-12-01",
                    "issue": 1,
                },
            }
        }
        warnings = doctor.surface_gate_warnings(
            "app", "macos.app", spec, today=date(2026, 11, 2)
        )
        self.assertTrue(any("gereksiz" in item for item in warnings), warnings)

    def test_waiver_boundary_is_inclusive(self) -> None:
        from datetime import date

        spec = {
            "gates": {
                "behavior": "./b",
                "ui": True,
                "ui_compare": "screenshot",
                "ui_waiver": {
                    "reason": "bugün bitiyor",
                    "until": "2026-11-02",
                    "issue": 1,
                },
            }
        }
        today = date(2026, 11, 2)
        self.assertEqual(
            doctor.surface_gate_errors("app", "macos.app", spec, today=today), []
        )
        errors = doctor.surface_gate_errors(
            "app", "macos.app", spec, today=date(2026, 11, 3)
        )
        self.assertTrue(any("süresi doldu" in item for item in errors), errors)

    def test_malformed_waiver_is_an_error(self) -> None:
        for waiver in (
            "geçici",
            {"reason": "x"},
            {"reason": "x", "until": "2026-13-01", "issue": 1},
            {"reason": "", "until": "2026-12-01", "issue": 1},
        ):
            with self.subTest(waiver=waiver):
                spec = {
                    "gates": {
                        "behavior": "./build.sh",
                        "ui": True,
                        "ui_compare": "screenshot",
                        "ui_waiver": waiver,
                    }
                }
                errors = doctor.surface_gate_errors("app", "macos.app", spec)
                self.assertTrue(any("ui_waiver" in item for item in errors), errors)

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
                "        gates: { behavior: './build.sh', ui: true, ui_compare: screenshot }\n",
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
