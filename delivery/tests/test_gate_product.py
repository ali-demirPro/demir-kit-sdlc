"""Tests for the product behavior gate."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("gate_product", SCRIPTS / "gate.py")
gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gate)

ECOSYSTEM = """
name: ornek
products:
  app:
    surfaces:
      ios:
        path: .
        stacks: [swift]
        platforms: [ios]
        gates:
          behavior: ./scripts/gate-behavior.sh {checkpoint}
          ui: false
"""

SELF = """
name: kit
products:
  kit:
    surfaces:
      kit.docs:
        path: delivery
        stacks: [markdown]
        platforms: [any]
        gates:
          behavior: ./delivery/scripts/gate.sh --checkpoint {checkpoint}
"""


class ProductBehaviorTests(unittest.TestCase):
    def test_product_command_is_returned_with_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "ecosystem.yaml").write_text(ECOSYSTEM, encoding="utf-8")
            commands = gate.product_behavior(project, "CP-2")
        self.assertEqual(commands, ["./scripts/gate-behavior.sh CP-2"])

    def test_self_reference_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "ecosystem.yaml").write_text(SELF, encoding="utf-8")
            self.assertEqual(gate.product_behavior(project, "CP-1"), [])

    def test_kit_root_is_skipped(self) -> None:
        self.assertEqual(gate.product_behavior(ROOT, "CP-1"), [])

    def test_missing_ecosystem_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(gate.product_behavior(Path(directory), "CP-1"), [])

    def test_plan_lists_the_product_command(self) -> None:
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "ecosystem.yaml").write_text(ECOSYSTEM, encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                gate.main(
                    ["--plan", "--checkpoint", "CP-1", "--project", directory]
                )
        self.assertIn("plan behavior", buffer.getvalue())
        self.assertIn("gate-behavior.sh CP-1", buffer.getvalue())

    def test_behavior_command_runs_through_the_shell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            marker = project / "ran.txt"
            code = gate._run(f"printf ok > {marker}", project, shell=True)
            self.assertEqual(code, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), "ok")

    def test_behavior_command_returns_its_own_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code = gate._run("exit 7", Path(directory), shell=True)
        self.assertEqual(code, 7)

    def test_main_runs_the_product_command_through_a_shell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "ecosystem.yaml").write_text(ECOSYSTEM, encoding="utf-8")
            scripts = project / "scripts"
            scripts.mkdir()
            script = scripts / "gate-behavior.sh"
            script.write_text("#!/bin/sh\nprintf ok > ran.txt\n", encoding="utf-8")
            script.chmod(0o755)
            with patch.object(gate, "step_command", return_value=["true"]):
                code = gate.main(["--checkpoint", "CP-1", "--project", directory])
            self.assertEqual(code, 0)
            self.assertEqual(
                (project / "ran.txt").read_text(encoding="utf-8"), "ok"
            )

    def test_invalid_checkpoint_is_rejected_before_the_shell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit) as raised:
                gate.main(
                    ["--checkpoint", "CP-1; touch pwned", "--project", directory]
                )
        self.assertNotEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
