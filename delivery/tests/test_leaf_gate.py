"""Tests for CP fast / leaf full gate wiring."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
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

    def test_leaf_gate_command_is_an_argument_list(self) -> None:
        command = transition.leaf_gate_command(ROOT, 251, "CP-1")
        self.assertIsInstance(command, list)
        self.assertEqual(command[-4:], ["--issue", "251", "--checkpoint", "CP-1"])
        self.assertTrue(command[0].endswith("gate.sh"))
        self.assertNotIn("--fast", command)

    def test_checkpoint_id_is_validated_before_the_command(self) -> None:
        with self.assertRaises(ValueError):
            transition.leaf_gate_command(ROOT, 251, "CP-1; rm -rf /")

    def test_disabled_gate_writes_a_degrade_note(self) -> None:
        note = transition.leaf_gate_degrade_note(251)
        self.assertIn("run degrade: issue #251", note)
        self.assertIn("DEMIR_KIT_LEAF_GATE=off", note)

    def test_gate_can_be_disabled(self) -> None:
        self.assertTrue(transition.leaf_gate_enabled())
        with mock.patch.dict(os.environ, {"DEMIR_KIT_LEAF_GATE": "off"}):
            self.assertFalse(transition.leaf_gate_enabled())

    def test_cp_close_defaults_to_fast(self) -> None:
        self.assertEqual(cp_close.DEFAULT_GATE_LEVEL, "fast")
        self.assertIn("--fast", cp_close.gate_command(251, "CP-1"))
        self.assertNotIn("--fast", cp_close.gate_command(251, "CP-1", "full"))

class CloseLeafGateTests(unittest.TestCase):
    def args(self, **overrides) -> argparse.Namespace:
        base = argparse.Namespace(issue=251, no_gate=False, reason="")
        base.__dict__.update(overrides)
        return base

    def issue(self, checkpoint: str = "CP-1") -> dict:
        issue = issue_with([checkpoint])
        issue["labels"] = [{"name": "executing"}]
        return issue

    def test_disabled_gate_posts_degrade_note(self) -> None:
        with mock.patch.dict(os.environ, {"DEMIR_KIT_LEAF_GATE": "off"}), \
             mock.patch.object(transition, "post_comment") as post, \
             mock.patch.object(transition.subprocess, "run") as run:
            transition.close_leaf_gate(self.issue(), self.args())
        post.assert_called_once()
        self.assertIn("run degrade: issue #251", post.call_args[0][1])
        self.assertIn("DEMIR_KIT_LEAF_GATE=off", post.call_args[0][1])
        run.assert_not_called()

    def test_enabled_gate_runs_argv_without_shell(self) -> None:
        done = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.dict(os.environ, {"DEMIR_KIT_LEAF_GATE": "on"}), \
             mock.patch.object(
                 transition, "run_gate_in_orca", return_value=(None, "")
             ), \
             mock.patch.object(transition.subprocess, "run", return_value=done) as run:
            transition.close_leaf_gate(self.issue(), self.args())
        command = run.call_args[0][0]
        self.assertIsInstance(command, list)
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_gate_runs_in_orca_terminal_and_reads_exit_file(self) -> None:
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def fake_run(command, **kwargs):
                calls.append(command)
                if command[1:3] == ["terminal", "create"]:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout=json.dumps(
                            {"ok": True, "result": {"terminal": {"handle": "term_x"}}}
                        ),
                        stderr="",
                    )
                if command[1:3] == ["terminal", "wait"]:
                    (root / "gate.log").write_text("gate ok\n", encoding="utf-8")
                    (root / "gate.exit").write_text("0", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with mock.patch.object(
                transition.shutil, "which", return_value="/usr/bin/orca"
            ), mock.patch.object(
                transition.subprocess, "run", side_effect=fake_run
            ):
                code, output = transition.run_gate_in_orca(
                    ROOT, ["true"], root=root
                )
        self.assertEqual(code, 0)
        self.assertIn("gate ok", output)
        self.assertEqual(calls[0][:3], ["orca", "terminal", "create"])
        self.assertEqual(calls[1][:3], ["orca", "terminal", "wait"])

    def test_missing_orca_falls_back_to_a_direct_run(self) -> None:
        with mock.patch.object(transition.shutil, "which", return_value=None):
            self.assertEqual(
                transition.run_gate_in_orca(ROOT, ["true"]), (None, "")
            )

    def test_created_terminal_without_result_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            def fake_run(command, **kwargs):
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps(
                        {"ok": True, "result": {"terminal": {"handle": "term_x"}}}
                    ),
                    stderr="",
                )

            with mock.patch.object(
                transition.shutil, "which", return_value="/usr/bin/orca"
            ), mock.patch.object(
                transition.subprocess, "run", side_effect=fake_run
            ):
                code, output = transition.run_gate_in_orca(
                    ROOT, ["true"], root=Path(directory)
                )
        self.assertEqual(code, 1)
        self.assertTrue(output)

    def test_invalid_checkpoint_is_rejected_even_when_gate_is_off(self) -> None:
        with mock.patch.dict(os.environ, {"DEMIR_KIT_LEAF_GATE": "off"}):
            ok, message = transition.validate(
                self.issue("CP-1; rm -rf /"), "leaf-done", self.args()
            )
        self.assertFalse(ok)
        self.assertIn("geçersiz checkpoint", message)


if __name__ == "__main__":
    unittest.main()
