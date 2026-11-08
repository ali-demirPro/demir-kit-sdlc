"""Tests for gate level in evidence and the cycle log."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("cp_close_level", SCRIPTS / "cp_close.py")
cp_close = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cp_close)


class LevelTests(unittest.TestCase):
    def test_default_level_is_fast(self) -> None:
        self.assertEqual(cp_close.DEFAULT_GATE_LEVEL, "fast")

    def test_evidence_schema_accepts_gate_level(self) -> None:
        import json

        schema = json.loads((ROOT / "delivery" / "schemas" / "evidence.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["gate_level"]["enum"], ["fast", "full"])

    def test_gate_reason_carries_the_level(self) -> None:
        source = (SCRIPTS / "gate.py").read_text(encoding="utf-8")
        self.assertIn("'fast' if args.fast else 'full'", source)


if __name__ == "__main__":
    unittest.main()
