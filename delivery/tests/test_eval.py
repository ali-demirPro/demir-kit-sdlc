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


def write_skill(root: Path, name: str, description: str = "Use when testing.") -> Path:
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"name: {name}\n"
        "description: >-\n"
        f"  {description}\n"
        "---\n\n"
        f"# {name}\n",
        encoding="utf-8",
    )
    return path


def write_session(
    runs: Path,
    name: str,
    events: list[str] | None = None,
    *,
    case: str = "",
    result: str = "{}",
) -> Path:
    session = runs / name
    (session / "session").mkdir(parents=True, exist_ok=True)
    (session / "spec.json").write_text(
        json.dumps({"case": case}), encoding="utf-8"
    )
    (session / "result.json").write_text(result, encoding="utf-8")
    body = "".join(line + "\n" for line in (events or []))
    (session / "session" / "events.ndjson").write_text(body, encoding="utf-8")
    return session


def write_batch_session(
    root: Path,
    name: str,
    *,
    status: str | None = None,
    criteria: dict | None = None,
    result: str | None = None,
    revision: str | None = None,
    turns: object = None,
    duration_ms: object = None,
) -> Path:
    session = root / "sessions" / name
    session.mkdir(parents=True, exist_ok=True)
    if result is not None:
        payload = result
    else:
        data: dict = {}
        if status is not None:
            data["status"] = status
        if criteria is not None:
            data["criteria"] = criteria
        if revision is not None:
            data["revision"] = revision
        if turns is not None:
            data["turns"] = turns
        if duration_ms is not None:
            data["duration_ms"] = duration_ms
        payload = json.dumps(data)
    (session / "result.json").write_text(payload, encoding="utf-8")
    return session


def write_batch_manifest(
    root: Path,
    batch_id: str,
    sessions: list,
    *,
    nested: bool = False,
    **extra,
) -> Path:
    manifest = {
        "demir_kit_version": "2",
        "batch": batch_id,
        "sessions": sessions,
    }
    manifest.update(extra)
    if nested:
        path = root / batch_id / "batch.json"
    else:
        path = root / f"{batch_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
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


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.skills = self.root / "skills"
        self.runs = self.root / "runs"
        self.skills.mkdir()
        self.runs.mkdir()
        write_skill(self.skills, "behavior-gate")
        write_session(
            self.runs,
            "01-triggered",
            [
                '{"seq": 0, "payload": {"tool": "read"}}',
                '{"seq": 1, "payload": {"skill": "behavior-gate"}}',
            ],
        )
        write_session(
            self.runs,
            "02-plain",
            ['{"seq": 0, "payload": {"tool": "read", "text": "merhaba"}}'],
        )
        write_session(self.runs, "03-empty", [])

    def tearDown(self) -> None:
        self._directory.cleanup()

    def report(self) -> dict:
        return eval_mod.build_discovery(
            ["behavior-gate"],
            [self.runs],
            runs=self.runs,
            skills_root=self.skills,
        )

    def test_t1_sessions_classify_as_triggered_plain_unknown(self) -> None:
        rows = self.report()["skills"][0]["sessions"]
        self.assertEqual(
            [row["status"] for row in rows],
            ["triggered", "not_triggered", "unknown"],
        )
        self.assertEqual([row["analyzable"] for row in rows], [True, True, False])

    def test_t2_unknown_is_counted_separately_from_not_triggered(self) -> None:
        skill = self.report()["skills"][0]
        self.assertEqual(skill["counts"]["unknown"], 1)
        self.assertEqual(skill["counts"]["not_triggered"], 1)
        self.assertEqual(skill["counts"]["triggered"], 1)
        self.assertEqual(skill["counts"]["analyzable"], 2)
        self.assertEqual(skill["rate"]["denominator"], 2)
        self.assertEqual(skill["rate"]["numerator"], 1)
        self.assertAlmostEqual(skill["rate"]["value"], 0.5)
        self.assertEqual(skill["unknown_rate"]["numerator"], 1)
        self.assertEqual(skill["unknown_rate"]["denominator"], 3)
        self.assertAlmostEqual(skill["unknown_rate"]["value"], 0.3333, places=4)
        unknown_row = next(
            row for row in skill["sessions"] if row["status"] == "unknown"
        )
        self.assertEqual(unknown_row["status"], "unknown")
        self.assertEqual(unknown_row["evidence"], [])
        self.assertTrue(unknown_row["reason"])

    def test_t3_evidence_points_at_the_matching_event_line(self) -> None:
        rows = self.report()["skills"][0]["sessions"]
        triggered, plain, unknown = rows
        self.assertEqual(
            triggered["evidence"],
            [{"kind": "artifact", "artifact": "session/events.ndjson", "line": 2}],
        )
        events_path = Path(triggered["session"]) / "session" / "events.ndjson"
        lines = events_path.read_text(encoding="utf-8").splitlines()
        self.assertIn('"skill": "behavior-gate"', lines[1])
        self.assertEqual(
            plain["evidence"],
            [{"kind": "artifact", "artifact": "session/events.ndjson", "line": 1}],
        )
        self.assertEqual(unknown["evidence"], [])

    def test_committed_case_matches_runs_by_case_field(self) -> None:
        case = write_case(
            self.root,
            case_record(),
            name="behavior.md",
        )
        write_session(
            self.runs,
            "04-case",
            ['{"seq": 0, "payload": {"name": "behavior-gate"}}'],
            case="behavior.md",
        )
        report = eval_mod.build_discovery(
            ["behavior-gate"],
            [case],
            runs=self.runs,
            skills_root=self.skills,
        )
        rows = report["skills"][0]["sessions"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["case"], "behavior.md")
        self.assertEqual(rows[0]["status"], "triggered")

    def test_case_without_sessions_is_reported_separately(self) -> None:
        case = write_case(self.root, case_record(), name="unused.md")
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = eval_mod.main(
                [
                    "discovery",
                    "--skill",
                    "behavior-gate",
                    "--case",
                    str(case),
                    "--runs",
                    str(self.runs),
                    "-o",
                    "json",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["skills"][0]["sessions"], [])
        self.assertEqual(payload["skills"][0]["counts"]["unknown"], 0)
        self.assertEqual(payload["cases_without_sessions"], [str(case)])

    def test_partially_corrupt_ndjson_is_unknown(self) -> None:
        session = write_session(
            self.runs,
            "05-corrupt",
            [
                '{"payload": {"skill": "behavior-gate"}',
                '{"payload": {"tool": "read"}}',
            ],
        )
        row = eval_mod.classify_session(session, "behavior-gate")
        self.assertEqual(row["status"], "unknown")
        self.assertFalse(row["analyzable"])
        self.assertEqual(row["event_count"], 1)
        self.assertIn("bozuk NDJSON", row["reason"])
        self.assertEqual(row["evidence"], [])
        self.assertEqual(row["matching_lines"], 0)

    def test_non_utf8_events_are_unknown_and_command_exits_zero(self) -> None:
        session = write_session(self.runs, "06-bytes", ['{"seq": 0}'])
        (session / "session" / "events.ndjson").write_bytes(
            b'{"seq": 0}\n\xff\xfe'
        )
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = eval_mod.main(
                [
                    "discovery",
                    "--skill",
                    "behavior-gate",
                    "--case",
                    str(session),
                    "--runs",
                    str(self.runs),
                    "-o",
                    "json",
                ]
            )
        self.assertEqual(code, 0)
        rows = json.loads(stream.getvalue())["skills"][0]["sessions"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "unknown")
        self.assertIn("okunamadı", rows[0]["reason"])

    def test_non_utf8_skill_description_exits_two(self) -> None:
        skill = write_skill(self.skills, "broken-skill")
        skill.write_bytes(b"---\nname: broken-skill\ndescription: \xff\xfe\n---\n")
        errors = io.StringIO()
        with mock.patch.object(eval_mod, "SKILLS", self.skills), contextlib.redirect_stderr(
            errors
        ):
            code = eval_mod.main(
                [
                    "discovery",
                    "--skill",
                    "broken-skill",
                    "--case",
                    str(self.runs),
                    "--runs",
                    str(self.runs),
                    "-o",
                    "json",
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("encoding", errors.getvalue())

    def test_same_named_cases_do_not_share_sessions(self) -> None:
        (self.root / "cases" / "a").mkdir(parents=True)
        (self.root / "cases" / "b").mkdir(parents=True)
        case_a = write_case(self.root, case_record(), name="cases/a/demo.md")
        case_b = write_case(self.root, case_record(), name="cases/b/demo.md")
        write_session(
            self.runs,
            "07-a",
            ['{"seq": 0, "payload": {"skill": "behavior-gate"}}'],
            case="cases/a/demo.md",
        )
        write_session(
            self.runs,
            "08-b",
            ['{"seq": 0, "payload": {"tool": "read"}}'],
            case="cases/b/demo.md",
        )
        sessions_a, empty_a = eval_mod.discovery_sessions([case_a], self.runs)
        sessions_b, empty_b = eval_mod.discovery_sessions([case_b], self.runs)
        self.assertEqual(empty_a + empty_b, [])
        self.assertEqual([path.name for path in sessions_a], ["07-a"])
        self.assertEqual([path.name for path in sessions_b], ["08-b"])

    def test_basename_only_evidence_matches_only_a_unique_case_name(self) -> None:
        (self.root / "cases" / "a").mkdir(parents=True)
        (self.root / "cases" / "b").mkdir(parents=True)
        case_a = write_case(self.root, case_record(), name="cases/a/demo.md")
        case_b = write_case(self.root, case_record(), name="cases/b/demo.md")
        write_session(
            self.runs,
            "15-bare",
            ['{"seq": 0, "payload": {"skill": "behavior-gate"}}'],
            case="demo.md",
        )
        sessions_one, empty_one = eval_mod.discovery_sessions([case_a], self.runs)
        self.assertEqual(empty_one, [])
        self.assertEqual([path.name for path in sessions_one], ["15-bare"])

        sessions_both, empty_both = eval_mod.discovery_sessions(
            [case_a, case_b], self.runs
        )
        self.assertEqual(sessions_both, [])
        self.assertEqual(empty_both, [str(case_a), str(case_b)])

    def test_normalized_basename_variants_are_ambiguous(self) -> None:
        (self.root / "cases" / "a").mkdir(parents=True)
        (self.root / "cases" / "b").mkdir(parents=True)
        case_a = write_case(self.root, case_record(), name="cases/a/demo.md")
        case_b = write_case(self.root, case_record(), name="cases/b/demo.md")
        write_session(
            self.runs,
            "16-dot-prefix",
            ['{"seq": 0, "payload": {"skill": "behavior-gate"}}'],
            case="./demo.md",
        )
        write_session(
            self.runs,
            "17-trailing-slash",
            ['{"seq": 0, "payload": {"tool": "read"}}'],
            case="demo.md/",
        )
        sessions, empty = eval_mod.discovery_sessions([case_a, case_b], self.runs)
        self.assertEqual(sessions, [])
        self.assertEqual(empty, [str(case_a), str(case_b)])

    def test_dotdot_basename_variant_is_ambiguous(self) -> None:
        (self.root / "cases" / "a").mkdir(parents=True)
        (self.root / "cases" / "b").mkdir(parents=True)
        case_a = write_case(self.root, case_record(), name="cases/a/demo.md")
        case_b = write_case(self.root, case_record(), name="cases/b/demo.md")
        write_session(
            self.runs,
            "18-dotdot",
            ['{"seq": 0, "payload": {"skill": "behavior-gate"}}'],
            case="foo/../demo.md",
        )
        sessions, empty = eval_mod.discovery_sessions([case_a, case_b], self.runs)
        self.assertEqual(sessions, [])
        self.assertEqual(empty, [str(case_a), str(case_b)])

        sessions_unique, empty_unique = eval_mod.discovery_sessions(
            [case_a], self.runs
        )
        self.assertEqual(empty_unique, [])
        self.assertEqual([path.name for path in sessions_unique], ["18-dotdot"])

    def test_unexpandable_or_null_case_value_does_not_crash_discovery(self) -> None:
        case = write_case(self.root, case_record(), name="edge.md")
        write_session(
            self.runs,
            "13-tilde",
            ['{"seq": 0, "payload": {"skill": "behavior-gate"}}'],
            case="~olmayankullanici/x.md",
        )
        write_session(
            self.runs,
            "14-nul",
            ['{"seq": 0, "payload": {"skill": "behavior-gate"}}'],
            case="bad\x00name.md",
        )
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = eval_mod.main(
                [
                    "discovery",
                    "--skill",
                    "behavior-gate",
                    "--case",
                    str(case),
                    "--runs",
                    str(self.runs),
                    "-o",
                    "json",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["skills"][0]["sessions"], [])
        self.assertEqual(payload["cases_without_sessions"], [str(case)])

    def test_missing_case_path_exits_two(self) -> None:
        missing = self.root / "does-not-exist.md"
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            code = eval_mod.main(
                [
                    "discovery",
                    "--skill",
                    "behavior-gate",
                    "--case",
                    str(missing),
                    "--runs",
                    str(self.runs),
                    "-o",
                    "json",
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("case yok", errors.getvalue())

    def test_stdout_and_exit_mentions_do_not_trigger(self) -> None:
        stdout_session = write_session(
            self.runs,
            "09-stdout",
            [
                '{"seq": 0, "payload": {"type": "stdout", '
                '"text": "behavior-gate çıktısı"}}'
            ],
        )
        exit_session = write_session(
            self.runs,
            "10-exit",
            ['{"seq": 0, "payload": {"type": "process.exit", "text": "behavior-gate"}}'],
        )
        start_session = write_session(
            self.runs,
            "11-start",
            [
                '{"seq": 0, "payload": {"type": "process.start", '
                '"command": ["cat", "skills/behavior-gate/SKILL.md"]}}'
            ],
        )
        cases = (
            (stdout_session, "not_triggered"),
            (exit_session, "not_triggered"),
            (start_session, "triggered"),
        )
        for session, expected in cases:
            row = eval_mod.classify_session(session, "behavior-gate")
            self.assertEqual(row["status"], expected, session.name)

    def test_evidence_truncation_is_reported(self) -> None:
        events = [
            '{"seq": %d, "payload": {"skill": "behavior-gate"}}' % index
            for index in range(25)
        ]
        session = write_session(self.runs, "12-many", events)
        row = eval_mod.classify_session(session, "behavior-gate")
        self.assertEqual(row["status"], "triggered")
        self.assertEqual(row["matching_lines"], 25)
        self.assertEqual(len(row["evidence"]), eval_mod.MAX_EVIDENCE)
        self.assertTrue(row["evidence_truncated"])

    def test_missing_skill_exits_two_without_touching_files(self) -> None:
        skill_path = self.skills / "behavior-gate" / "SKILL.md"
        before = skill_path.read_bytes()
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            code = eval_mod.main(
                [
                    "discovery",
                    "--skill",
                    "does-not-exist",
                    "--case",
                    str(self.runs),
                    "--runs",
                    str(self.runs),
                    "-o",
                    "json",
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("skill yok", errors.getvalue())
        self.assertEqual(skill_path.read_bytes(), before)

    def test_skill_file_stays_byte_identical(self) -> None:
        skill_path = self.skills / "behavior-gate" / "SKILL.md"
        before = skill_path.read_bytes()
        self.report()
        self.assertEqual(skill_path.read_bytes(), before)

    def test_t4_multi_skill_report_has_rates_evidence_and_totals(self) -> None:
        names = ["behavior-gate", "health-check", "work-package"]
        for name in names:
            write_skill(self.skills, name, description=f"Use {name} when testing.")
        write_session(
            self.runs,
            "20-health",
            ['{"seq": 0, "payload": {"skill": "health-check"}}'],
        )
        write_session(
            self.runs,
            "21-work",
            ['{"seq": 0, "payload": {"skill": "work-package"}}'],
        )
        report = eval_mod.build_discovery(
            names, [self.runs], runs=self.runs, skills_root=self.skills
        )
        self.assertEqual([skill["name"] for skill in report["skills"]], names)
        expected = {
            "behavior-gate": (1, 4),
            "health-check": (1, 4),
            "work-package": (1, 4),
        }
        for skill in report["skills"]:
            numerator, denominator = expected[skill["name"]]
            self.assertGreater(skill["rate"]["denominator"], 0)
            self.assertEqual(skill["rate"]["numerator"], numerator)
            self.assertEqual(skill["rate"]["denominator"], denominator)
            self.assertAlmostEqual(skill["rate"]["value"], numerator / denominator)
            self.assertTrue(skill["description_sha256"].startswith("sha256:"))
            self.assertTrue(skill["source"].endswith("SKILL.md"))
            self.assertTrue(any(row["evidence"] for row in skill["sessions"]))
            counts = skill["counts"]
            self.assertEqual(
                counts["triggered"] + counts["not_triggered"] + counts["unknown"],
                counts["total"],
            )
            self.assertEqual(
                counts["analyzable"], counts["total"] - counts["unknown"]
            )
        totals = report["totals"]
        for key in (
            "triggered",
            "not_triggered",
            "unknown",
            "total",
            "analyzable",
        ):
            self.assertEqual(
                totals[key],
                sum(skill["counts"][key] for skill in report["skills"]),
                key,
            )

    def _discovery_json(self, args: list[str]) -> str:
        stream = io.StringIO()
        with mock.patch.object(eval_mod, "SKILLS", self.skills), contextlib.redirect_stdout(
            stream
        ):
            code = eval_mod.main(
                ["discovery", *args, "--runs", str(self.runs), "-o", "json"]
            )
        self.assertEqual(code, 0)
        return stream.getvalue()

    def test_t5_argument_order_is_byte_stable(self) -> None:
        (self.root / "cases").mkdir()
        case_a = write_case(self.root, case_record(id="case-a"), name="cases/a.md")
        case_b = write_case(self.root, case_record(id="case-b"), name="cases/b.md")
        write_skill(self.skills, "health-check")
        write_session(
            self.runs,
            "20-a",
            ['{"seq": 0, "payload": {"skill": "behavior-gate"}}'],
            case="cases/a.md",
        )
        write_session(
            self.runs,
            "21-b",
            ['{"seq": 0, "payload": {"skill": "health-check"}}'],
            case="cases/b.md",
        )
        first = self._discovery_json(
            [
                "--skill",
                "health-check",
                "--skill",
                "behavior-gate",
                "--skill",
                "health-check",
                "--case",
                str(case_b),
                "--case",
                str(case_a),
            ]
        )
        second = self._discovery_json(
            [
                "--skill",
                "behavior-gate",
                "--skill",
                "health-check",
                "--case",
                str(case_a),
                "--case",
                str(case_b),
            ]
        )
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(
            [skill["name"] for skill in payload["skills"]],
            ["behavior-gate", "health-check"],
        )
        for skill in payload["skills"]:
            sessions = [row["session"] for row in skill["sessions"]]
            self.assertEqual(sessions, sorted(sessions))
        self.assertEqual(payload["cases_without_sessions"], [])

    def test_t6_real_skill_description_is_read_only(self) -> None:
        skill_path = ROOT / "skills" / "behavior-gate" / "SKILL.md"
        before = skill_path.read_bytes()
        before_sha = hashlib.sha256(before).hexdigest()
        report = eval_mod.build_discovery(
            ["behavior-gate"], [self.runs], runs=self.runs
        )
        after = skill_path.read_bytes()
        self.assertEqual(hashlib.sha256(after).hexdigest(), before_sha)
        skill = report["skills"][0]
        self.assertEqual(skill["source"], "skills/behavior-gate/SKILL.md")
        frontmatter, _body, error = eval_mod.split_frontmatter(
            before.decode("utf-8").lstrip("\ufeff")
        )
        self.assertIsNone(error)
        description = frontmatter["description"].strip()
        self.assertTrue(description)
        self.assertEqual(
            skill["description_sha256"],
            "sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest(),
        )


class CompareTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.batches = self.root / "batches"
        self.batches.mkdir()

    def tearDown(self) -> None:
        self._directory.cleanup()

    def run_compare(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = eval_mod.main(
                [
                    "compare",
                    "--batch-root",
                    str(self.batches),
                    *arguments,
                ]
            )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_t1_selectors_reject_missing_empty_duplicate_and_unknown(self) -> None:
        write_batch_session(
            self.batches, "base-ok", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_session(
            self.batches, "cand-ok", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(self.batches, "base", ["sessions/base-ok"])
        write_batch_manifest(self.batches, "cand", ["sessions/cand-ok"])

        code, _, errors = self.run_compare("--candidate", "batch=cand")
        self.assertEqual(code, 2)
        self.assertIn("--baseline", errors)

        code, _, errors = self.run_compare(
            "--baseline", "batch=", "--candidate", "batch=cand"
        )
        self.assertEqual(code, 2)
        self.assertIn("boş", errors)

        code, _, errors = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=base"
        )
        self.assertEqual(code, 2)
        self.assertIn("aynı batch", errors)

        code, _, errors = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=missing"
        )
        self.assertEqual(code, 2)
        self.assertIn("bulunamadı", errors)

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "-o", "json"
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["mode"], "compare")

    def test_t2_rates_use_judged_denominator_and_exclude_unassessable(self) -> None:
        write_batch_session(
            self.batches,
            "base-1",
            status="pass",
            criteria={"AC-1": "pass"},
        )
        write_batch_session(
            self.batches,
            "base-2",
            status="fail",
            criteria={"AC-1": "pass", "AC-2": "fail"},
        )
        write_batch_session(
            self.batches,
            "base-3",
            status="blocked",
            criteria={"AC-1": "unknown"},
        )
        write_batch_manifest(
            self.batches,
            "base",
            ["sessions/base-1", "sessions/base-2", "sessions/base-3"],
        )

        write_batch_session(
            self.batches,
            "cand-1",
            status="pass",
            criteria={"AC-1": "pass"},
        )
        write_batch_session(
            self.batches,
            "cand-2",
            status="pass",
            criteria={"AC-2": "pass", "AC-3": "unassessable"},
        )
        write_batch_manifest(
            self.batches,
            "cand",
            [
                str(self.batches / "sessions" / "cand-1"),
                str(self.batches / "sessions" / "cand-2"),
            ],
            nested=True,
        )

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "--json"
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        baseline = payload["baseline"]
        candidate = payload["candidate"]

        self.assertEqual(baseline["sessions"], 3)
        self.assertEqual(baseline["completed"], 2)
        self.assertEqual(
            baseline["pass_rate"],
            {"pass": 2, "judged": 3, "value": 0.6667, "basis": "criteria"},
        )
        self.assertEqual(baseline["criteria"]["AC-1"]["pass"], 2)
        self.assertEqual(baseline["criteria"]["AC-1"]["unknown"], 1)
        self.assertEqual(baseline["criteria"]["AC-1"]["judged"], 2)
        self.assertEqual(baseline["criteria"]["AC-1"]["value"], 1.0)
        self.assertEqual(baseline["criteria"]["AC-2"]["fail"], 1)
        self.assertEqual(baseline["criteria"]["AC-2"]["judged"], 1)
        self.assertEqual(baseline["criteria"]["AC-2"]["value"], 0.0)

        self.assertEqual(candidate["sessions"], 2)
        self.assertEqual(candidate["completed"], 2)
        self.assertEqual(
            candidate["pass_rate"],
            {"pass": 2, "judged": 2, "value": 1.0, "basis": "criteria"},
        )
        self.assertEqual(candidate["criteria"]["AC-3"]["unassessable"], 1)
        self.assertEqual(candidate["criteria"]["AC-3"]["judged"], 0)
        self.assertIsNone(candidate["criteria"]["AC-3"]["value"])
        self.assertEqual(candidate["criteria"]["AC-2"]["value"], 1.0)

    def test_t3_completion_is_not_judgement(self) -> None:
        write_batch_session(
            self.batches,
            "done-unknown",
            status="pass",
            criteria={"AC-1": "unknown"},
        )
        write_batch_session(
            self.batches,
            "done-unassessable",
            status="pass",
            criteria={"AC-1": "unassessable"},
        )
        write_batch_manifest(
            self.batches,
            "base",
            [
                "sessions/done-unknown",
                "sessions/done-unassessable",
            ],
        )
        write_batch_session(
            self.batches, "cand-done", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-done"])

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "-o", "json"
        )
        self.assertEqual(code, 0)
        baseline = json.loads(stdout)["baseline"]
        self.assertEqual(baseline["sessions"], 2)
        self.assertEqual(baseline["completed"], 2)
        self.assertEqual(
            baseline["pass_rate"],
            {"pass": 0, "judged": 0, "value": None, "basis": "criteria"},
        )
        self.assertEqual(baseline["criteria"]["AC-1"]["unknown"], 1)
        self.assertEqual(baseline["criteria"]["AC-1"]["unassessable"], 1)
        self.assertEqual(baseline["criteria"]["AC-1"]["judged"], 0)
        self.assertIsNone(baseline["criteria"]["AC-1"]["value"])

    def test_missing_or_broken_result_is_unknown_and_does_not_crash(self) -> None:
        missing = self.batches / "sessions" / "missing"
        missing.mkdir(parents=True)
        write_batch_session(self.batches, "broken", result="{bozuk")
        write_batch_session(self.batches, "broken-2", result="{bozuk")
        write_batch_manifest(
            self.batches,
            "base",
            [
                "sessions/missing",
                "sessions/broken",
                {"session": "sessions/broken-2", "criteria": {"AC-1": "pass"}},
            ],
        )
        write_batch_session(
            self.batches, "cand-ok", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-ok"])

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "-o", "json"
        )
        self.assertEqual(code, 0)
        baseline = json.loads(stdout)["baseline"]
        self.assertEqual(baseline["sessions"], 3)
        self.assertEqual(baseline["completed"], 0)
        self.assertEqual(baseline["criteria"]["AC-1"]["pass"], 1)
        self.assertEqual(baseline["criteria"]["AC-1"]["judged"], 1)

    def test_adv1_revision_filters_sessions_and_counts_missing(self) -> None:
        write_batch_session(
            self.batches,
            "a",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="sha256:a",
        )
        write_batch_session(
            self.batches,
            "b",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="sha256:b",
        )
        write_batch_session(
            self.batches,
            "c",
            status="pass",
            criteria={"AC-1": "pass"},
        )
        write_batch_session(
            self.batches,
            "cand-a",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="sha256:a",
        )
        write_batch_manifest(
            self.batches, "base", ["sessions/a", "sessions/b", "sessions/c"]
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-a"])

        code, stdout, _ = self.run_compare(
            "--baseline",
            "batch=base",
            "--candidate",
            "batch=cand",
            "--revision",
            "sha256:a",
            "--json",
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["revision"], "sha256:a")
        baseline = payload["baseline"]
        self.assertEqual(baseline["sessions"], 1)
        self.assertEqual(baseline["completed"], 1)
        self.assertEqual(
            baseline["pass_rate"],
            {"pass": 1, "judged": 1, "value": 1.0, "basis": "criteria"},
        )
        self.assertEqual(
            payload["warnings"],
            [
                "baseline: revision filtresi (sha256:a): 1 eşleşti; "
                "1 farklı revision ve 1 revision taşımayan oturum dışlandı",
                "candidate: revision filtresi (sha256:a): 1 eşleşti; "
                "0 farklı revision ve 0 revision taşımayan oturum dışlandı",
            ],
        )

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "--json"
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["baseline"]["sessions"], 3)

    def test_adv1_manifest_revision_is_a_default(self) -> None:
        write_batch_session(
            self.batches, "a", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_session(
            self.batches,
            "cand-a",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="sha256:m",
        )
        write_batch_manifest(
            self.batches, "base", ["sessions/a"], revision="sha256:m"
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-a"])

        code, stdout, _ = self.run_compare(
            "--baseline",
            "batch=base",
            "--candidate",
            "batch=cand",
            "--revision",
            "sha256:m",
            "-o",
            "json",
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["baseline"]["sessions"], 1)

    def test_adv2_duplicate_session_paths_are_deduplicated(self) -> None:
        write_batch_session(
            self.batches, "a", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(
            self.batches,
            "base",
            [
                "sessions/a",
                "sessions/a",
                {"session": "sessions/a"},
            ],
        )
        write_batch_session(
            self.batches, "cand-ok", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-ok"])

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "--json"
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        baseline = payload["baseline"]
        self.assertEqual(baseline["sessions"], 1)
        self.assertEqual(baseline["completed"], 1)
        self.assertEqual(
            baseline["pass_rate"],
            {"pass": 1, "judged": 1, "value": 1.0, "basis": "criteria"},
        )
        self.assertEqual(
            payload["warnings"],
            ["baseline: 2 yinelenen oturum girdisi tekilleştirildi"],
        )

    def test_adv2_conflicting_duplicate_overrides_are_rejected(self) -> None:
        write_batch_session(
            self.batches, "a", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(
            self.batches,
            "base",
            [
                "sessions/a",
                {"session": "sessions/a", "criteria": {"AC-1": "fail"}},
            ],
        )
        write_batch_manifest(self.batches, "cand", [])

        code, _, errors = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand"
        )
        self.assertEqual(code, 2)
        self.assertIn("sessions[1]", errors)
        self.assertIn("çakış", errors)

    def test_adv3_invalid_session_entries_are_rejected(self) -> None:
        write_batch_manifest(self.batches, "cand", [])
        cases = [
            ([42], "string ya da nesne"),
            ([{"criteria": {"AC-1": "pass"}}], "'session' alanı"),
            ([""], "boş olamaz"),
            ([{"session": "  "}], "boş olamaz"),
        ]
        for sessions, expected in cases:
            with self.subTest(sessions=sessions):
                write_batch_manifest(self.batches, "base", sessions)
                code, _, errors = self.run_compare(
                    "--baseline", "batch=base", "--candidate", "batch=cand"
                )
                self.assertEqual(code, 2)
                self.assertIn("sessions[0]", errors)
                self.assertIn(expected, errors)

    def test_adv4_relative_paths_resolve_only_against_manifest_dir(self) -> None:
        write_batch_session(
            self.batches, "a", status="pass", criteria={"AC-1": "pass"}
        )
        outside = self.root / "trap" / "a"
        outside.mkdir(parents=True)
        (outside / "result.json").write_text(
            json.dumps({"status": "pass", "criteria": {"TRAP": "pass"}}),
            encoding="utf-8",
        )
        write_batch_manifest(
            self.batches,
            "base",
            ["sessions/a", "sessions/absent", str(outside)],
        )
        write_batch_session(
            self.batches, "cand-ok", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-ok"])

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "--json"
        )
        self.assertEqual(code, 0)
        baseline = json.loads(stdout)["baseline"]
        self.assertEqual(baseline["sessions"], 3)
        self.assertIn(
            str((self.batches / "sessions" / "a").resolve()),
            baseline["session_paths"],
        )
        self.assertIn(outside.resolve().as_posix(), baseline["session_paths"])
        self.assertEqual(
            baseline["unresolved"],
            [
                {
                    "path": str((self.batches / "sessions" / "absent").resolve()),
                    "reason": "oturum dizini yok: "
                    + str((self.batches / "sessions" / "absent").resolve()),
                }
            ],
        )
        self.assertEqual(baseline["criteria"]["TRAP"]["pass"], 1)
        self.assertEqual(baseline["completed"], 2)

    def test_adv4_missing_relative_session_is_unknown_with_reason(self) -> None:
        write_batch_manifest(
            self.batches, "base", ["sessions/ghost"]
        )
        write_batch_session(
            self.batches, "cand-ok", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-ok"])

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "-o", "json"
        )
        self.assertEqual(code, 0)
        baseline = json.loads(stdout)["baseline"]
        self.assertEqual(baseline["sessions"], 1)
        self.assertEqual(baseline["completed"], 0)
        self.assertEqual(
            baseline["pass_rate"],
            {"pass": 0, "judged": 0, "value": None, "basis": "criteria"},
        )
        self.assertEqual(len(baseline["unresolved"]), 1)
        self.assertIn("oturum dizini yok", baseline["unresolved"][0]["reason"])

    def test_adv5_pass_rate_names_criteria_basis(self) -> None:
        write_batch_session(
            self.batches,
            "multi",
            status="pass",
            criteria={"AC-1": "pass", "AC-2": "pass", "AC-3": "fail"},
        )
        write_batch_session(
            self.batches, "single", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_session(
            self.batches, "cand-ok", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(self.batches, "base", ["sessions/multi", "sessions/single"])
        write_batch_manifest(self.batches, "cand", ["sessions/cand-ok"])

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "--json"
        )
        self.assertEqual(code, 0)
        baseline = json.loads(stdout)["baseline"]
        self.assertEqual(baseline["pass_rate"]["basis"], "criteria")
        self.assertEqual(
            baseline["pass_rate"],
            {"pass": 3, "judged": 4, "value": 0.75, "basis": "criteria"},
        )

        code, text, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand"
        )
        self.assertEqual(code, 0)
        self.assertIn("pass rate (kriter ağırlıklı)", text)


    def test_adv6_unknown_override_keys_are_rejected(self) -> None:
        write_batch_session(
            self.batches, "a", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(self.batches, "cand", [])
        cases = [
            ({"session": "sessions/a", "critera": {"AC-1": "pass"}}, "critera"),
            ({"session": "sessions/a", "status": "pass", "extra": 1}, "extra"),
        ]
        for entry, key in cases:
            with self.subTest(entry=entry):
                write_batch_manifest(self.batches, "base", [entry])
                code, _, errors = self.run_compare(
                    "--baseline", "batch=base", "--candidate", "batch=cand"
                )
                self.assertEqual(code, 2)
                self.assertIn("sessions[0]", errors)
                self.assertIn("bilinmeyen override anahtarı", errors)
                self.assertIn(key, errors)

    def test_adv7_missing_session_keeps_override_revision_and_unresolved(self) -> None:
        write_batch_session(
            self.batches,
            "a",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="sha256:a",
        )
        write_batch_manifest(
            self.batches,
            "base",
            [
                "sessions/a",
                {"session": "sessions/ghost", "revision": "sha256:a"},
                "sessions/ghost-no-rev",
                {"session": "sessions/ghost-b", "revision": "sha256:b"},
            ],
        )
        write_batch_session(
            self.batches,
            "cand-a",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="sha256:a",
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-a"])

        code, stdout, _ = self.run_compare(
            "--baseline",
            "batch=base",
            "--candidate",
            "batch=cand",
            "--revision",
            "sha256:a",
            "--json",
        )
        self.assertEqual(code, 0)
        baseline = json.loads(stdout)["baseline"]
        self.assertEqual(baseline["sessions"], 2)
        self.assertEqual(
            baseline["pass_rate"],
            {"pass": 1, "judged": 1, "value": 1.0, "basis": "criteria"},
        )
        unresolved_paths = sorted(item["path"] for item in baseline["unresolved"])
        self.assertEqual(
            unresolved_paths,
            [
                str((self.batches / "sessions" / "ghost").resolve()),
                str((self.batches / "sessions" / "ghost-b").resolve()),
                str((self.batches / "sessions" / "ghost-no-rev").resolve()),
            ],
        )
        ghost = next(
            item
            for item in baseline["unresolved"]
            if item["path"].endswith("sessions/ghost")
        )
        self.assertIn("oturum dizini yok", ghost["reason"])

    def test_adv8_session_path_and_revision_are_stripped(self) -> None:
        write_batch_session(
            self.batches,
            "a",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="  sha256:a  ",
        )
        write_batch_manifest(
            self.batches,
            "base",
            [{"session": "  sessions/a  ", "revision": "  sha256:a  "}],
        )
        write_batch_session(
            self.batches,
            "cand-a",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="sha256:a",
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-a"])

        code, stdout, _ = self.run_compare(
            "--baseline",
            "batch=base",
            "--candidate",
            "batch=cand",
            "--revision",
            "  sha256:a  ",
            "--json",
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["revision"], "sha256:a")
        baseline = payload["baseline"]
        self.assertEqual(baseline["sessions"], 1)
        self.assertEqual(baseline["revision"], "sha256:a")
        self.assertEqual(
            baseline["session_paths"],
            [str((self.batches / "sessions" / "a").resolve())],
        )
        self.assertEqual(
            baseline["pass_rate"],
            {"pass": 1, "judged": 1, "value": 1.0, "basis": "criteria"},
        )

    def test_adv8_manifest_revision_is_stripped(self) -> None:
        write_batch_session(
            self.batches, "a", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_session(
            self.batches,
            "cand-a",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="sha256:m",
        )
        write_batch_manifest(
            self.batches, "base", ["sessions/a"], revision="  sha256:m  "
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-a"])

        code, stdout, _ = self.run_compare(
            "--baseline",
            "batch=base",
            "--candidate",
            "batch=cand",
            "--revision",
            "sha256:m",
            "--json",
        )
        self.assertEqual(code, 0)
        baseline = json.loads(stdout)["baseline"]
        self.assertEqual(baseline["sessions"], 1)
        self.assertEqual(baseline["revision"], "sha256:m")

    def test_t4_medians_and_delta_are_computed(self) -> None:
        write_batch_session(
            self.batches,
            "base-1",
            status="pass",
            criteria={"AC-1": "pass"},
            turns=2,
            duration_ms=100,
        )
        write_batch_session(
            self.batches,
            "base-2",
            status="pass",
            criteria={"AC-1": "pass"},
            turns=4,
            duration_ms=200,
        )
        write_batch_session(
            self.batches,
            "base-3",
            status="fail",
            criteria={"AC-1": "fail"},
            turns=6,
            duration_ms=300,
        )
        # Missing duration is skipped instead of becoming zero.
        write_batch_session(
            self.batches,
            "base-4",
            status="pass",
            criteria={"AC-1": "pass"},
            turns=8,
        )
        write_batch_manifest(
            self.batches,
            "base",
            [
                "sessions/base-1",
                "sessions/base-2",
                "sessions/base-3",
                "sessions/base-4",
            ],
        )
        write_batch_session(
            self.batches,
            "cand-1",
            status="pass",
            criteria={"AC-1": "pass"},
            turns=3,
            duration_ms=150,
        )
        write_batch_session(
            self.batches,
            "cand-2",
            status="pass",
            criteria={"AC-1": "pass"},
            turns=5,
            duration_ms=250,
        )
        write_batch_manifest(
            self.batches, "cand", ["sessions/cand-1", "sessions/cand-2"]
        )

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "--json"
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        baseline = payload["baseline"]
        candidate = payload["candidate"]

        # Even count averages the middle pair; odd count takes the middle value.
        self.assertEqual(baseline["median_turns"], 5.0)
        self.assertEqual(baseline["median_duration_ms"], 200.0)
        self.assertEqual(candidate["median_turns"], 4.0)
        self.assertEqual(candidate["median_duration_ms"], 200.0)
        self.assertEqual(
            payload["delta"],
            {
                "pass_rate": 0.25,
                "criteria": {"AC-1": 0.25},
                "median_turns": -1.0,
                "median_duration_ms": 0.0,
                "judged": -2,
            },
        )

        code, text, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand"
        )
        self.assertEqual(code, 0)
        self.assertIn("medyan tur: 5.00", text)
        self.assertIn("medyan süre: 200.00 ms", text)
        self.assertIn("delta: pass rate +0.2500", text)
        self.assertIn("medyan tur -1.00", text)

        # Invalid (string, bool) metrics are skipped; no values means null.
        write_batch_session(
            self.batches,
            "invalid",
            result=json.dumps(
                {
                    "status": "pass",
                    "criteria": {"AC-1": "pass"},
                    "turns": "3",
                    "duration_ms": True,
                }
            ),
        )
        write_batch_manifest(self.batches, "null", ["sessions/invalid"])
        code, stdout, _ = self.run_compare(
            "--baseline", "batch=null", "--candidate", "batch=cand", "--json"
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertIsNone(payload["baseline"]["median_turns"])
        self.assertIsNone(payload["baseline"]["median_duration_ms"])
        self.assertIsNone(payload["delta"]["median_turns"])
        self.assertIsNone(payload["delta"]["median_duration_ms"])

    def test_t5_mixed_revision_warns_and_revision_narrows(self) -> None:
        write_batch_session(
            self.batches,
            "base-r1",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="r1",
        )
        write_batch_session(
            self.batches,
            "base-r2",
            status="fail",
            criteria={"AC-1": "fail"},
            revision="r2",
        )
        write_batch_manifest(
            self.batches, "base", ["sessions/base-r1", "sessions/base-r2"]
        )
        write_batch_session(
            self.batches,
            "cand-r1",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="r1",
        )
        write_batch_manifest(self.batches, "cand", ["sessions/cand-r1"])

        code, stdout, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "--json"
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(
            payload["warnings"],
            [
                "baseline: birden fazla revision (r1, r2); "
                "--revision <hash> ile daralt"
            ],
        )
        # Both revisions are still counted, but never silently: the warning names them.
        self.assertEqual(payload["baseline"]["sessions"], 2)
        self.assertEqual(payload["baseline"]["criteria"]["AC-1"]["judged"], 2)
        self.assertEqual(payload["baseline"]["criteria"]["AC-1"]["value"], 0.5)

        code, text, _ = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand"
        )
        self.assertEqual(code, 0)
        self.assertIn("birden fazla revision (r1, r2)", text)
        self.assertIn("--revision <hash> ile daralt", text)

        code, stdout, _ = self.run_compare(
            "--baseline",
            "batch=base",
            "--candidate",
            "batch=cand",
            "--revision",
            "r1",
            "--json",
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["baseline"]["sessions"], 1)
        self.assertEqual(payload["baseline"]["criteria"]["AC-1"]["value"], 1.0)
        self.assertFalse(
            any("birden fazla revision" in warning for warning in payload["warnings"])
        )

    def test_t6_empty_side_is_no_match_without_invented_zeros(self) -> None:
        write_batch_session(
            self.batches, "base-ok", status="pass", criteria={"AC-1": "pass"}
        )
        write_batch_manifest(self.batches, "base", ["sessions/base-ok"])
        write_batch_manifest(self.batches, "cand", [])

        code, stdout, errors = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "--json"
        )
        self.assertEqual(code, 1)
        self.assertIn("eşleşme yok: candidate", errors)
        payload = json.loads(stdout)
        self.assertEqual(
            payload,
            {
                "mode": "compare",
                "status": "no-match",
                "side": "candidate",
                "error": "eşleşme yok",
            },
        )
        self.assertNotIn("pass_rate", payload)
        self.assertNotIn("delta", payload)

        # Text mode reports the same and prints no invented metrics.
        code, stdout, errors = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand"
        )
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("eşleşme yok: candidate", errors)

        # The other side being empty is reported symmetrically.
        write_batch_manifest(self.batches, "base", [])
        code, stdout, errors = self.run_compare(
            "--baseline", "batch=base", "--candidate", "batch=cand", "--json"
        )
        self.assertEqual(code, 1)
        self.assertIn("eşleşme yok: baseline", errors)
        self.assertEqual(json.loads(stdout)["side"], "baseline")

        # A revision filter that empties a side is also a no-match.
        write_batch_session(
            self.batches,
            "base-r1",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="r1",
        )
        write_batch_session(
            self.batches,
            "cand-r1",
            status="pass",
            criteria={"AC-1": "pass"},
            revision="r1",
        )
        write_batch_manifest(self.batches, "base", ["sessions/base-r1"])
        write_batch_manifest(self.batches, "cand", ["sessions/cand-r1"])
        code, stdout, errors = self.run_compare(
            "--baseline",
            "batch=base",
            "--candidate",
            "batch=cand",
            "--revision",
            "r2",
            "--json",
        )
        self.assertEqual(code, 1)
        self.assertIn("eşleşme yok: baseline", errors)
        payload = json.loads(stdout)
        self.assertEqual(payload["status"], "no-match")
        self.assertNotIn("pass_rate", payload)


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
