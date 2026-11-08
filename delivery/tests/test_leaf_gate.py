"""Tests for CP fast / leaf full gate wiring."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("transition_gate", SCRIPTS / "transition.py")
transition = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(transition)

spec_c = importlib.util.spec_from_file_location("cp_close_gate", SCRIPTS / "cp_close.py")
cp_close = importlib.util.module_from_spec(spec_c)
assert spec_c.loader is not None
spec_c.loader.exec_module(cp_close)


def issue_with(checkpoints: list[str]) -> dict:
    seal = {
        "demir_kit_version": "2",
        "checkpoints": [{"id": cp, "title": "t", "gates": {"behavior": True}} for cp in checkpoints],
    }
    body = "```yaml demir-kit\n" + yaml.safe_dump(seal, sort_keys=False) + "```\n"
    return {"body": body}


class LeafGateTests(unittest.TestCase):
    def test_last_checkpoint(self) -> None:
        self.assertEqual(transition.last_checkpoint(issue_with(["CP-1", "CP-2"])), "CP-2")
        self.assertIsNone(transition.last_checkpoint({"body": ""}))

    def test_leaf_gate_command_is_full(self) -> None:
        command = transition.leaf_gate_command(ROOT, 251, "CP-1")
        self.assertIn("gate.sh --issue 251 --checkpoint CP-1", command)
        self.assertNotIn("--fast", command)

    def test_gate_can_be_disabled(self) -> None:
        self.assertTrue(transition.leaf_gate_enabled())
        with mock.patch.dict(os.environ, {"DEMIR_KIT_LEAF_GATE": "off"}):
            self.assertFalse(transition.leaf_gate_enabled())

    def test_cp_close_defaults_to_fast(self) -> None:
        self.assertEqual(cp_close.DEFAULT_GATE_LEVEL, "fast")
        self.assertIn("--fast", cp_close.gate_command(251, "CP-1"))
        self.assertNotIn("--fast", cp_close.gate_command(251, "CP-1", "full"))


if __name__ == "__main__":
    unittest.main()
