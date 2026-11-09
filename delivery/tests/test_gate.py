"""Tests for the checkpoint gate (doctor + suites the changes require)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


gate = load("gate")
cp_close = load("cp_close")


def plan(*changed: str) -> subprocess.CompletedProcess:
    command = [
        "bash",
        "delivery/scripts/gate.sh",
        "--plan",
        "--checkpoint",
        "CP-1",
    ]
    for path in changed:
        command += ["--changed", path]
    return subprocess.run(
        command, cwd=str(ROOT), capture_output=True, text=True
    )


class PlanTests(unittest.TestCase):
    def test_suites_for_paths(self) -> None:
        self.assertEqual(
            gate.suites_for(["delivery/tests/test_gate.py"], ROOT),
            ["unittest:delivery.tests.test_gate"],
        )
        self.assertEqual(
            gate.suites_for(["delivery/tests/test_gate.py"], ROOT, full=True),
            ["unittest"],
        )
        self.assertEqual(gate.suites_for(["plugins/orca/index.ts"], ROOT), ["plugin"])
        self.assertEqual(
            gate.suites_for(
                ["plugins/orca/index.ts", "delivery/tests/test_gate.py"], ROOT
            ),
            ["unittest:delivery.tests.test_gate", "plugin"],
        )
        self.assertEqual(gate.suites_for(["README.md"], ROOT), [])

    def test_script_selects_the_tests_that_name_it(self) -> None:
        modules = gate.selected_test_modules(["delivery/scripts/gate.py"], ROOT)
        self.assertIn("delivery.tests.test_gate", modules)
        self.assertIn("delivery.tests.test_gate_tiering", modules)
        self.assertNotIn("delivery.tests.test_handoff", modules)

    def test_config_selects_the_tests_that_mention_it(self) -> None:
        modules = gate.selected_test_modules(
            ["delivery/schemas/evidence.schema.json"], ROOT
        )
        self.assertTrue(any("evidence" in module for module in modules))

    def test_deleted_test_file_is_not_selected(self) -> None:
        modules = gate.selected_test_modules(
            ["delivery/tests/test_worker_reaper.py"], ROOT
        )
        self.assertNotIn("delivery.tests.test_worker_reaper", modules)

    def test_plan_lists_steps(self) -> None:
        result = plan("delivery/tests/test_gate.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("doctor", result.stdout)
        self.assertIn("unittest:delivery.tests.test_gate", result.stdout)
        self.assertNotIn("Ran ", result.stdout)
        self.assertNotIn(" exit ", result.stdout)

    def test_plan_without_tests(self) -> None:
        result = plan("README.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("doctor", result.stdout)
        self.assertNotIn("unittest", result.stdout)
        self.assertNotIn(" exit ", result.stdout)

    def test_changed_requires_plan(self) -> None:
        result = subprocess.run(
            [
                "bash",
                "delivery/scripts/gate.sh",
                "--issue",
                "208",
                "--checkpoint",
                "CP-1",
                "--changed",
                "README.md",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--changed yalnız --plan", result.stderr)

    def test_plan_warns_missing_changed_path(self) -> None:
        result = plan("missing/no-such-file.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("uyarı", result.stderr)
        self.assertIn("doctor", result.stdout)

    def test_cp_close_uses_gate(self) -> None:
        command = cp_close.gate_command(208, "CP-1")
        self.assertIn("gate.sh", command)
        self.assertIn("--issue 208", command)
        self.assertIn("--checkpoint CP-1", command)

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                cp_close.routing, "project_root", return_value=Path(directory)
            ), patch.object(cp_close.routing, "kit_prefix", return_value=""):
                fallback = cp_close.gate_command(208, "CP-1")
        self.assertIn("doctor.sh", fallback)
        self.assertNotIn("gate.sh", fallback)

    def test_cp_close_uses_gate_with_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            kit = Path(directory) / "demir-kit"
            script = kit / "delivery" / "scripts" / "gate.sh"
            script.parent.mkdir(parents=True)
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            with patch.object(
                cp_close.routing, "project_root", return_value=Path(directory)
            ), patch.object(
                cp_close.routing, "kit_prefix", return_value="demir-kit/"
            ):
                command = cp_close.gate_command(208, "CP-1")
                self.assertIn(
                    "./demir-kit/delivery/scripts/gate.sh --issue 208 "
                    "--checkpoint CP-1",
                    command,
                )

                script.unlink()
                fallback = cp_close.gate_command(208, "CP-1")
        self.assertIn("doctor.sh", fallback)
        self.assertIn("--product --root .", fallback)


if __name__ == "__main__":
    unittest.main()
