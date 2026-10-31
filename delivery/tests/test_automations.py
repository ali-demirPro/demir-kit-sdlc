"""Tests for Orca automation templates."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("automations", SCRIPTS / "automations.py")
automations = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(automations)


class AutomationTests(unittest.TestCase):
    def test_templates_exist(self) -> None:
        names = {path.stem for path in automations.TEMPLATES.glob("*.y*ml")}
        self.assertIn("stale-lease", names)
        self.assertIn("weekly-doctor", names)
        self.assertIn("pr-queue", names)
        self.assertIn("weekly-report", names)

    def test_create_is_disabled_by_default(self) -> None:
        command = automations.create_command(
            {
                "name": "t",
                "trigger": "daily",
                "prompt": "p",
                "provider": "opencode2",
            },
            enable=False,
        )
        self.assertIn("--disabled", command)
        self.assertNotIn("--enabled", command)

    def test_enable_removes_disabled(self) -> None:
        command = automations.create_command(
            {
                "name": "t",
                "trigger": "daily",
                "prompt": "p",
                "provider": "opencode2",
            },
            enable=True,
        )
        self.assertNotIn("--disabled", command)

    def test_missing_field_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            automations.create_command({"name": "t"}, enable=False)

    def test_template_loads_and_is_disabled(self) -> None:
        template = automations.load_template("stale-lease")
        self.assertEqual(template["provider"], "opencode2")
        command = automations.create_command(template, enable=False)
        self.assertIn("--precheck", command)


if __name__ == "__main__":
    unittest.main()
