"""Tests for the Orca worktree/run gate."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("orca_gate", SCRIPTS / "orca_gate.py")
orca_gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(orca_gate)


def leaf_body(epic: int | None = 15) -> str:
    seal = {"demir_kit_version": "2", "package_version": 3, "epic": epic}
    return "```yaml demir-kit\n" + yaml.safe_dump(seal, sort_keys=False) + "```\n"


class OrcaGateTests(unittest.TestCase):
    def test_disabled_config_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text("orca:\n  epic_worktree: false\n")
            result = orca_gate.evaluate(root, {"body": leaf_body()})
            self.assertTrue(result["ok"])
            self.assertEqual(result["mode"], "disabled")

    def test_missing_orca_without_record_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text("orca:\n  epic_worktree: true\n")
            with patch.object(
                orca_gate.epic_worktree, "orca_available", return_value=False
            ):
                result = orca_gate.evaluate(
                    root, {"number": 15, "body": leaf_body()}
                )
            self.assertFalse(result["ok"])
            self.assertIn("degrade", result["reason"])

    def test_missing_orca_with_record_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text("orca:\n  epic_worktree: true\n")
            state = root / ".orchestration" / "degrade-15.json"
            state.parent.mkdir()
            state.write_text('{"reason": "Orca kapalı"}', encoding="utf-8")
            with patch.object(
                orca_gate.epic_worktree, "orca_available", return_value=False
            ):
                result = orca_gate.evaluate(
                    root, {"number": 15, "body": leaf_body()}
                )
            self.assertTrue(result["ok"])
            self.assertEqual(result["mode"], "degrade")

    def test_wrong_worktree_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text("orca:\n  epic_worktree: true\n")
            with patch.object(
                orca_gate.epic_worktree, "orca_available", return_value=True
            ), patch.object(
                orca_gate.epic_worktree,
                "check",
                side_effect=orca_gate.epic_worktree.WorktreeError("ana checkout"),
            ):
                result = orca_gate.evaluate(root, {"body": leaf_body()})
            self.assertFalse(result["ok"])
            self.assertIn("ana checkout", result["reason"])

    def test_missing_run_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text("orca:\n  epic_worktree: true\n")
            with patch.object(
                orca_gate.epic_worktree, "orca_available", return_value=True
            ), patch.object(
                orca_gate.epic_worktree,
                "check",
                return_value={"ok": True, "run_id": None},
            ):
                result = orca_gate.evaluate(root, {"body": leaf_body()})
            self.assertFalse(result["ok"])
            self.assertIn("run yok", result["reason"])

    def test_missing_task_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text("orca:\n  epic_worktree: true\n")
            with patch.object(
                orca_gate.epic_worktree, "orca_available", return_value=True
            ), patch.object(
                orca_gate.epic_worktree,
                "check",
                return_value={"ok": True, "run_id": "run_x"},
            ), patch.object(orca_gate, "task_count", return_value=0):
                result = orca_gate.evaluate(root, {"body": leaf_body()})
            self.assertFalse(result["ok"])
            self.assertIn("task yok", result["reason"])

    def test_valid_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text("orca:\n  epic_worktree: true\n")
            with patch.object(
                orca_gate.epic_worktree, "orca_available", return_value=True
            ), patch.object(
                orca_gate.epic_worktree,
                "check",
                return_value={"ok": True, "run_id": "run_x", "path": "/tmp/epic-15"},
            ), patch.object(orca_gate, "task_count", return_value=1):
                result = orca_gate.evaluate(root, {"body": leaf_body()})
            self.assertTrue(result["ok"])
            self.assertEqual(result["run_id"], "run_x")

    def test_record_degrade_writes_comment_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text(
                "tracker:\n  repo: owner/repo\norca:\n  epic_worktree: true\n"
            )
            calls = []

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            def fake_run(args, **kwargs):
                calls.append(args)
                return Result()

            with patch.object(orca_gate.subprocess, "run", side_effect=fake_run):
                result = orca_gate.record_degrade(root, 15, "Orca kapalı")
            self.assertTrue(result["ok"])
            self.assertTrue(
                any("run degrade: issue" in " ".join(map(str, item)) for item in calls)
            )
            self.assertTrue(
                (root / ".orchestration" / "degrade-15.json").is_file()
            )

    def test_ask_rejects_out_of_range_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError):
                orca_gate.ask(root, "soru?", timeout_ms=1_800_001)

    def test_send_builds_group_message(self) -> None:
        captured = {}

        def fake(project, args):
            captured["args"] = args
            return {"ok": True}

        with patch.object(orca_gate, "orca_action", side_effect=fake):
            orca_gate.send(Path("/tmp"), "@idle", "Mola", "Kısa mola", "status")
        self.assertIn("--to", captured["args"])
        self.assertIn("@idle", captured["args"])
        self.assertIn("--subject", captured["args"])

    def test_gate_create_passes_options_json(self) -> None:
        captured = {}

        def fake(project, args):
            captured["args"] = args
            return {"ok": True}

        with patch.object(orca_gate, "orca_action", side_effect=fake):
            orca_gate.gate_create(Path("/tmp"), "task_1", "Onay?", ["approve", "revise"])
        self.assertIn("--task", captured["args"])
        self.assertIn('["approve", "revise"]', captured["args"])


if __name__ == "__main__":
    unittest.main()
