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


def write_gh(
    directory: Path,
    body_file: Path,
    comments_file: Path,
    comments_ok: bool = True,
    body_ok: bool = True,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "gh"
    comments = (
        f'cat {shlex.quote(str(comments_file))}'
        if comments_ok
        else "exit 1"
    )
    body = f'cat {shlex.quote(str(body_file))}' if body_ok else "exit 1"
    script.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f'  *"/comments"*) {comments} ;;\n'
        '  *"--json labels"*) echo agent-approved ;;\n'
        f'  *"--json body"*) {body} ;;\n'
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

    def head(self) -> str:
        return subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def accept(self, digest: str, base: str) -> dict:
        body = (
            "```yaml demir-kit-accept\n"
            'demir_kit_version: "2"\n'
            "issue: 7\n"
            "by: human\n"
            "decision: accepted\n"
            f"binding_sha256: {digest}\n"
            f"binding_base: {base}\n"
            "```\n"
        )
        return {
            "body": body,
            "user": {"login": "human"},
            "author_association": "MEMBER",
        }

    def run_guard(
        self,
        digest: str | None,
        base: str | None = None,
        comments_ok: bool = True,
        body_ok: bool = True,
    ) -> subprocess.CompletedProcess:
        suffix = []
        if digest is not None:
            suffix = [self.accept(digest, base or self.head())]
        self.comments_file.write_text(json.dumps(suffix), encoding="utf-8")
        write_gh(
            self.stub,
            self.body_file,
            self.comments_file,
            comments_ok=comments_ok,
            body_ok=body_ok,
        )
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
        return approvals.binding_digest(BODY, self.head())

    def test_matching_digest_keeps_current_behaviour(self) -> None:
        result = self.run_guard(self.current_digest())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("guard: OK", result.stdout)

    def test_mismatched_digest_blocks_source_write(self) -> None:
        body = BODY.replace("Onay digest'i testi.", "Değişmiş seal.")
        stale = approvals.binding_digest(body, self.head())
        result = self.run_guard(stale)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)
        self.assertIn("digest", result.stderr)

    def test_base_not_ancestor_blocks_source_write(self) -> None:
        base = "deadbeef" * 5
        stale = approvals.binding_digest(BODY, base)
        result = self.run_guard(stale, base)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)
        self.assertIn("atası değil", result.stderr)

    def test_legacy_accept_without_digest_still_passes(self) -> None:
        result = self.run_guard(None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("guard: OK", result.stdout)

    def test_comments_api_failure_blocks_fail_closed(self) -> None:
        result = self.run_guard(self.current_digest(), comments_ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)
        self.assertIn("onay yorumları okunamadı", result.stderr)

    def test_seal_body_failure_blocks_fail_closed(self) -> None:
        result = self.run_guard(self.current_digest(), body_ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)
        self.assertIn("seal gövdesi okunamadı", result.stderr)


SEAL_BODY = """## Neden

Capability path allowlist'i sınar.

```yaml demir-kit
demir_kit_version: "2"
package_version: 4
epic: 292
intent: Capability path allowlist'i sınar.
surfaces: [kit.docs]
risk: {level: medium, reasons: [test]}
```
"""


def seal_body(surfaces: str) -> str:
    return SEAL_BODY.replace("surfaces: [kit.docs]", f"surfaces: [{surfaces}]")


class CapabilityScopeTests(unittest.TestCase):
    """Capability glob'ları yazma sınırı: içi geçer, dışı G1 ihlali."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="guard-scope-")
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

        self.body_file = Path(self.tmp.name) / "body.md"
        self.comments_file = Path(self.tmp.name) / "comments.json"
        self.stub = Path(self.tmp.name) / "bin"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def head(self) -> str:
        return subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def run_guard(
        self, body: str, *files: str, issue: bool = True
    ) -> subprocess.CompletedProcess:
        for name in files:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n", encoding="utf-8")
        digest = approvals.binding_digest(body, self.head())
        self.body_file.write_text(body, encoding="utf-8")
        self.comments_file.write_text(
            json.dumps(
                [
                    {
                        "body": (
                            "```yaml demir-kit-accept\n"
                            'demir_kit_version: "2"\n'
                            "issue: 7\n"
                            "by: human\n"
                            "decision: accepted\n"
                            f"binding_sha256: {digest}\n"
                            f"binding_base: {self.head()}\n"
                            "```\n"
                        ),
                        "user": {"login": "human"},
                        "author_association": "MEMBER",
                    }
                ]
            ),
            encoding="utf-8",
        )
        write_gh(self.stub, self.body_file, self.comments_file)
        env = dict(os.environ)
        env["PATH"] = f"{self.stub}{os.pathsep}{env.get('PATH', '')}"
        args = ["bash", str(SCRIPTS / "guard.sh"), "--degrade", "--reason", "test"]
        if issue:
            args += ["--issue", "7"]
        return subprocess.run(
            args, cwd=self.root, env=env, capture_output=True, text=True
        )

    def test_change_outside_capability_globs_blocks(self) -> None:
        result = self.run_guard(SEAL_BODY, "outside/notes.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("capability dışı yazım", result.stderr)
        self.assertIn("kit.docs", result.stderr)
        self.assertIn("delivery/**", result.stderr)
        self.assertIn("outside/notes.py", result.stderr)

    def test_change_inside_capability_globs_passes(self) -> None:
        result = self.run_guard(SEAL_BODY, "delivery/notes.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("guard: OK", result.stdout)

    def test_common_paths_stay_writable(self) -> None:
        result = self.run_guard(SEAL_BODY, "CHANGELOG.md")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_app_paths_still_require_issue(self) -> None:
        result = self.run_guard(SEAL_BODY, "src/app.ts", issue=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uygulama yolu değişti", result.stderr)

    def test_risk_glob_still_escalates(self) -> None:
        result = self.run_guard(SEAL_BODY, "app/auth/login.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("registry high glob'u", result.stderr)

    def test_unknown_surface_keeps_current_behaviour(self) -> None:
        result = self.run_guard(seal_body("unknown.surface"), "outside/notes.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tanımsız surface", result.stderr)


if __name__ == "__main__":
    unittest.main()
