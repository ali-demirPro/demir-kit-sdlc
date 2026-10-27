"""Tests for read-only adaptation verification."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("verify", SCRIPTS / "verify.py")
verify = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(verify)


def write(root: Path, name: str, text: str = "") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def web_api_project(root: Path) -> None:
    write(
        root,
        "package.json",
        json.dumps(
            {
                "dependencies": {"next": "1", "react": "1", "express": "1"},
                "scripts": {"test": "vitest", "lint": "eslint ."},
            }
        ),
    )
    write(root, "src/auth/login.ts", "export default 1\n")
    write(root, "api/main.ts", "export default 1\n")
    write(root, "vercel.json", "{}")


def ios_project(root: Path) -> None:
    write(root, "Package.swift", "// swift-tools-version: 5.9\nimport SwiftUI\n")
    (root / "ios" / "App.xcodeproj").mkdir(parents=True)
    write(root, "fastlane/Fastfile", "app_store\n")


def flutter_project(root: Path) -> None:
    write(
        root,
        "pubspec.yaml",
        "name: app\nenvironment:\n  sdk: flutter\nflutter:\n  uses-material-design: true\n",
    )
    (root / "ios").mkdir()
    (root / "android").mkdir()
    write(root, "lib/main.dart", "void main() {}\n")
    write(root, "vercel.json", "{}")


class VerifyTests(unittest.TestCase):
    def test_web_api_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_api_project(root)
            report = verify.verify_project(root)
            self.assertTrue(report["ok"], report["issues"])
            self.assertEqual(
                report["profiles"], ["web-app", "api-service", "auth"]
            )
            self.assertIn("domain.auth", report["capabilities"])
            self.assertEqual({item["name"] for item in report["surfaces"]}, {"web", "api"})

    def test_ios_store_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ios_project(root)
            report = verify.verify_project(root)
            self.assertTrue(report["ok"], report["issues"])
            self.assertEqual(report["profiles"], ["ios-app"])
            self.assertIn("distribution.app_store", report["capabilities"])

    def test_flutter_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flutter_project(root)
            report = verify.verify_project(root)
            self.assertTrue(report["ok"], report["issues"])
            self.assertEqual(report["profiles"], ["flutter-app"])
            self.assertIn("platform.ios", report["capabilities"])
            self.assertIn("platform.android", report["capabilities"])

    def test_empty_project_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = verify.verify_project(Path(directory))
            self.assertFalse(report["ok"])
            self.assertTrue(any("yüzey" in item for item in report["issues"]))

    def test_verify_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_api_project(root)
            before = sorted(
                (str(path.relative_to(root)), path.stat().st_mtime_ns)
                for path in root.rglob("*")
            )
            verify.verify_project(root)
            after = sorted(
                (str(path.relative_to(root)), path.stat().st_mtime_ns)
                for path in root.rglob("*")
            )
            self.assertEqual(before, after)
            self.assertFalse((root / "AGENTS.md").exists())

    def test_existing_declarations_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_api_project(root)
            write(
                root,
                "kit.config.yaml",
                "kit:\n  protocol: \"2\"\n"
                "factory:\n  default_profile: auth\n  profiles: [auth]\n",
            )
            write(
                root,
                ".kit/capabilities.yaml",
                "version: 1\ninclude: [platform.ghost]\nexclude: []\n",
            )
            report = verify.verify_project(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any("base" in item for item in report["issues"]))
            self.assertTrue(
                any("platform.ghost" in item for item in report["issues"])
            )
            self.assertEqual(report["configured"]["profiles"], ["auth"])
            self.assertTrue(report["configured"]["capabilities_file"])

    def test_existing_valid_declarations_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_api_project(root)
            write(
                root,
                "kit.config.yaml",
                "kit:\n  protocol: \"2\"\n"
                "factory:\n  default_profile: web-app\n"
                "  profiles: [web-app, auth]\n",
            )
            write(
                root,
                ".kit/capabilities.yaml",
                "version: 1\ninclude: [platform.web]\nexclude: []\n",
            )
            report = verify.verify_project(root)
            self.assertTrue(report["ok"], report["issues"])
            self.assertEqual(report["configured"]["profiles"], ["web-app", "auth"])

    def test_check_plan_rejects_bad_shapes(self) -> None:
        known = verify.known_capabilities()
        base = {
            "fingerprint": {"surfaces": [{"name": "web", "platforms": ["web"]}]},
            "profiles": ["web-app"],
            "profile": "web-app",
            "capabilities": ["platform.web"],
        }
        self.assertEqual(verify.check_plan(base, known), [])
        for override, expected in (
            ({"fingerprint": {"surfaces": []}}, "yüzey"),
            ({"profile": "api-service"}, "default"),
            ({"profiles": ["auth"], "profile": "auth"}, "base"),
            ({"profiles": ["ghost"], "profile": "ghost"}, "profil yok"),
            ({"capabilities": ["platform.ghost"]}, "capability"),
        ):
            plan = {**base, **override}
            self.assertTrue(
                any(expected in item for item in verify.check_plan(plan, known)),
                (override, verify.check_plan(plan, known)),
            )

    def test_multi_project_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "web"
            second = root / "ios"
            web_api_project(first)
            ios_project(second)
            argv = [
                "verify.py",
                "--project",
                str(first),
                "--project",
                str(second),
                "--json",
            ]
            output = io.StringIO()
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
                self.assertEqual(verify.main(), 0)
            data = json.loads(output.getvalue())
            self.assertEqual([item["ok"] for item in data], [True, True])
            self.assertEqual(len(data), 2)

    def test_cli_failure_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            argv = ["verify.py", "--project", directory, "--json"]
            output = io.StringIO()
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
                self.assertEqual(verify.main(), 1)
            self.assertFalse(json.loads(output.getvalue())[0]["ok"])


if __name__ == "__main__":
    unittest.main()
