"""Tests for context miss/over-read metrics and the leaf-done record."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, file_name: str | None = None):
    spec = importlib.util.spec_from_file_location(
        name, SCRIPTS / (file_name or f"{name}.py")
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


context_metrics = load("context_metrics")
transition = load("transition_metrics_test", "transition.py")


def write_usage(root: Path, issue: int, tokens: dict) -> Path:
    directory = root / ".kit"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"usage-{issue}.json"
    path.write_text(json.dumps({"issue": issue, "tokens": tokens}), encoding="utf-8")
    return path


def write_doc(root: Path, name: str, size: int) -> Path:
    path = root / name
    path.write_bytes(b"x" * size)
    return path


class RateTests(unittest.TestCase):
    def test_miss_and_over_read_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_usage(
                root,
                314,
                {
                    "input": 100,
                    "output": 100,
                    "reasoning": 50,
                    "cache": {"read": 50, "write": 0},
                },
            )
            extra = write_doc(root, "extra.md", 400)  # 100 tokens
            unused = write_doc(root, "unused.md", 200)  # 50 tokens
            brief = [write_doc(root, f"brief-{index}.md", 40) for index in range(3)]
            row = context_metrics.build_row(
                314,
                "CP-1",
                brief_docs=brief,
                unused_brief_docs=[unused],
                extra_docs=[extra],
                missed_docs=["missed.md"],
                root=root,
            )
        self.assertEqual(row["tokens"], 300)
        self.assertEqual(row["miss_rate"], 0.25)  # 1 / (3 + 1)
        self.assertEqual(row["over_read_rate"], 0.5)  # (100 + 50) / 300
        self.assertFalse(row["clamped"])
        self.assertEqual(context_metrics.miss_rate(["a", "b"], ["c"]), 0.3333)

    def test_zero_denominator_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = context_metrics.build_row(
                314, "CP-1", tokens=0, root=root
            )
            self.assertEqual(row["tokens"], "unknown")
            self.assertEqual(row["miss_rate"], "unknown")
            self.assertEqual(row["over_read_rate"], "unknown")

            empty = context_metrics.build_row(
                314, "CP-1", tokens=100, root=root
            )
            self.assertEqual(empty["miss_rate"], "unknown")
            self.assertEqual(empty["over_read_rate"], 0.0)

            missing = context_metrics.build_row(
                314,
                "CP-1",
                extra_docs=["does-not-exist.md"],
                tokens=100,
                root=root,
            )
            self.assertEqual(missing["over_read_rate"], "unknown")
            self.assertIn("doc-missing:does-not-exist.md", missing["method"])


class RecordTests(unittest.TestCase):
    def test_record_line_and_transition_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_usage(root, 314, {"input": 100, "output": 0, "reasoning": 0})
            row, line = context_metrics.record(
                314,
                "CP-1",
                brief_docs=["delivery/policies/context-budget.md"],
                tokens=100,
                root=root,
            )
            path = root / ".kit" / "context-metrics.jsonl"
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_text(encoding="utf-8"), line + "\n")
            self.assertEqual(json.loads(line), row)
            self.assertTrue(context_metrics.check(314, root)[0])
            ok, message = context_metrics.check(999, root)
            self.assertFalse(ok)
            self.assertEqual(message, "uyari: context-metrics satiri yok")

        stderr = io.StringIO()
        with patch.object(
            transition.context_metrics,
            "check",
            return_value=(False, "uyari: context-metrics satiri yok"),
        ):
            with contextlib.redirect_stderr(stderr):
                transition.warn_context_metrics(999)
        self.assertIn("uyari: context-metrics satiri yok", stderr.getvalue())

        stdout = io.StringIO()
        with patch.object(
            transition.context_metrics, "check", return_value=(True, "var")
        ):
            with contextlib.redirect_stderr(stdout):
                transition.warn_context_metrics(314)
        self.assertEqual(stdout.getvalue(), "")


class FixtureTests(unittest.TestCase):
    scenarios = {
        "clean": {
            "brief": 2,
            "unused": 0,
            "extra": 0,
            "missed": 0,
            "tokens": 200,
            "miss_rate": 0.0,
            "over_read_rate": 0.0,
        },
        "miss": {
            "brief": 3,
            "unused": 0,
            "extra": 0,
            "missed": 1,
            "tokens": 200,
            "miss_rate": 0.25,
            "over_read_rate": 0.0,
        },
        "over-read": {
            "brief": 0,
            "unused": 1,
            "extra": 1,
            "missed": 0,
            "tokens": 300,
            "miss_rate": "unknown",
            "over_read_rate": 0.5,
        },
    }

    def test_clean_miss_over_read_are_deterministic(self) -> None:
        for name, spec in self.scenarios.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_usage(
                    root,
                    314,
                    {"input": spec["tokens"], "output": 0, "reasoning": 0},
                )
                brief = [
                    write_doc(root, f"{name}-brief-{index}.md", 40)
                    for index in range(spec["brief"])
                ]
                unused = [
                    write_doc(root, f"{name}-unused-{index}.md", 200)
                    for index in range(spec["unused"])
                ]
                extra = [
                    write_doc(root, f"{name}-extra-{index}.md", 400)
                    for index in range(spec["extra"])
                ]
                missed = [f"{name}-missed-{index}.md" for index in range(spec["missed"])]
                first, first_line = context_metrics.record(
                    314,
                    "CP-1",
                    brief_docs=brief,
                    unused_brief_docs=unused,
                    extra_docs=extra,
                    missed_docs=missed,
                    root=root,
                    write=False,
                )
                second, second_line = context_metrics.record(
                    314,
                    "CP-1",
                    brief_docs=brief,
                    unused_brief_docs=unused,
                    extra_docs=extra,
                    missed_docs=missed,
                    root=root,
                    write=False,
                )
                self.assertEqual(first, second)
                self.assertEqual(first_line, second_line)
                self.assertEqual(first["miss_rate"], spec["miss_rate"])
                self.assertEqual(first["over_read_rate"], spec["over_read_rate"])


if __name__ == "__main__":
    unittest.main()
