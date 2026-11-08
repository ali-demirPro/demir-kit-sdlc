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
            ok, message = transition.push_branch(ROOT)
        self.assertTrue(ok)
        self.assertIn("push", calls[-1])
        self.assertEqual(calls[-1][:4], ["git", "push", "-u", "origin"])

    def test_failed_push_is_reported(self) -> None:
        def fake(args, **kwargs):
            if "rev-parse" in args:
                return result(0, "epic-246\n")
            return result(1, "", "remote: denied")

        with mock.patch("subprocess.run", side_effect=fake):
            ok, message = transition.push_branch(ROOT)
        self.assertFalse(ok)
        self.assertIn("denied", message)

    def test_main_branch_is_skipped(self) -> None:
        calls = []

        def fake(args, **kwargs):
            calls.append(args)
            return result(0, "main\n")

        with mock.patch("subprocess.run", side_effect=fake):
            ok, _ = transition.push_branch(ROOT)
        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
