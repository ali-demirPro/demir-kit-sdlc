"""Tests for Orca feature detection (no version comparison)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "orca_capabilities", SCRIPTS / "orca_capabilities.py"
)
orca_capabilities = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(orca_capabilities)

SCHEMA = {
    "schemaVersion": 1,
    "commands": [
        {
            "command": "worktree set",
            "flags": ["issue", "pr", "comment", "workspace-status", "unread", "json"],
        },
        {
            "command": "orchestration worker-start",
            "flags": ["task", "spec", "worktree", "agent", "model", "effort", "json"],
        },
    ],
}


def fake_run(stdout: str, code: int = 0):
    return types.SimpleNamespace(returncode=code, stdout=stdout, stderr="")


class CapabilityTests(unittest.TestCase):
    def test_has_and_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                orca_capabilities,
                "run",
                return_value=fake_run(json.dumps(SCHEMA)),
            ):
                schema = orca_capabilities.load_schema(root, refresh=True)
            self.assertTrue(orca_capabilities.has("worktree set", root, schema))
            self.assertIn(
                "workspace-status",
                orca_capabilities.flags("worktree set", root, schema),
            )
            self.assertFalse(
                orca_capabilities.has("orchestration gate-create", root, schema)
            )

    def test_require_reports_missing_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                orca_capabilities,
                "run",
                return_value=fake_run(json.dumps(SCHEMA)),
            ):
                schema = orca_capabilities.load_schema(root, refresh=True)
            item = orca_capabilities.require(
                "orchestration worker-start", ("task", "model"), root, schema
            )
            self.assertEqual(item["command"], "orchestration worker-start")
            with self.assertRaises(orca_capabilities.OrcaCapabilityError):
                orca_capabilities.require(
                    "orchestration worker-start", ("gate",), root, schema
                )

    def test_cache_avoids_second_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []

            def fake(args, cwd):
                calls.append(args)
                return fake_run(json.dumps(SCHEMA))

            with patch.object(orca_capabilities, "run", side_effect=fake):
                orca_capabilities.load_schema(root, refresh=True)
                orca_capabilities.load_schema(root)
            self.assertEqual(len(calls), 1)
            self.assertTrue(
                (root / ".orchestration" / "orca-schema.json").is_file()
            )

    def test_missing_orca_is_a_capability_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                orca_capabilities, "run", side_effect=FileNotFoundError()
            ):
                with self.assertRaises(orca_capabilities.OrcaCapabilityError):
                    orca_capabilities.load_schema(root, refresh=True)


if __name__ == "__main__":
    unittest.main()
