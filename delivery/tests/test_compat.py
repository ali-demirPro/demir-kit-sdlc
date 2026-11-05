"""Tests for the kit ↔ Orca schema compatibility map."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("compat", SCRIPTS / "compat.py")
compat = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(compat)

doctor_spec = importlib.util.spec_from_file_location(
    "doctor_compat", SCRIPTS / "doctor_compat.py"
)
doctor_compat = importlib.util.module_from_spec(doctor_spec)
assert doctor_spec.loader is not None
doctor_spec.loader.exec_module(doctor_compat)


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


def fake_runner(payloads: dict[str, dict]):
    def run(command: str, extra: list[str] | None = None) -> dict:
        return payloads[command]

    return run


class ShapeTests(unittest.TestCase):
    def test_run_shape_drift(self) -> None:
        issues = compat.check_shapes(
            lambda command, extra=None: {"result": {"foo": 1}}
        )
        self.assertTrue(any("run-current" in item for item in issues), issues)
        self.assertTrue(all("yanıt şekli" in item for item in issues), issues)

    def test_run_accepts_flat_and_nested(self) -> None:
        flat = fake_runner(
            {
                "orchestration run-current": {"result": {"runId": "run_x"}},
                "orchestration run-list": {"result": {"runs": []}},
                "orchestration task-list": {"result": {"tasks": []}},
            }
        )
        nested = fake_runner(
            {
                "orchestration run-current": {
                    "result": {"run": {"id": "run_x"}}
                },
                "orchestration run-list": {"result": {"runs": []}},
                "orchestration task-list": {"result": {"tasks": []}},
            }
        )
        self.assertEqual(compat.check_shapes(flat), [])
        self.assertEqual(compat.check_shapes(nested), [])

    def test_run_list_and_task_list(self) -> None:
        valid = fake_runner(
            {
                "orchestration run-current": {"result": {"runId": "run_x"}},
                "orchestration run-list": {"result": {"runs": [{"id": "run_x"}]}},
                "orchestration task-list": {"result": {"tasks": [], "runId": "run_x"}},
            }
        )
        self.assertEqual(compat.check_shapes(valid), [])
        drifted = fake_runner(
            {
                "orchestration run-current": {"result": {"runId": "run_x"}},
                "orchestration run-list": {"result": {"runs": {"id": "run_x"}}},
                "orchestration task-list": {"result": {"tasks": {}}},
            }
        )
        issues = compat.check_shapes(drifted)
        self.assertTrue(any("run-list" in item for item in issues), issues)
        self.assertTrue(any("task-list" in item for item in issues), issues)

    def test_missing_orca_skips(self) -> None:
        def missing(command: str, extra: list[str] | None = None) -> dict:
            raise OSError("orca yok")

        self.assertEqual(compat.check_shapes(missing), [])

    def test_no_bound_run_is_not_drift(self) -> None:
        payloads = [
            {"result": {"runId": None}},
            {"result": {"run": None}},
            {"result": None},
            {"ok": False},
            {"ok": False, "result": None},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):

                def runner(command, extra=None, payload=payload):
                    if command == "orchestration run-current":
                        return payload
                    return {"result": {"runs": []}}

                self.assertEqual(compat.check_shapes(runner), [])

    def test_partial_drift_survives_later_probe_failure(self) -> None:
        def list_drift(command, extra=None):
            if command == "orchestration run-current":
                return {"result": {"runId": "run_x"}}
            if command == "orchestration run-list":
                return {"result": {"runs": {}}}
            raise OSError("task-list yok")

        issues = compat.check_shapes(list_drift)
        self.assertTrue(any("run-list" in item for item in issues), issues)

        def current_drift(command, extra=None):
            if command == "orchestration run-current":
                return {"result": {"foo": 1}}
            raise OSError("kalan problar yok")

        issues = compat.check_shapes(current_drift)
        self.assertTrue(any("run-current" in item for item in issues), issues)


class DoctorCompatTests(unittest.TestCase):
    def test_drift_reaches_doctor_errors(self) -> None:
        errors: list[str] = []
        calls: list[str] = []
        drift = "orca orchestration run-list: yanıt şekli — drift"
        with mock.patch.object(
            doctor_compat.compat, "check", return_value=[]
        ), mock.patch.object(
            doctor_compat.compat, "check_shapes", return_value=[drift]
        ), mock.patch.object(
            doctor_compat.compat.orca_capabilities,
            "load_schema",
            return_value={"commands": []},
        ):
            doctor_compat.check_compat(Path("/tmp"), errors.append, calls.append)
        self.assertEqual(calls, ["compat"])
        self.assertEqual(errors, [drift])

    def test_unreadable_schema_skips_quietly(self) -> None:
        errors: list[str] = []
        calls: list[str] = []
        with mock.patch.object(
            doctor_compat.compat.orca_capabilities,
            "load_schema",
            side_effect=OSError("çevrimdışı"),
        ):
            doctor_compat.check_compat(Path("/tmp"), errors.append, calls.append)
        self.assertEqual(calls, ["compat"])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
