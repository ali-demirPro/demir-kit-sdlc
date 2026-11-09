"""Tests for context miss/over-read metrics and the leaf-done record."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import threading
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


def write_snapshot(root: Path, issue: int, session_id: str, tokens: dict) -> Path:
    directory = root / ".orchestration"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"usage-{issue}.json"
    path.write_text(
        json.dumps(
            {
                "issue": issue,
                "session_id": session_id,
                "cost": 0,
                "tokens": tokens,
                "time": {"created": 0, "updated": 1000},
                "created_at": "2026-11-09T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
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
            self.assertTrue(context_metrics.check(314, "CP-1", root)[0])
            self.assertTrue(context_metrics.check(314, root=root)[0])
            ok, message = context_metrics.check(314, "CP-2", root)
            self.assertFalse(ok)
            self.assertEqual(message, "uyari: context-metrics satiri yok")
            ok, message = context_metrics.check(999, root=root)
            self.assertFalse(ok)
            self.assertEqual(message, "uyari: context-metrics satiri yok")

        stderr = io.StringIO()
        with patch.object(
            transition.context_metrics,
            "check",
            return_value=(False, "uyari: context-metrics satiri yok"),
        ) as check:
            with contextlib.redirect_stderr(stderr):
                transition.warn_context_metrics(999, "CP-1")
        check.assert_called_once_with(999, "CP-1")
        self.assertIn("uyari: context-metrics satiri yok", stderr.getvalue())

        stdout = io.StringIO()
        with patch.object(
            transition.context_metrics, "check", return_value=(True, "var")
        ):
            with contextlib.redirect_stderr(stdout):
                transition.warn_context_metrics(314)
        self.assertEqual(stdout.getvalue(), "")

    def test_issue_only_fallback_is_labelled(self) -> None:
        stderr = io.StringIO()
        with patch.object(
            transition.context_metrics,
            "check",
            return_value=(False, "uyari: context-metrics satiri yok"),
        ):
            with contextlib.redirect_stderr(stderr):
                transition.warn_context_metrics(999)
        self.assertIn("uyari: context-metrics satiri yok", stderr.getvalue())
        self.assertIn("checkpoint bilinmiyor", stderr.getvalue())

    def test_known_checkpoint_scopes_the_metrics_check(self) -> None:
        body = (
            "```yaml demir-kit\n"
            "demir_kit_version: '2'\n"
            "checkpoints:\n"
            "  - id: CP-2\n"
            "```\n"
        )
        self.assertEqual(transition.metrics_cp(None, {"body": body}), "CP-2")
        self.assertEqual(transition.metrics_cp("CP-1", {"body": body}), "CP-1")
        self.assertIsNone(transition.metrics_cp(None, {"body": ""}))


class ConcurrencyTests(unittest.TestCase):
    """Two writers serialize on the lock instead of dropping rows."""

    def test_two_threads_keep_both_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            barrier = threading.Barrier(2)
            errors: list[BaseException] = []

            def writer(issue: int) -> None:
                try:
                    barrier.wait(timeout=5)
                    context_metrics.record(
                        issue,
                        "CP-1",
                        brief_docs=[f"{issue}.md"],
                        tokens=100,
                        root=root,
                    )
                except BaseException as exc:  # noqa: BLE001 - surfaced below
                    errors.append(exc)

            threads = [
                threading.Thread(target=writer, args=(issue,))
                for issue in (400, 401)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            path = root / ".kit" / "context-metrics.jsonl"
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(errors, [])
        rows = [json.loads(raw) for raw in raw_lines]
        self.assertEqual(sorted(row["issue"] for row in rows), [400, 401])


class BriefMetaTests(unittest.TestCase):
    """Machine metadata the CP brief writes, and the row it derives."""

    def write_meta(
        self,
        root: Path,
        issue: int,
        cp: str,
        armed: list[str],
        fallbacks: list[str],
        selected_docs: list[str],
        unarmed: list[str] | None = None,
    ) -> Path:
        return self.write_raw_meta(
            root,
            issue,
            cp,
            {
                "armed": armed,
                "unarmed": unarmed if unarmed is not None else [],
                "fallbacks": fallbacks,
                "selected_docs": selected_docs,
            },
        )

    def write_raw_meta(
        self,
        root: Path,
        issue: int,
        cp: str,
        payload: dict,
    ) -> Path:
        path = context_metrics.brief_meta_path(issue, cp, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"issue": issue, "cp": cp, **payload}),
            encoding="utf-8",
        )
        return path

    def test_record_from_brief_derives_armed_and_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_usage(root, 321, {"input": 100, "output": 0, "reasoning": 0})
            docs = [
                "delivery/scripts/brief.py",
                "delivery/scripts/context_metrics.py",
            ]
            self.write_meta(
                root,
                321,
                "CP-1",
                ["path pure_technical", "cp CP-1"],
                ["ecosystem yok", "index yok"],
                docs,
                ["route tuketilmedi"],
            )
            result = context_metrics.record_from_brief(321, "CP-1", root)
        self.assertIsNotNone(result)
        row, line = result
        self.assertEqual(row["armed"], True)
        self.assertEqual(row["fallback_count"], 2)
        self.assertEqual(row["selected_docs"], docs)
        self.assertEqual(row["brief_docs"], [])
        self.assertEqual(row["tokens"], 100)
        self.assertEqual(row["miss_rate"], "unknown")
        self.assertEqual(row["over_read_rate"], "unknown")
        self.assertIn("split:unknown", row["method"])
        self.assertEqual(json.loads(line), row)

    def test_non_list_metadata_is_ignored(self) -> None:
        cases = (
            {"armed": "no"},
            {"fallbacks": "index yok"},
            {"selected_docs": "a.md"},
            {"unarmed": "route tuketilmedi"},
        )
        for bad in cases:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                payload = {
                    "armed": [],
                    "unarmed": [],
                    "fallbacks": [],
                    "selected_docs": [],
                    **bad,
                }
                self.write_raw_meta(root, 321, "CP-1", payload)
                self.assertIsNone(
                    context_metrics.read_brief_meta(321, "CP-1", root)
                )
                self.assertIsNone(
                    context_metrics.record_from_brief(321, "CP-1", root)
                )

    def test_missing_metadata_is_unknown_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = context_metrics.build_row(321, "CP-1", tokens=100, root=root)
            self.assertEqual(row["armed"], "unknown")
            self.assertEqual(row["fallback_count"], "unknown")
            with patch.object(
                context_metrics,
                "session_delta",
                side_effect=ValueError("no snapshot"),
            ):
                self.assertIsNone(
                    context_metrics.record_from_brief(321, "CP-1", root)
                )

    def test_present_meta_without_keys_is_unknown_not_false_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = context_metrics.build_row(
                321,
                "CP-1",
                tokens=100,
                brief_meta={"issue": 321, "cp": "CP-1"},
                root=root,
            )
        self.assertEqual(row["armed"], "unknown")
        self.assertEqual(row["fallback_count"], "unknown")

    def test_present_keys_keep_their_meaning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = context_metrics.build_row(
                321,
                "CP-1",
                tokens=100,
                brief_meta={"issue": 321, "cp": "CP-1", "armed": [], "fallbacks": []},
                root=root,
            )
        self.assertEqual(row["armed"], False)
        self.assertEqual(row["fallback_count"], 0)

    def test_non_list_armed_and_fallbacks_are_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = context_metrics.build_row(
                321,
                "CP-1",
                tokens=100,
                brief_meta={
                    "issue": 321,
                    "cp": "CP-1",
                    "armed": "no",
                    "fallbacks": None,
                },
                root=root,
            )
        self.assertEqual(row["armed"], "unknown")
        self.assertEqual(row["fallback_count"], "unknown")

    def test_invalid_utf8_brief_meta_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = context_metrics.brief_meta_path(321, "CP-1", root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'{"issue": 321, "cp": "CP-1", "armed": "\xff\xfe"}')
            self.assertIsNone(context_metrics.read_brief_meta(321, "CP-1", root))
            self.assertIsNone(
                context_metrics.record_from_brief(321, "CP-1", root)
            )

    def test_mismatched_metadata_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_meta(root, 321, "CP-2", ["cp CP-2"], [], ["a.md"])
            self.assertIsNone(
                context_metrics.read_brief_meta(321, "CP-1", root)
            )

    def test_same_issue_and_cp_keeps_one_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".kit" / "context-metrics.jsonl"
            context_metrics.record(
                321, "CP-1", brief_docs=["a.md"], tokens=100, root=root
            )
            path.write_text(
                path.read_text(encoding="utf-8") + "bozuk satir\n",
                encoding="utf-8",
            )
            context_metrics.record(
                321, "CP-1", brief_docs=["b.md"], tokens=200, root=root
            )
            context_metrics.record(
                321, "CP-2", brief_docs=["c.md"], tokens=300, root=root
            )
            self.assertFalse(
                (path.parent / "context-metrics.jsonl.tmp").exists()
            )
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(raw_lines[0], "bozuk satir")
        rows = [json.loads(raw) for raw in raw_lines[1:]]
        self.assertEqual(
            [(row["issue"], row["cp"]) for row in rows],
            [(321, "CP-1"), (321, "CP-2")],
        )
        self.assertEqual(rows[0]["brief_docs"], ["b.md"])
        self.assertEqual(rows[1]["brief_docs"], ["c.md"])

    def test_invalid_utf8_metrics_file_is_preserved_and_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".kit" / "context-metrics.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            original = b"\xff\xfe bozuk\n"
            path.write_bytes(original)
            with self.assertRaises(context_metrics.ContextMetricsError):
                context_metrics.record(
                    321, "CP-1", brief_docs=["a.md"], tokens=100, root=root
                )
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(
                (path.parent / "context-metrics.jsonl.tmp").exists()
            )

            meta = context_metrics.brief_meta_path(321, "CP-1", root)
            meta.write_text(
                json.dumps(
                    {"issue": 321, "cp": "CP-1", "selected_docs": ["a.md"]}
                ),
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertIsNone(
                    context_metrics.record_from_brief(321, "CP-1", root)
                )
            self.assertIn(
                "uyari: context-metrics okunamadi; satir yazilmadi",
                stderr.getvalue(),
            )
            self.assertEqual(path.read_bytes(), original)

    def test_cli_record_reports_read_error_and_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".kit" / "context-metrics.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            original = b"\xff\xfe bozuk\n"
            path.write_bytes(original)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = context_metrics.main(
                    [
                        "--project",
                        str(root),
                        "record",
                        "--issue",
                        "321",
                        "--cp",
                        "CP-1",
                        "--tokens",
                        "100",
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("context-metrics:", stderr.getvalue())
            self.assertEqual(path.read_bytes(), original)


class TokenTests(unittest.TestCase):
    def test_dot_kit_delta_wins_over_session_delta(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_usage(root, 314, {"input": 300, "output": 0, "reasoning": 0})
            with patch.object(
                context_metrics,
                "session_delta",
                side_effect=AssertionError("session delta okunmamali"),
            ):
                row = context_metrics.build_row(314, "CP-1", root=root)
        self.assertEqual(row["tokens"], 300)
        self.assertTrue(row["method"].startswith("tokens:usage-delta:"))
        self.assertIn(".kit/usage-314.json", row["method"])

    def test_session_delta_is_called_when_dot_kit_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delta = {
                "tokens": {
                    "input": 120,
                    "output": 30,
                    "reasoning": 0,
                    "cache_read": 50,
                    "cache_write": 0,
                }
            }
            with patch.object(context_metrics, "session_delta", return_value=delta):
                row = context_metrics.build_row(314, "CP-1", root=root)
        self.assertEqual(row["tokens"], 200)
        self.assertEqual(row["method"], "tokens:usage-delta:session")

    def test_session_delta_reads_the_given_root(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            other = Path(first)
            root = Path(second)
            write_snapshot(other, 314, "ses_root", {"input": 10})
            write_snapshot(root, 314, "ses_root", {"input": 100})
            current = {
                "id": "ses_root",
                "cost": 0,
                "tokens": {"input": 150},
                "time": {"created": 0, "updated": 2000},
            }
            with patch.object(
                context_metrics.usage, "project_root", return_value=other
            ), patch.object(
                context_metrics.usage, "api_session_info", return_value=current
            ):
                row = context_metrics.build_row(314, "CP-1", root=root)
        self.assertEqual(row["tokens"], 50)  # root delta, not other/.orchestration
        self.assertEqual(row["method"], "tokens:usage-delta:session")

    def test_no_delta_source_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                context_metrics.usage, "session_delta", side_effect=ValueError("no snapshot")
            ):
                row = context_metrics.build_row(314, "CP-1", root=root)
        self.assertEqual(row["tokens"], "unknown")
        self.assertEqual(row["method"], "tokens:unknown")
        self.assertEqual(row["over_read_rate"], "unknown")

    def test_explicit_snapshot_file_is_labelled_total(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".orchestration").mkdir()
            snapshot = root / ".orchestration" / "usage-314.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "issue": 314,
                        "session_id": "ses_test",
                        "cost": 0,
                        "tokens": {"input": 400},
                        "time": {"updated": 0},
                        "created_at": "2026-11-09T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            row = context_metrics.build_row(
                314,
                "CP-1",
                usage_file=snapshot,
                root=root,
            )
        self.assertEqual(row["tokens"], 400)
        self.assertTrue(row["method"].startswith("tokens:usage-total:"))


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
