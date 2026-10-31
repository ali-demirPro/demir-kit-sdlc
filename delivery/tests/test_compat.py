"""Tests for the kit ↔ Orca schema compatibility map."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("compat", SCRIPTS / "compat.py")
compat = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(compat)


def cmd(name: str, flags: list[str]) -> dict:
    return {"command": name, "flags": flags}


class CompatTests(unittest.TestCase):
    def test_empty_schema_reports_missing_commands(self) -> None:
        issues = compat.check(schema={"commands": []})
        self.assertTrue(any("komut yok" in item for item in issues))
        self.assertGreaterEqual(len(issues), len(compat.REQUIRED))

    def test_missing_flag_reported(self) -> None:
        schema = {
            "commands": [
                cmd(name, list(flags)) for name, flags in compat.REQUIRED.items()
            ]
        }
        schema["commands"] = [
            item for item in schema["commands"] if item["command"] != "worktree set"
        ] + [cmd("worktree set", ["comment"])]
        issues = compat.check(schema=schema)
        self.assertTrue(any("worktree set" in item and "eksik flag" in item for item in issues))

    def test_full_schema_passes(self) -> None:
        schema = {
            "commands": [
                cmd(name, list(flags)) for name, flags in compat.REQUIRED.items()
            ]
        }
        self.assertEqual(compat.check(schema=schema), [])


if __name__ == "__main__":
    unittest.main()
