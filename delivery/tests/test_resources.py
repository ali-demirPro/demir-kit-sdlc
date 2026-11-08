"""Tests for the machine budget guard."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("resources", SCRIPTS / "resources.py")
resources = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(resources)

HEALTHY = {
    "free_ram_mb": 4200,
    "compressor_mb": 300,
    "load1": 1.2,
    "cpus": 8,
    "booted_simulators": 0,
    "heavy_workers": 0,
}


def metrics(**changes):
    data = dict(HEALTHY)
    data.update(changes)
    return data


class EvaluateTests(unittest.TestCase):
    def test_healthy_machine_passes(self) -> None:
        result = resources.evaluate(metrics())
        self.assertEqual(result["state"], 0)
        self.assertEqual(result["reasons"], [])

    def test_low_memory_degrades_then_blocks(self) -> None:
        self.assertEqual(resources.evaluate(metrics(free_ram_mb=1200))["state"], 2)
        blocked = resources.evaluate(metrics(free_ram_mb=400))
        self.assertEqual(blocked["state"], 3)
        self.assertTrue(any("RAM" in reason for reason in blocked["reasons"]))

    def test_compressor_and_load_have_two_levels(self) -> None:
        self.assertEqual(resources.evaluate(metrics(compressor_mb=2000))["state"], 2)
        self.assertEqual(resources.evaluate(metrics(compressor_mb=3500))["state"], 3)
        self.assertEqual(resources.evaluate(metrics(load1=13.0))["state"], 2)
        self.assertEqual(resources.evaluate(metrics(load1=21.0))["state"], 3)

    def test_simulator_and_worker_budget_blocks(self) -> None:
        self.assertEqual(resources.evaluate(metrics(booted_simulators=2))["state"], 3)
        self.assertEqual(resources.evaluate(metrics(heavy_workers=3))["state"], 3)

    def test_limits_override_merges_with_defaults(self) -> None:
        self.assertEqual(resources.evaluate(metrics(free_ram_mb=1800))["state"], 0)
        raised = resources.evaluate(
            metrics(free_ram_mb=1800), {"free_ram_warn_mb": 2000}
        )
        self.assertEqual(raised["state"], 2)
        self.assertEqual(raised["limits"]["free_ram_block_mb"], 800)

    def test_unmeasured_memory_is_reported_separately(self) -> None:
        result = resources.evaluate(metrics(free_ram_mb=0, vm_measured=False))
        self.assertEqual(result["state"], 3)
        self.assertTrue(any("ölçülemedi" in reason for reason in result["reasons"]))
        self.assertFalse(any("dolu" in reason for reason in result["reasons"]))

    def test_reasons_are_short_turkish_lines(self) -> None:
        result = resources.evaluate(metrics(free_ram_mb=200))
        self.assertTrue(result["reasons"])
        for reason in result["reasons"]:
            self.assertIsInstance(reason, str)
            self.assertGreater(len(reason), 5)


class LogTests(unittest.TestCase):
    def test_record_appends_one_line_without_personal_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            result = resources.evaluate(metrics(free_ram_mb=200))
            resources.record(project, result)
            path = project / ".kit" / "resources.jsonl"
            self.assertTrue(path.is_file())
            row = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual(row["state"], 3)
            self.assertIn("metrics", row)
            self.assertIn("ts", row)
            self.assertNotIn("title", row)
            self.assertNotIn("command", row)


class CliTests(unittest.TestCase):
    def test_json_output_reports_state_and_metrics(self) -> None:
        payload = json.dumps(metrics(free_ram_mb=200))
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "resources.py"), "--json", "--no-log",
             "--metrics", payload],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["state"], 3)
        self.assertEqual(data["metrics"]["free_ram_mb"], 200)

    def test_healthy_machine_exits_zero(self) -> None:
        payload = json.dumps(metrics())
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "resources.py"), "--json", "--no-log",
             "--metrics", payload],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
