"""Tests for the one-step checkpoint close."""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("cp_close", SCRIPTS / "cp_close.py")
cp_close = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cp_close)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64

VERIFICATION = {
    "commit": "abcdef1",
    "diff_hash": HASH_A,
    "ci": {"status": "skipped", "reason": "yerel kapı"},
    "reviewers": [
        {
            "role": "adversarial",
            "id": "ses_reviewer",
            "model": "test/model",
            "prompt_hash": HASH_B,
            "diff_hash": HASH_A,
        }
    ],
}

RECORD = {
    "demir_kit_version": "2",
    "cp_id": "CP-1",
    "issue": 148,
    "agent": "developer",
    "behavior": {"command": "gate", "exit_code": 0},
    "reviews": {
        "adversarial": {"reviewer_a": "approved"},
        "risk": "medium",
    },
    "tests": [{"case": "T-1", "result": "pass"}],
    "verification": VERIFICATION,
    "status": "pass",
}


def run_main(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with patch.object(cp_close, "repo_name", return_value="o/r"), patch.object(
        cp_close, "issue_payload", return_value={"body": "x"}
    ), patch.object(cp_close, "risk_of", return_value="medium"), patch.object(
        cp_close, "load_evidence", return_value=RECORD
    ), patch.object(cp_close, "validate_record", return_value=[]), patch.object(
        cp_close, "gate_command", return_value="gate"
    ), patch.object(sys, "argv", ["cp_close.py", *argv]), redirect_stdout(
        out
    ), redirect_stderr(err):
        code = cp_close.main()
    return code, out.getvalue(), err.getvalue()


class CpCloseTests(unittest.TestCase):
    def test_dry_run_does_not_write(self) -> None:
        with patch.object(cp_close, "run_gate") as gate, patch.object(
            cp_close, "post_comment"
        ) as post:
            code, out, _ = run_main(["--issue", "148", "--cp", "CP-1", "--evidence", "e"])
        self.assertEqual(code, 0)
        self.assertIn("CP close planı", out)
        gate.assert_not_called()
        post.assert_not_called()

    def test_apply_runs_gate_post_verify_checkpoint(self) -> None:
        calls: list[str] = []
        with patch.object(
            cp_close, "run_gate", side_effect=lambda c: (calls.append("gate"), (0, ""))[1]
        ), patch.object(
            cp_close, "post_comment",
            side_effect=lambda *a: (calls.append("post"), "c1")[1],
        ), patch.object(
            cp_close, "verify_issue",
            side_effect=lambda i, e: (calls.append("verify"), (0, ""))[1],
        ), patch.object(
            cp_close, "checkpoint",
            side_effect=lambda *a: (calls.append("checkpoint"), True)[1],
        ):
            code, out, _ = run_main(
                ["--issue", "148", "--cp", "CP-1", "--evidence", "e", "--apply"]
            )
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["gate", "post", "verify", "checkpoint"])
        self.assertIn("CP kapandı", out)

    def test_gate_failure_does_not_post(self) -> None:
        with patch.object(cp_close, "run_gate", return_value=(1, "kırmızı")), patch.object(
            cp_close, "post_comment"
        ) as post:
            code, _, err = run_main(
                ["--issue", "148", "--cp", "CP-1", "--evidence", "e", "--apply"]
            )
        self.assertEqual(code, 1)
        post.assert_not_called()
        self.assertIn("gate düştü", err)

    def test_verify_failure_rolls_back(self) -> None:
        with patch.object(cp_close, "run_gate", return_value=(0, "")), patch.object(
            cp_close, "post_comment", return_value="c1"
        ), patch.object(cp_close, "verify_issue", return_value=(1, "kırmızı")), patch.object(
            cp_close, "delete_comment"
        ) as delete, patch.object(cp_close, "checkpoint") as checkpoint:
            code, _, err = run_main(
                ["--issue", "148", "--cp", "CP-1", "--evidence", "e", "--apply"]
            )
        self.assertEqual(code, 1)
        delete.assert_called_once_with("o/r", "c1")
        checkpoint.assert_not_called()
        self.assertIn("geri alındı", err)

    def test_comment_body_is_marked(self) -> None:
        import re

        import yaml

        body = cp_close.comment_body(RECORD)
        match = re.search(
            r"```yaml\s+demir-kit-evidence\s*\n(.*?)```", body, re.S
        )
        self.assertIsNotNone(match)
        parsed = yaml.safe_load(match.group(1))
        self.assertEqual(parsed["cp_id"], "CP-1")

    def test_delete_failure_is_reported(self) -> None:
        with patch.object(cp_close, "run_gate", return_value=(0, "")), patch.object(
            cp_close, "post_comment", return_value="c1"
        ), patch.object(cp_close, "verify_issue", return_value=(1, "kırmızı")), patch.object(
            cp_close, "delete_comment", return_value=False
        ), patch.object(cp_close, "checkpoint") as checkpoint:
            code, _, err = run_main(
                ["--issue", "148", "--cp", "CP-1", "--evidence", "e", "--apply"]
            )
        self.assertEqual(code, 1)
        self.assertIn("SİLİNEMEDİ", err)
        checkpoint.assert_not_called()

    def test_checkpoint_failure_does_not_claim_success(self) -> None:
        with patch.object(cp_close, "run_gate", return_value=(0, "")), patch.object(
            cp_close, "post_comment", return_value="c1"
        ), patch.object(cp_close, "verify_issue", return_value=(0, "")), patch.object(
            cp_close, "checkpoint", return_value=False
        ):
            code, out, err = run_main(
                ["--issue", "148", "--cp", "CP-1", "--evidence", "e", "--apply"]
            )
        self.assertEqual(code, 0)
        self.assertIn("checkpoint yazılamadı", err)
        self.assertIn("CP kapandı", out)

    def test_verify_issue_product_mode_uses_evidence(self) -> None:
        import subprocess as sp

        captured = {}

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        def fake_run(command, **kwargs):
            captured["command"] = command
            return Result()

        with patch.object(cp_close.routing, "kit_prefix", return_value="demir-kit/"), patch.object(
            cp_close.routing, "project_root", return_value=Path("/tmp/product")
        ), patch.object(sp, "run", side_effect=fake_run):
            code, _ = cp_close.verify_issue(148, Path("/tmp/e.yaml"))
        self.assertEqual(code, 0)
        command = captured["command"]
        self.assertIn("--evidence", command)
        self.assertIn("--product", command)
        self.assertIn("demir-kit/delivery/scripts/doctor.sh", " ".join(command))

    def test_normalize_evidence_text_wraps_plain_yaml(self) -> None:
        doctor = cp_close.doctor
        wrapped = doctor.normalize_evidence_text("cp_id: CP-1\nstatus: pass\n")
        self.assertTrue(wrapped.startswith("```yaml\ndemir-kit-evidence"))
        fenced = "```yaml\ndemir-kit-evidence\ncp_id: CP-1\n```"
        self.assertEqual(doctor.normalize_evidence_text(fenced), fenced)
        self.assertIsNone(doctor.normalize_evidence_text(None))

    def test_evidence_mode_checks_only_given_cp(self) -> None:
        doctor = cp_close.doctor
        body = """```yaml demir-kit
demir_kit_version: "2"
package_version: 4
mode: extend
epic: 1
entry: {kind: feature}
factory: {profile: kit-internal}
intent: iki checkpointli test leaf
surfaces: [kit.docs]
reference: {kind: github_paths, summary: referans dokuman, paths: [delivery/CONTRACT.md]}
acceptance_criteria: [{id: AC-1, text: kabul kriteri metni}]
out_of_scope: [kapsam disi]
risk: {level: low}
tests_plan:
  - checkpoint_id: CP-1
    cases: [{id: T-1, ac: AC-1, text: test metni, check: doc}]
  - checkpoint_id: CP-2
    cases: [{id: T-2, ac: AC-1, text: test metni, check: doc}]
checkpoints:
  - {id: CP-1, title: birinci, gates: {behavior: true}}
  - {id: CP-2, title: ikinci, gates: {behavior: true}}
```
"""
        evidence = """```yaml
demir-kit-evidence
demir_kit_version: "2"
cp_id: CP-1
issue: 999
agent: developer
behavior: {command: x, exit_code: 0}
reviews: {adversarial: {reviewer_a: skipped}, risk: low}
tests: [{case: T-1, result: pass}]
status: pass
```
"""
        doctor.ERRORS.clear()
        doctor.WARNS.clear()
        doctor.check_issue_body(
            body, ["executing"], None, root=doctor.ROOT, repo=None, evidence_text=evidence
        )
        errors = list(doctor.ERRORS)
        self.assertFalse(any("CP-2 evidence yok" in e for e in errors))
        self.assertTrue(any("reviewer onayı gerekli" in e for e in errors))

    def test_evidence_mode_fails_closed(self) -> None:
        doctor = cp_close.doctor
        body = """```yaml demir-kit
demir_kit_version: "2"
package_version: 4
mode: extend
epic: 1
entry: {kind: feature}
factory: {profile: kit-internal}
intent: iki checkpointli test leaf
surfaces: [kit.docs]
reference: {kind: github_paths, summary: referans dokuman, paths: [delivery/CONTRACT.md]}
acceptance_criteria: [{id: AC-1, text: kabul kriteri metni}]
out_of_scope: [kapsam disi]
risk: {level: low}
tests_plan:
  - checkpoint_id: CP-1
    cases: [{id: T-1, ac: AC-1, text: test metni, check: doc}]
  - checkpoint_id: CP-2
    cases: [{id: T-2, ac: AC-1, text: test metni, check: doc}]
checkpoints:
  - {id: CP-1, title: birinci, gates: {behavior: true}}
  - {id: CP-2, title: ikinci, gates: {behavior: true}}
```
"""
        evidence = """```yaml
demir-kit-evidence
cp_id: CP-1
status: pass
```
"""
        doctor.ERRORS.clear()
        doctor.WARNS.clear()
        doctor.check_issue_body(
            body, ["executing"], None, root=doctor.ROOT, repo=None,
            evidence_text="", checkpoint="CP-1",
        )
        self.assertTrue(any("kayıt bulunamadı" in e for e in doctor.ERRORS))

        doctor.ERRORS.clear()
        doctor.check_issue_body(
            body, ["executing"], None, root=doctor.ROOT, repo=None,
            evidence_text=evidence, checkpoint="CP-2",
        )
        self.assertTrue(
            any("checkpoint CP-2 için kayıt yok" in e for e in doctor.ERRORS)
        )

    def test_load_evidence_fenced_and_plain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "e.md"
            path.write_text(
                "```yaml\ndemir-kit-evidence\ncp_id: CP-1\nstatus: pass\n```\n",
                encoding="utf-8",
            )
            self.assertEqual(cp_close.load_evidence(path)["cp_id"], "CP-1")
            path.write_text("cp_id: CP-2\nstatus: pass\n", encoding="utf-8")
            self.assertEqual(cp_close.load_evidence(path)["cp_id"], "CP-2")

    def test_validate_record_flags_mismatch(self) -> None:
        with patch.object(cp_close.evidence_lib, "verify", return_value=[]):
            self.assertEqual(
                cp_close.validate_record(RECORD, 148, "CP-1", "medium", "o/r"), []
            )
            errors = cp_close.validate_record(RECORD, 149, "CP-2", "medium", "o/r")
        self.assertTrue(any("cp_id" in error for error in errors))
        self.assertTrue(any("issue" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
