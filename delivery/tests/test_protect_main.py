"""Tests for main branch protection script."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "delivery" / "scripts" / "protect_main.sh"

GOOD = {
    "required_status_checks": {"strict": True, "contexts": ["delivery-doctor"]},
    "enforce_admins": {"enabled": True},
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
    "required_pull_request_reviews": {"required_approving_review_count": 0},
}


def run_check(payload: dict) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        fixture = root / "fixture.json"
        fixture.write_text(json.dumps(payload), encoding="utf-8")
        gh = root / "gh"
        gh.write_text('#!/bin/sh\ncat "$FIXTURE"\n', encoding="utf-8")
        gh.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{root}:{env['PATH']}"
        env["REPO"] = "owner/repo"
        env["FIXTURE"] = str(fixture)
        return subprocess.run(
            [str(SCRIPT), "--check"],
            capture_output=True,
            text=True,
            env=env,
        )


class ProtectMainTests(unittest.TestCase):
    def test_script_contains_protection(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        for needle in (
            "required_status_checks",
            "delivery-doctor",
            '"enforce_admins": true',
            '"allow_force_pushes": false',
            '"allow_deletions": false',
            "required_pull_request_reviews",
        ):
            self.assertIn(needle, text)

    def test_check_passes_for_full_protection(self) -> None:
        result = run_check(GOOD)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_fails_without_pr_gate(self) -> None:
        payload = dict(GOOD)
        payload["required_pull_request_reviews"] = None
        result = run_check(payload)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PR zorunlu", result.stderr)

    def test_check_fails_with_admin_bypass(self) -> None:
        payload = dict(GOOD)
        payload["enforce_admins"] = {"enabled": False}
        result = run_check(payload)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("admin bypass", result.stderr)


if __name__ == "__main__":
    unittest.main()
