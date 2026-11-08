"""Tests for pushing the epic branch before leaf-done."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("transition_push", SCRIPTS / "transition.py")
transition = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(transition)


def result(code: int, out: str = "", err: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], code, out, err)


class PushTests(unittest.TestCase):
    def test_main_and_detached_need_no_push(self) -> None:
        for branch in ("main", "master", "HEAD", ""):
            self.assertFalse(transition.push_needed(branch))
        self.assertTrue(transition.push_needed("ali-demirPro/epic-246"))

    def test_successful_push(self) -> None:
        calls = []

        def fake(args, **kwargs):
            calls.append(args)
            if "rev-parse" in args:
                return result(0, "ali-demirPro/epic-246\n")
            return result(0, "", "pushed")

        with mock.patch("subprocess.run", side_effect=fake):
            status, message = transition.push_branch(ROOT)
        self.assertEqual(status, "pushed")
        self.assertIn("push", calls[-1])
        self.assertEqual(calls[-1][:4], ["git", "push", "-u", "origin"])

    def test_failed_push_is_reported(self) -> None:
        def fake(args, **kwargs):
            if "rev-parse" in args:
                return result(0, "epic-246\n")
            if "status" in args:
                return result(0, "")
            return result(1, "", "remote: denied")

        with mock.patch("subprocess.run", side_effect=fake):
            status, message = transition.push_branch(ROOT)
        self.assertEqual(status, "failed")
        self.assertIn("denied", message)

    def test_main_branch_is_skipped(self) -> None:
        calls = []

        def fake(args, **kwargs):
            calls.append(args)
            return result(0, "main\n")

        with mock.patch("subprocess.run", side_effect=fake):
            status, message = transition.push_branch(ROOT)
        self.assertEqual(status, "skipped")
        self.assertIn("push edilmez", message)
        self.assertEqual(len(calls), 1)

    def test_dirty_tree_blocks_the_push(self) -> None:
        calls = []

        def fake(args, **kwargs):
            calls.append(args)
            if "rev-parse" in args:
                return result(0, "epic-246\n")
            if "status" in args:
                return result(0, " M delivery/scripts/gate.py\n")
            return result(0, "", "pushed")

        with mock.patch("subprocess.run", side_effect=fake):
            status, message = transition.push_branch(ROOT)
        self.assertEqual(status, "failed")
        self.assertIn("kirli", message)
        self.assertFalse(any("push" in call for call in calls))


class CheckPushTests(unittest.TestCase):
    def args(self, **overrides):
        base = mock.Mock(issue=268, no_push=False, reason="")
        for key, value in overrides.items():
            setattr(base, key, value)
        return base

    def test_skipped_push_requires_a_recorded_reason(self) -> None:
        with mock.patch.object(transition, "push_branch", return_value=("skipped", "dal main")), \
             mock.patch.object(transition, "post_comment"):
            with self.assertRaises(SystemExit):
                transition.check_push(self.args())

    def test_skipped_push_with_reason_writes_degrade(self) -> None:
        with mock.patch.object(transition, "push_branch", return_value=("skipped", "dal main")), \
             mock.patch.object(transition, "post_comment") as post:
            transition.check_push(self.args(reason="epic PR sonrasi"))
        self.assertIn("run degrade: issue #268", post.call_args[0][1])
        self.assertIn("push atlandı", post.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
