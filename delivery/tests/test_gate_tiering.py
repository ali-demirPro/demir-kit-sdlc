"""Tests for gate tiering (fast at CP, full at leaf close)."""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("gate_t", SCRIPTS / "gate.py")
gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gate)

spec_c = importlib.util.spec_from_file_location("cp_close_t", SCRIPTS / "cp_close.py")
cp_close = importlib.util.module_from_spec(spec_c)
assert spec_c.loader is not None
spec_c.loader.exec_module(cp_close)


class FastGateTests(unittest.TestCase):
    def run_plan(self, *extra: str) -> str:
        with tempfile.TemporaryDirectory() as directory:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                gate.main(
                    [
                        "--plan",
                        "--changed",
                        "delivery/tests/test_gate.py",
                        "--checkpoint",
                        "CP-1",
                        "--project",
                        directory,
                        *extra,
                    ]
                )
        return buffer.getvalue()

    def test_fast_runs_only_doctor(self) -> None:
        text = self.run_plan("--fast")
        self.assertIn("level fast", text)
        self.assertIn("plan doctor", text)
        self.assertNotIn("unittest", text)

    def test_full_runs_the_suites(self) -> None:
        text = self.run_plan()
        self.assertIn("level full", text)
        self.assertIn("unittest", text)

    def test_cp_close_command_carries_the_level(self) -> None:
        self.assertIn("--fast", cp_close.gate_command(231, "CP-1", "fast"))
        self.assertNotIn("--fast", cp_close.gate_command(231, "CP-1", "full"))


if __name__ == "__main__":
    unittest.main()
