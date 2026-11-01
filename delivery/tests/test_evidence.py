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


def bare_remote_fixture(base: Path) -> tuple[Path, Path, str]:
    """A clone missing the newest commit, its source repo and that commit.

    The bare remote enables SHA fetch like GitHub does, so `fetch_commit` can be
    tested end to end.
    """
    origin = base / "origin.git"
    source = base / "source"
    clone = base / "clone"
    subprocess.check_call(["git", "init", "--bare", "-q", str(origin)])
    git(["config", "uploadpack.allowAnySHA1InWant", "true"], origin)
    source.mkdir()
    make_repo(source)
    git(["remote", "add", "origin", str(origin)], source)
    git(["push", "-q", "origin", "HEAD:main"], source)
    subprocess.check_call(["git", "clone", "-q", str(origin), str(clone)])
    (source / "file.txt").write_text("three\n")
    git(["add", "file.txt"], source)
    git(["commit", "-q", "-m", "three"], source)
    git(["push", "-q", "origin", "HEAD:main"], source)
    return clone, source, git(["rev-parse", "HEAD"], source)


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

    def test_remote_commit_satisfies_missing_local_commit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            clone, source, new = bare_remote_fixture(Path(raw))
            self.assertFalse(evidence.commit_exists(new, clone))
            record = self.record(
                commit=new,
                diff_hash=evidence.diff_hash(new, source),
                reviewers=[reviewer("ses_reviewer", evidence.diff_hash(new, source))],
            )
            errors = evidence.verify(
                record, root=clone, repo="org/repo", risk="low"
            )
            self.assertEqual(errors, [])
            self.assertTrue(evidence.commit_exists(new, clone))

    def test_fetched_commit_still_checks_diff_hash(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            clone, source, new = bare_remote_fixture(Path(raw))
            wrong = "sha256:" + "0" * 64
            record = self.record(
                commit=new, diff_hash=wrong, reviewers=[reviewer("ses_reviewer", wrong)]
            )
            errors = evidence.verify(
                record, root=clone, repo="org/repo", risk="low"
            )
        self.assertTrue(any("eşleşmiyor" in item for item in errors), errors)

    def test_missing_commit_everywhere_fails(self) -> None:
        record = self.record(commit="b" * 40)
        with patch.object(evidence, "fetch_commit", return_value=False):
            errors = evidence.verify(
                record, root=self.root, repo="org/repo", risk="low"
            )
        self.assertTrue(any("commit bulunamadı" in item for item in errors), errors)

    def test_missing_commit_without_repo_fails(self) -> None:
        record = self.record(commit="c" * 40)
        with patch.object(evidence, "fetch_commit") as fetch:
            errors = evidence.verify(record, root=self.root, risk="low")
            fetch.assert_not_called()
        self.assertTrue(any("commit bulunamadı" in item for item in errors), errors)

    def test_fetch_commit_rejects_non_commit_input(self) -> None:
        self.assertFalse(evidence.fetch_commit("not-a-sha", self.root))

    def test_fetch_commit_from_origin(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            clone, source, new = bare_remote_fixture(Path(raw))
            self.assertFalse(evidence.commit_exists(new, clone))
            self.assertTrue(evidence.fetch_commit(new, clone))
            self.assertTrue(evidence.commit_exists(new, clone))
            self.assertEqual(
                evidence.diff_hash(new, clone), evidence.diff_hash(new, source)
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

    def refactor_block(self, **overrides) -> dict:
        block = {
            "baseline": {"commit": self.first, "tests": "pass"},
            "after": {"commit": self.second, "tests": "pass"},
            "unchanged": True,
            "files_changed": 4,
        }
        block.update(overrides)
        return block

    def test_refactor_block_passes(self) -> None:
        errors = evidence.verify_refactor(self.refactor_block(), root=self.root)
        self.assertEqual(errors, [])

    def test_refactor_requires_unchanged_true(self) -> None:
        errors = evidence.verify_refactor(
            self.refactor_block(unchanged=False), root=self.root
        )
        self.assertTrue(any("unchanged" in item for item in errors), errors)

    def test_refactor_baseline_must_be_ancestor(self) -> None:
        block = self.refactor_block(
            baseline={"commit": self.second, "tests": "pass"},
            after={"commit": self.first, "tests": "pass"},
        )
        errors = evidence.verify_refactor(block, root=self.root)
        self.assertTrue(any("atası değil" in item for item in errors), errors)

    def test_refactor_baseline_and_after_differ(self) -> None:
        block = self.refactor_block(
            baseline={"commit": self.second, "tests": "pass"},
            after={"commit": self.second, "tests": "pass"},
        )
        errors = evidence.verify_refactor(block, root=self.root)
        self.assertTrue(any("aynı commit" in item for item in errors), errors)

    def test_refactor_tests_must_pass(self) -> None:
        block = self.refactor_block(
            after={"commit": self.second, "tests": "fail"}
        )
        errors = evidence.verify_refactor(block, root=self.root)
        self.assertTrue(any("tests pass" in item for item in errors), errors)

    def test_refactor_file_limit(self) -> None:
        errors = evidence.verify_refactor(
            self.refactor_block(files_changed=21), root=self.root
        )
        self.assertTrue(any("üst sınır" in item for item in errors), errors)

    def test_refactor_ui_unchanged_needs_equal_hashes(self) -> None:
        hashes = "sha256:" + "a" * 64
        same = self.refactor_block(
            ui_unchanged=True,
            baseline={"commit": self.first, "tests": "pass", "snapshots": hashes},
            after={"commit": self.second, "tests": "pass", "snapshots": hashes},
        )
        self.assertEqual(evidence.verify_refactor(same, root=self.root), [])
        different = self.refactor_block(
            ui_unchanged=True,
            baseline={"commit": self.first, "tests": "pass", "snapshots": hashes},
            after={
                "commit": self.second,
                "tests": "pass",
                "snapshots": "sha256:" + "b" * 64,
            },
        )
        errors = evidence.verify_refactor(different, root=self.root)
        self.assertTrue(any("snapshot" in item for item in errors), errors)

    def test_refactor_ui_unchanged_needs_hashes(self) -> None:
        block = self.refactor_block(ui_unchanged=True)
        errors = evidence.verify_refactor(block, root=self.root)
        self.assertTrue(any("snapshot hash gerekli" in item for item in errors), errors)

    def test_verify_runs_refactor_rules(self) -> None:
        record = self.record(refactor=self.refactor_block(unchanged=False))
        errors = evidence.verify(record, root=self.root, risk="low")
        self.assertTrue(any("unchanged" in item for item in errors), errors)


if __name__ == "__main__":
    unittest.main()
