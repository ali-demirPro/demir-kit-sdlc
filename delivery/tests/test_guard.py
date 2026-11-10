"""Tests for the G1 guard's approval-digest binding."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("approvals", SCRIPTS / "approvals.py")
approvals = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(approvals)

BODY = """## Neden

Onay digest'i gerekli.

```yaml demir-kit
demir_kit_version: "2"
package_version: 4
epic: 292
intent: Onay digest'i testi.
risk: {level: medium, reasons: [test]}
```
"""


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def write_gh(directory: Path, body_file: Path, comments_file: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "gh"
    script.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f'  *"/comments"*) cat {shlex.quote(str(comments_file))} ;;\n'
        '  *"--json labels"*) echo agent-approved ;;\n'
        f'  *"--json body"*) cat {shlex.quote(str(body_file))} ;;\n'
        '  *"issue comment"*) exit 0 ;;\n'
        '  *) echo "" ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return directory


class GuardBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="guard-binding-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        (self.root / "ecosystem.yaml").write_text(
            "tracker:\n  provider: github\n  repo: owner/repo\nproducts: {}\n",
            encoding="utf-8",
        )
        (self.root / "kit.config.yaml").write_text(
            "kit:\n  root: '.'\nfactory:\n  app_paths: [src]\n", encoding="utf-8"
        )
        git(self.root, "init", "-q")
        git(self.root, "checkout", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        (self.root / "src").mkdir()
        (self.root / "src" / "app.ts").write_text("after\n", encoding="utf-8")

        self.body_file = Path(self.tmp.name) / "body.md"
        self.body_file.write_text(BODY, encoding="utf-8")
        self.comments_file = Path(self.tmp.name) / "comments.json"
        self.stub = Path(self.tmp.name) / "bin"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def accept(self, digest: str) -> dict:
        body = (
            "```yaml demir-kit-accept\n"
            'demir_kit_version: "2"\n'
            "issue: 7\n"
            "by: human\n"
            "decision: accepted\n"
            f"binding_sha256: {digest}\n"
            "```\n"
        )
        return {
            "body": body,
            "user": {"login": "human"},
            "author_association": "MEMBER",
        }

    def run_guard(self, digest: str | None) -> subprocess.CompletedProcess:
        suffix = []
        if digest is not None:
            suffix = [self.accept(digest)]
        self.comments_file.write_text(json.dumps(suffix), encoding="utf-8")
        write_gh(self.stub, self.body_file, self.comments_file)
        env = dict(os.environ)
        env["PATH"] = f"{self.stub}{os.pathsep}{env.get('PATH', '')}"
        return subprocess.run(
            [
                "bash",
                str(SCRIPTS / "guard.sh"),
                "--issue",
                "7",
                "--degrade",
                "--reason",
                "test",
            ],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
        )

    def current_digest(self) -> str:
        files = approvals.changed_files(self.root)
        return approvals.binding_digest(BODY, files)

    def test_matching_digest_keeps_current_behaviour(self) -> None:
        result = self.run_guard(self.current_digest())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("guard: OK", result.stdout)

    def test_mismatched_digest_blocks_source_write(self) -> None:
        stale = approvals.binding_digest(BODY, ["src/nothing.ts"])
        result = self.run_guard(stale)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)
        self.assertIn("digest", result.stderr)

    def test_legacy_accept_without_digest_still_passes(self) -> None:
        result = self.run_guard(None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("guard: OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
