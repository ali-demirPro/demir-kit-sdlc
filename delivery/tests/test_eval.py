"""Tests for eval scenario enforcement and finding records."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
SCHEMAS = ROOT / "delivery" / "schemas"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("eval", SCRIPTS / "eval.py")
eval_mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(eval_mod)

from schema_lite import validate_schema  # noqa: E402


def finding_schema() -> dict:
    return json.loads((SCHEMAS / "finding.schema.json").read_text(encoding="utf-8"))


def finding(**overrides) -> dict:
    record = {
        "demir_kit_version": "2",
        "id": "FND-1",
        "kind": "FRICTION",
        "basis": "OBSERVED",
        "effect": "EXTRA_WORK",
        "cause": "PRODUCT",
        "label": "Eksik kurulum adımı",
        "detail": "Agent kurulum adımını bulamadı ve kendisi tamamladı.",
        "evidence": [{"kind": "trace", "seq": 7}],
    }
    record.update(overrides)
    return record


def write_finding(root: Path, record: dict, name: str = "FND-1.finding.yaml") -> Path:
    path = root / name
    path.write_text(
        yaml.safe_dump(record, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


# Fixture: kanıt yetersiz olduğu için etki ve neden UNKNOWN kalır.
FIXTURE_UNKNOWN_EVIDENCE = finding(
    id="FND-UNKNOWN",
    basis="INFERRED",
    effect="UNKNOWN",
    cause="UNKNOWN",
    label="Okuma erişimi belirsiz",
    detail="Oturum kaydında sayfanın okunup okunmadığını gösteren iz yok.",
    evidence=[{"kind": "artifact", "artifact": "session/events.ndjson", "line": 2}],
)


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


def write_case(
    root: Path, frontmatter: dict, body: str = "Case istemi.", name: str = "case.md"
) -> Path:
    path = root / name
    path.write_text(
        "---\n"
        + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
        + "---\n"
        + body
        + "\n",
        encoding="utf-8",
    )
    return path


def case_record(**overrides) -> dict:
    record = {
        "id": "case-1",
        "intent": "Case sözleşmesini doğrula",
        "criteria": ["Dosya değişir", "Testler yeşil"],
        "targets": ["delivery/scripts/eval.py"],
        "tools": ["python3"],
        "inputs": ["delivery/scripts/eval.py"],
    }
    record.update(overrides)
    return record


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


class CaseContractTests(unittest.TestCase):
    def test_legacy_table_format_still_parses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_eval(
                Path(directory),
                [f"| X-{index} | senaryo | beklenen | fail |" for index in range(1, 11)],
            )
            rows = eval_mod.parse_eval(path)
            self.assertEqual(len(rows), 10)
            self.assertEqual(rows[0]["id"], "X-1")
            self.assertEqual(eval_mod.check_eval_file(path), [])

    def test_frontmatter_fields_are_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(Path(directory), case_record())
            case = eval_mod.parse_case(path)
            self.assertEqual(case["id"], "case-1")
            self.assertEqual(case["intent"], "Case sözleşmesini doğrula")
            self.assertEqual(len(case["criteria"]), 2)
            self.assertEqual(case["targets"], ["delivery/scripts/eval.py"])
            self.assertTrue(case["body"].startswith("Case istemi."))

    def test_missing_required_field_exits_one(self) -> None:
        record = case_record()
        record.pop("criteria")
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(Path(directory), record)
            errors = eval_mod.check_case_file(path)
            self.assertTrue(any("criteria" in item for item in errors))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(eval_mod.main(["--check", str(path)]), 1)

    def test_valid_case_passes_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(Path(directory), case_record())
            self.assertEqual(eval_mod.check_case_file(path), [])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(eval_mod.main(["--check", str(path)]), 0)


class EvalModeTests(unittest.TestCase):
    def test_verify_reports_yes_no_and_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            valid = write_case(
                Path(directory),
                case_record(targets=["delivery/scripts/eval.py"], tools=[]),
                name="valid.md",
            )
            result = eval_mod.verify_case(valid)
            self.assertEqual(result["status"], "passed")
            self.assertGreaterEqual(result["summary"]["yes"], 1)
            self.assertEqual(result["summary"]["no"], 0)

            unresolved = write_case(
                Path(directory),
                case_record(
                    targets=["${{ env.TARGET }}"],
                    tools=[],
                    inputs=[],
                ),
                name="unresolved.md",
            )
            result = eval_mod.verify_case(unresolved)
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(result["summary"]["no"], 0)
            self.assertGreaterEqual(result["summary"]["unknown"], 1)

            missing = write_case(
                Path(directory),
                case_record(targets=["delivery/does-not-exist.md"], tools=[], inputs=[]),
                name="missing.md",
            )
            result = eval_mod.verify_case(missing)
            self.assertEqual(result["status"], "failed")
            self.assertGreaterEqual(result["summary"]["no"], 1)

    def test_verify_unresolved_input_stays_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(
                Path(directory),
                case_record(
                    targets=["delivery/scripts/eval.py"],
                    tools=[],
                    inputs=["${{ env.INPUT }}"],
                ),
            )
            result = eval_mod.verify_case(path)
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(result["summary"]["no"], 0)
            self.assertGreaterEqual(result["summary"]["unknown"], 1)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(eval_mod.main(["--verify", str(path)]), 0)

    def test_verify_matches_check_for_bom_case(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(
                Path(directory),
                case_record(targets=["delivery/scripts/eval.py"], tools=[], inputs=[]),
            )
            path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
            self.assertEqual(eval_mod.check_case_file(path), [])
            result = eval_mod.verify_case(path)
            self.assertEqual(result["status"], "passed")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(eval_mod.main(["--check", str(path)]), 0)
                self.assertEqual(eval_mod.main(["--verify", str(path)]), 0)

    def test_verify_exits_one_only_for_definite_no(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            unresolved = write_case(
                Path(directory),
                case_record(targets=["${{ env.TARGET }}"], tools=[], inputs=[]),
                name="unresolved.md",
            )
            missing = write_case(
                Path(directory),
                case_record(targets=["delivery/does-not-exist.md"], tools=[], inputs=[]),
                name="missing.md",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(eval_mod.main(["--verify", str(unresolved)]), 0)
                self.assertEqual(eval_mod.main(["--verify", str(missing)]), 1)

    def test_verify_json_output_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(
                Path(directory),
                case_record(targets=["delivery/scripts/eval.py"], tools=[]),
            )
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(
                    eval_mod.main(["--verify", str(path), "-o", "json"]),
                    0,
                )
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["mode"], "verify")
            self.assertIn("summary", payload["cases"][0])
            self.assertIn("checks", payload["cases"][0])

    def test_dry_run_writes_case_and_input_hashes_without_executing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.txt").write_text("girdi\n", encoding="utf-8")
            path = write_case(
                root,
                case_record(
                    targets=["delivery/scripts/eval.py"],
                    tools=[],
                    inputs=["input.txt"],
                ),
            )
            with mock.patch("subprocess.run") as run:
                result = eval_mod.dry_run_case(path)
                run.assert_not_called()
            self.assertFalse(result["executed"])
            expected = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(result["sha256"], expected)
            self.assertEqual(
                result["inputs"][0]["sha256"],
                "sha256:" + hashlib.sha256(b"girdi\n").hexdigest(),
            )

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(
                    eval_mod.main(["--dry-run", str(path), "-o", "json"]),
                    0,
                )
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["mode"], "dry-run")
            self.assertFalse(payload["executed"])
            self.assertEqual(payload["cases"][0]["sha256"], expected)

    def test_same_identity_keeps_revisions_separate_and_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "revisions.jsonl"
            first, warnings = eval_mod.record_revision(
                "case-1", "sha256:" + "a" * 64, log=log, at="2026-11-09T10:00:00+00:00"
            )
            self.assertEqual(warnings, [])
            second, warnings = eval_mod.record_revision(
                "case-1", "sha256:" + "b" * 64, log=log, at="2026-11-09T10:05:00+00:00"
            )
            self.assertTrue(any("farklı revision" in item for item in warnings))
            rows = eval_mod.read_revisions(log)
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                {row["revision"] for row in rows},
                {first["revision"], second["revision"]},
            )
            self.assertEqual({row["id"] for row in rows}, {"case-1"})

    def test_run_command_records_selected_case_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = write_case(
                root,
                case_record(targets=["delivery/scripts/eval.py"], tools=[], inputs=[]),
            )
            log = root / "revisions.jsonl"
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(
                    eval_mod.main(
                        ["--run", str(path), "--revision-log", str(log), "-o", "json"]
                    ),
                    0,
                )
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["mode"], "run")
            self.assertEqual(payload["records"][0]["id"], "case-1")
            self.assertEqual(len(eval_mod.read_revisions(log)), 1)


class NoCopiedSourceTests(unittest.TestCase):
    def test_eval_imports_stay_stdlib_and_yaml(self) -> None:
        import ast

        source = (SCRIPTS / "eval.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        allowed = set(sys.stdlib_module_names) | {"yaml", "schema_lite"}
        self.assertEqual(imported - allowed, set(), imported - allowed)
        lowered = source.lower()
        self.assertNotIn("withgauge", lowered)
        self.assertNotIn("createhash", lowered)


class FindingSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = finding_schema()

    def test_valid_record_passes(self) -> None:
        self.assertEqual(validate_schema(finding(), self.schema), [])

    def test_unknown_evidence_stays_unknown(self) -> None:
        record = dict(FIXTURE_UNKNOWN_EVIDENCE)
        self.assertEqual(validate_schema(record, self.schema), [])
        self.assertEqual(record["effect"], "UNKNOWN")
        self.assertEqual(record["cause"], "UNKNOWN")

    def test_unknown_effect_is_not_a_fail_value(self) -> None:
        errors = validate_schema(
            finding(effect="FAIL"), self.schema
        )
        self.assertTrue(any("effect" in item and "enum dışında" in item for item in errors))

    def test_invalid_kind_rejected(self) -> None:
        errors = validate_schema(finding(kind="BUG"), self.schema)
        self.assertTrue(any("kind" in item and "enum dışında" in item for item in errors))

    def test_missing_evidence_rejected(self) -> None:
        record = finding()
        record.pop("evidence")
        errors = validate_schema(record, self.schema)
        self.assertTrue(any("evidence: eksik" in item for item in errors))

    def test_empty_evidence_rejected(self) -> None:
        errors = validate_schema(finding(evidence=[]), self.schema)
        self.assertTrue(any("en az 1 öğe" in item for item in errors))

    def test_trace_evidence_needs_seq(self) -> None:
        errors = validate_schema(finding(evidence=[{"kind": "trace"}]), self.schema)
        self.assertTrue(any("seq: eksik" in item for item in errors))

    def test_artifact_evidence_needs_path_and_line(self) -> None:
        errors = validate_schema(
            finding(evidence=[{"kind": "artifact"}]), self.schema
        )
        self.assertTrue(any("artifact: eksik" in item for item in errors))
        self.assertTrue(any("line: eksik" in item for item in errors))


class FindingCheckTests(unittest.TestCase):
    def test_valid_finding_file_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_finding(Path(directory), finding())
            self.assertEqual(eval_mod.check_finding_file(path), [])

    def test_unknown_finding_file_is_not_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_finding(Path(directory), FIXTURE_UNKNOWN_EVIDENCE)
            self.assertEqual(eval_mod.check_finding_file(path), [])

    def test_invalid_record_reports_schema_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_finding(Path(directory), finding(kind="BUG"))
            errors = eval_mod.check_finding_file(path)
            self.assertTrue(any("enum dışında" in item for item in errors))

    def test_finding_without_evidence_is_rejected(self) -> None:
        record = finding()
        record.pop("evidence")
        with tempfile.TemporaryDirectory() as directory:
            path = write_finding(Path(directory), record)
            errors = eval_mod.check_finding_file(path)
            self.assertTrue(any("kanıt referansı yok" in item for item in errors))

    def test_only_finding_suffixes_are_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_finding(root, finding())
            (root / "notes.md").write_text("serbest metin", encoding="utf-8")
            (root / "payload.json").write_text("{}", encoding="utf-8")
            self.assertEqual(eval_mod.check_findings(root), [])

    def test_check_command_exits_one_on_invalid_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_finding(Path(directory), finding(effect="FAIL"))
            with mock.patch.object(eval_mod, "FINDINGS", Path(directory)):
                with mock.patch.object(sys, "argv", ["eval.py", "--check"]):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(eval_mod.main(), 1)

    def test_check_command_exits_zero_with_unknown_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_finding(Path(directory), FIXTURE_UNKNOWN_EVIDENCE)
            with mock.patch.object(eval_mod, "FINDINGS", Path(directory)):
                with mock.patch.object(sys, "argv", ["eval.py", "--check"]):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(eval_mod.main(), 0)


if __name__ == "__main__":
    unittest.main()
