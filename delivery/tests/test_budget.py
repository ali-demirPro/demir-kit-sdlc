"""Tests for the heavy-work budget."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("budget", SCRIPTS / "budget.py")
budget = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(budget)

spec_w = importlib.util.spec_from_file_location("orca_wave_b", SCRIPTS / "orca_wave.py")
wave = importlib.util.module_from_spec(spec_w)
assert spec_w.loader is not None
spec_w.loader.exec_module(wave)


class LoadTests(unittest.TestCase):
    def test_missing_resources_means_no_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "ecosystem.yaml").write_text("name: x\n", encoding="utf-8")
            data = budget.load(project)
        self.assertIsNone(data["heavy_workers"])
        self.assertIsNone(data["simulators"])

    def test_resources_are_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "ecosystem.yaml").write_text(
                "name: x\nresources:\n  heavy_workers: 2\n  simulators: 1\n",
                encoding="utf-8",
            )
            data = budget.load(project)
        self.assertEqual(data["heavy_workers"], 2)
        self.assertEqual(data["simulators"], 1)

    def test_invalid_values_fall_back_to_no_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "ecosystem.yaml").write_text(
                "name: x\nresources:\n  heavy_workers: 0\n", encoding="utf-8"
            )
            data = budget.load(project)
        self.assertIsNone(data["heavy_workers"])


class WaveChunkTests(unittest.TestCase):
    def tasks(self, count: int) -> list[dict]:
        return [{"id": f"t{index}", "deps": []} for index in range(count)]

    def test_waves_are_chunked_to_the_budget(self) -> None:
        waves = wave.topological_waves(self.tasks(5), max_parallel=2)
        self.assertEqual([len(item) for item in waves], [2, 2, 1])
        self.assertEqual(waves[0], ["t0", "t1"])
        self.assertEqual(waves[2], ["t4"])

    def test_no_budget_keeps_one_wave(self) -> None:
        waves = wave.topological_waves(self.tasks(5))
        self.assertEqual([len(item) for item in waves], [5])

    def test_dependencies_still_hold_between_chunks(self) -> None:
        tasks = [
            {"id": "a", "deps": []},
            {"id": "b", "deps": []},
            {"id": "c", "deps": ["task:a"]},
        ]
        waves = wave.topological_waves(tasks, max_parallel=1)
        self.assertEqual(waves, [["a"], ["b"], ["c"]])


if __name__ == "__main__":
    unittest.main()
