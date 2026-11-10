"""Tests for the seal lint."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "seal_lint", SCRIPTS / "seal_lint.py"
)
seal_lint = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(seal_lint)


def seal(
    ac_text: str = "Komut exit 0 döner.",
    case_text: str = "doctor testi çalışır",
    case_id: str = "T-1",
    ac_ref: str = "AC-1",
    cp_id: str = "CP-1",
) -> dict:
    return {
        "acceptance_criteria": [{"id": "AC-1", "text": ac_text}],
        "tests_plan": [
            {
                "checkpoint_id": cp_id,
                "cases": [
                    {"id": case_id, "ac": ac_ref, "text": case_text, "check": "unit"}
                ],
            }
        ],
        "checkpoints": [{"id": "CP-1", "title": "CP"}],
    }


class SealLintTests(unittest.TestCase):
    def test_clean_seal(self) -> None:
        self.assertEqual(seal_lint.lint(seal()), [])

    def test_vague_acceptance(self) -> None:
        findings = seal_lint.lint(seal(ac_text="Sistem daha iyi olur"))
        self.assertTrue(any(item["severity"] == "warning" for item in findings))

    def test_vague_acceptance_with_punctuation(self) -> None:
        findings = seal_lint.lint(seal(ac_text="Sistem daha iyi olur."))
        self.assertTrue(any(item["severity"] == "warning" for item in findings))

    def test_case_with_generic_test_word_is_weak(self) -> None:
        findings = seal_lint.lint(seal(case_text="kontrol test edilir"))
        self.assertTrue(
            any("çalıştırılabilir" in item["message"] for item in findings)
        )

    def test_plugin_test_trace_is_accepted(self) -> None:
        findings = seal_lint.lint(
            seal(case_text="plugins/orca/src/panel.check.ts: panel çizilir")
        )
        self.assertEqual(findings, [])
        findings = seal_lint.lint(
            seal(case_text="panel testi `orca plugin test plugins/orca` ile koşar")
        )
        self.assertEqual(findings, [])

    def test_finding_paths_are_nested(self) -> None:
        data = seal()
        data["tests_plan"].append(
            {
                "checkpoint_id": "CP-1",
                "cases": [{"id": "T-1", "ac": "AC-1", "text": "x", "check": "unit"}],
            }
        )
        findings = seal_lint.lint(data)
        self.assertTrue(
            any("$.tests_plan[1].cases[0].id" == item["path"] for item in findings)
        )

    def test_missing_observable_is_flagged(self) -> None:
        findings = seal_lint.lint(seal(ac_text="Sistem hazırdır."))
        self.assertTrue(
            any("gözlenebilir" in item["message"] for item in findings)
        )

    def test_vague_word_with_observable_is_flagged(self) -> None:
        findings = seal_lint.lint(seal(ac_text="Test hızlı olur."))
        self.assertTrue(
            any("belirsiz" in item["message"] for item in findings)
        )

    def test_word_boundary_avoids_false_vague(self) -> None:
        findings = seal_lint.lint(
            seal(ac_text="Test exit 0 ile doğrulama sağlar.")
        )
        self.assertFalse(any("belirsiz" in item["message"] for item in findings))

    def test_gate_case_with_generic_word_is_weak(self) -> None:
        data = seal()
        data["tests_plan"][0]["cases"][0]["check"] = "gate"
        data["tests_plan"][0]["cases"][0]["text"] = "gate testi"
        findings = seal_lint.lint(data)
        self.assertTrue(
            any("çalıştırılabilir" in item["message"] for item in findings)
        )

    def test_non_dict_plan_does_not_crash(self) -> None:
        data = seal()
        data["tests_plan"].append("bozuk")
        self.assertIsInstance(seal_lint.lint(data), list)

    def test_slash_is_not_an_observable_marker(self) -> None:
        findings = seal_lint.lint(seal(ac_text="Sistem hata/uyari uretir."))
        self.assertTrue(
            any("gözlenebilir" in item["message"] for item in findings)
        )
        weak = seal_lint.lint(seal(case_text="hata/uyari davranisi"))
        self.assertTrue(
            any("çalıştırılabilir" in item["message"] for item in weak)
        )

    def test_python_unittest_marker(self) -> None:
        findings = seal_lint.lint(
            seal(case_text="python3 -m unittest discover çalışır")
        )
        self.assertFalse(
            any("çalıştırılabilir" in item["message"] for item in findings)
        )

    def test_weak_unit_case(self) -> None:
        findings = seal_lint.lint(seal(case_text="kontrol edilir"))
        self.assertTrue(
            any("çalıştırılabilir" in item["message"] for item in findings)
        )

    def test_duplicate_and_unknown_refs(self) -> None:
        data = seal()
        data["tests_plan"][0]["cases"].append(
            {"id": "T-1", "ac": "AC-9", "text": "test", "check": "unit"}
        )
        findings = seal_lint.lint(data)
        messages = " ".join(item["message"] for item in findings)
        self.assertIn("tekrarlı case", messages)
        self.assertIn("bilinmeyen AC", messages)

        data = seal(cp_id="CP-9")
        self.assertTrue(
            any("bilinmeyen CP" in item["message"] for item in seal_lint.lint(data))
        )

    def test_cli_json_and_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "leaf.md"
            body = seal()
            path.write_text(
                "```yaml demir-kit\n"
                + json.dumps(body)
                + "\n```\n",
                encoding="utf-8",
            )
            out = io.StringIO()
            with patch.object(sys, "argv", ["seal_lint.py", "--body", str(path), "--json"]):
                with redirect_stdout(out):
                    self.assertEqual(seal_lint.main(), 0)
            self.assertIn("findings", json.loads(out.getvalue()))

            body["acceptance_criteria"][0]["text"] = "daha iyi"
            path.write_text(
                "```yaml demir-kit\n" + json.dumps(body) + "\n```\n",
                encoding="utf-8",
            )
            with patch.object(
                sys, "argv", ["seal_lint.py", "--body", str(path)]
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(seal_lint.main(), 0)
            with patch.object(
                sys, "argv", ["seal_lint.py", "--body", str(path), "--strict"]
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(seal_lint.main(), 1)

            body["tests_plan"][0]["cases"].append(
                {"id": "T-1", "ac": "AC-1", "text": "x", "check": "unit"}
            )
            path.write_text(
                "```yaml demir-kit\n" + json.dumps(body) + "\n```\n",
                encoding="utf-8",
            )
            with patch.object(
                sys, "argv", ["seal_lint.py", "--body", str(path)]
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(seal_lint.main(), 1)


class DoctorWiringTests(unittest.TestCase):
    BODY = """```yaml demir-kit
demir_kit_version: "2"
package_version: 4
mode: extend
epic: 1
entry: {kind: feature}
factory: {profile: kit-internal}
intent: seal lint entegrasyon testi
surfaces: [kit.docs]
reference: {kind: github_paths, summary: referans dokuman, paths: [delivery/CONTRACT.md]}
acceptance_criteria: [{id: AC-1, text: kabul kriteri metni}]
out_of_scope: [kapsam disi]
risk: {level: low}
tests_plan:
  - checkpoint_id: CP-1
    cases: [{id: T-1, ac: AC-1, text: test metni, check: unit}]
checkpoints:
  - {id: CP-1, title: birinci, gates: {behavior: true}}
```
"""

    def test_error_and_warning_are_wired(self) -> None:
        import doctor

        doctor.ERRORS.clear()
        doctor.WARNS.clear()
        with patch.object(
            doctor.seal_lint,
            "lint",
            return_value=[{"severity": "error", "path": "$", "message": "hata"}],
        ):
            doctor.check_issue_body(self.BODY, [], None, root=doctor.ROOT)
        self.assertTrue(any("seal lint" in item for item in doctor.ERRORS))

        doctor.ERRORS.clear()
        doctor.WARNS.clear()
        with patch.object(
            doctor.seal_lint,
            "lint",
            return_value=[{"severity": "warning", "path": "$", "message": "uyarı"}],
        ):
            doctor.check_issue_body(self.BODY, [], None, root=doctor.ROOT)
        self.assertTrue(any("seal lint" in item for item in doctor.WARNS))


if __name__ == "__main__":
    unittest.main()
