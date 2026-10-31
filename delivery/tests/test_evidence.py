"""Tests for evidence v3 verification."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("evidence", SCRIPTS / "evidence.py")
evidence = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(evidence)


def git(args: list[str], root: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def make_repo(root: Path) -> tuple[str, str]:
    git(["init", "-q"], root)
    git(["config", "user.email", "test@example.com"], root)
    git(["config", "user.name", "Test"], root)
    path = root / "file.txt"
    path.write_text("one\n")
    git(["add", "file.txt"], root)
    git(["commit", "-q", "-m", "one"], root)
    first = git(["rev-parse", "HEAD"], root)
    path.write_text("two\n")
    git(["add", "file.txt"], root)
    git(["commit", "-q", "-m", "two"], root)
    second = git(["rev-parse", "HEAD"], root)
    return first, second


def reviewer(identifier: str, diff_hash: str) -> dict:
    return {
        "role": "adversarial",
        "id": identifier,
        "model": "test-model",
        "prompt_hash": evidence.hash_text("prompt"),
        "diff_hash": diff_hash,
    }


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.first, self.second = make_repo(self.root)
        self.expected = evidence.diff_hash(self.second, self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def record(self, **overrides) -> dict:
        data = {
            "commit": self.second,
            "diff_hash": self.expected,
            "ci": {"status": "skipped", "reason": "unit test"},
            "reviewers": [reviewer("ses_reviewer", self.expected)],
        }
        data.update(overrides)
        return data

    def test_commit_and_diff_hash(self) -> None:
        self.assertTrue(evidence.commit_exists(self.first, self.root))
        self.assertTrue(evidence.diff_hash(self.first, self.root).startswith("sha256:"))
        self.assertNotEqual(
            evidence.diff_hash(self.first, self.root),
            evidence.diff_hash(self.second, self.root),
        )

    def test_valid_verification(self) -> None:
        self.assertEqual(
            evidence.verify(
                self.record(), root=self.root, risk="low", implementer="developer"
            ),
            [],
        )

    def test_diff_mismatch(self) -> None:
        bad = self.record(diff_hash="sha256:" + "0" * 64)
        errors = evidence.verify(bad, root=self.root, risk="low")
        self.assertTrue(any("eşleşmiyor" in item for item in errors))

    def test_duplicate_reviewer(self) -> None:
        bad = self.record(
            reviewers=[
                reviewer("ses_same", self.expected),
                reviewer("ses_same", self.expected),
            ]
        )
        errors = evidence.verify(bad, root=self.root, risk="low")
        self.assertTrue(any("tekrarlı" in item for item in errors))

    def test_implementer_cannot_review(self) -> None:
        bad = self.record(reviewers=[reviewer("developer", self.expected)])
        errors = evidence.verify(
            bad, root=self.root, risk="low", implementer="developer"
        )
        self.assertTrue(any("uygulayıcıyla aynı" in item for item in errors))

    def test_high_risk_needs_two_reviewers_and_local_gate(self) -> None:
        errors = evidence.verify(self.record(), root=self.root, risk="high")
        self.assertTrue(any("en az 2 reviewer" in item for item in errors))
        self.assertTrue(any("yerel kapı" in item for item in errors))

    def test_high_risk_accepts_local_gate(self) -> None:
        record = self.record(
            ci={"status": "skipped", "reason": "yerel imzalı build"},
            local_gate={"command": "xcodebuild test", "exit_code": 0},
            reviewers=[
                reviewer("ses_a", self.expected),
                reviewer("ses_b", self.expected),
            ],
        )
        self.assertEqual(
            evidence.verify(record, root=self.root, risk="high"), []
        )

    def test_critical_risk_rejects_skipped_ci_even_with_local_gate(self) -> None:
        record = self.record(
            ci={"status": "skipped", "reason": "yerel"},
            local_gate={"command": "xcodebuild test", "exit_code": 0},
            reviewers=[
                reviewer("ses_a", self.expected),
                reviewer("ses_b", self.expected),
            ],
        )
        errors = evidence.verify(record, root=self.root, risk="critical")
        self.assertTrue(any("critical için CI skipped" in item for item in errors))

    def test_ci_success_must_match_commit(self) -> None:
        record = self.record(
            ci={"status": "success", "run_id": "123", "url": "https://example/123"}
        )
        with patch.object(
            evidence,
            "ci_status",
            return_value={"head_sha": self.second, "conclusion": "success"},
        ):
            self.assertEqual(
                evidence.verify(record, root=self.root, repo="owner/repo"), []
            )
        with patch.object(
            evidence,
            "ci_status",
            return_value={"head_sha": self.first, "conclusion": "success"},
        ):
            errors = evidence.verify(record, root=self.root, repo="owner/repo")
            self.assertTrue(any("farklı commit" in item for item in errors))

    def test_build_fills_diff_hash(self) -> None:
        data = evidence.build(
            self.second,
            "developer",
            None,
            "unit test",
            [json.dumps(reviewer("ses_reviewer", ""))],
            root=self.root,
        )
        self.assertEqual(data["diff_hash"], self.expected)
        self.assertEqual(data["reviewers"][0]["diff_hash"], self.expected)


if __name__ == "__main__":
    unittest.main()
