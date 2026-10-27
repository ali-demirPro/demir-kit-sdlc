"""Tests for eval scenario enforcement."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("eval", SCRIPTS / "eval.py")
eval_mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(eval_mod)


def write_eval(root: Path, rows: list[str]) -> Path:
    path = root / "eval.md"
    path.write_text(
        "| ID | Senaryo | Beklenen | Fail |\n"
        "|----|---------|----------|------|\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    return path


class EvalTests(unittest.TestCase):
    def test_real_evals_pass(self) -> None:
        self.assertEqual(eval_mod.check_all(), [])

    def test_too_few_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_eval(
                Path(directory),
                ["| X-1 | a | b | c |", "| X-2 | a | b | c |"],
            )
            errors = eval_mod.check_eval_file(path)
            self.assertTrue(any("en az 10" in item for item in errors))

    def test_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rows = [f"| X-1 | a | b | c |" for _ in range(10)]
            path = write_eval(Path(directory), rows)
            errors = eval_mod.check_eval_file(path)
            self.assertTrue(any("tekrarlı" in item for item in errors))

    def test_results_require_all_ids(self) -> None:
        errors = eval_mod.validate_results(
            {"results": [{"id": "A", "result": "pass"}]}, ["A", "B"]
        )
        self.assertTrue(any("eksik sonuç" in item for item in errors))

    def test_results_fail_and_skip(self) -> None:
        errors = eval_mod.validate_results(
            {"results": [{"id": "A", "result": "fail"}]}, ["A"]
        )
        self.assertTrue(any("A: fail" in item for item in errors))
        errors = eval_mod.validate_results(
            {"results": [{"id": "A", "result": "skip"}]}, ["A"]
        )
        self.assertTrue(any("A: skip" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
