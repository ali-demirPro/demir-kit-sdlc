"""Tests for project wiring generation."""

from __future__ import annotations

import importlib.util
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("init", SCRIPTS / "init.py")
init_mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(init_mod)


def write(root: Path, relative: str, text: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def web_project(root: Path) -> None:
    write(
        root,
        "package.json",
        json.dumps(
            {
                "dependencies": {"next": "1", "react": "1"},
                "scripts": {"test": "vitest", "typecheck": "tsc"},
            }
        ),
    )
    write(root, "next.config.js", "module.exports = {}")
    write(root, "src/app/page.tsx", "export default 1")
    write(root, "vercel.json", "{}")


def ios_project(root: Path) -> None:
    write(root, "Package.swift", "// swift-tools-version: 5.9\nimport SwiftUI\n")
    (root / "ios" / "App.xcodeproj").mkdir(parents=True)


class InitTests(unittest.TestCase):
    def test_web_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_project(root)
            plan = init_mod.build(root)
            self.assertEqual(plan["profile"], "web-app")
            self.assertEqual(plan["profiles"], ["web-app"])
            self.assertIn("platform.web", plan["capabilities"])
            self.assertIn("distribution.web", plan["capabilities"])
            self.assertIn("kit.config.yaml", plan["files"])
            self.assertIn("ecosystem.yaml", plan["files"])
            self.assertIn(".kit/capabilities.yaml", plan["files"])
            self.assertIn("scripts/gate-behavior.sh", plan["files"])
            self.assertIn("npm run test", plan["files"]["scripts/gate-behavior.sh"])
            eco = yaml.safe_load(plan["files"]["ecosystem.yaml"])
            self.assertEqual(eco["products"]["app"]["surfaces"]["web"]["platforms"], ["web"])

    def test_ios_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ios_project(root)
            plan = init_mod.build(root)
            self.assertIn("platform.ios", plan["capabilities"])
            self.assertNotIn("distribution.app_store", plan["capabilities"])
            self.assertIn("ios", plan["files"]["ecosystem.yaml"])
            self.assertIn("swift test", plan["files"]["scripts/gate-behavior.sh"])
            declared = yaml.safe_load(plan["files"][".kit/capabilities.yaml"])
            self.assertNotIn("distribution.app_store", declared["include"])

    def test_multi_profile_web_api_auth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "package.json",
                json.dumps(
                    {
                        "dependencies": {
                            "react": "1",
                            "express": "1",
                        }
                    }
                ),
            )
            write(root, "src/auth/login.ts", "export default 1")
            write(root, "api/main.ts", "export default 1")
            plan = init_mod.build(root)
            self.assertEqual(plan["profiles"], ["web-app", "api-service", "auth"])
            self.assertIn("domain.auth", plan["capabilities"])
            config = yaml.safe_load(plan["files"]["kit.config.yaml"])
            self.assertEqual(
                config["factory"]["profiles"],
                ["web-app", "api-service", "auth"],
            )
            declared = yaml.safe_load(plan["files"][".kit/capabilities.yaml"])
            self.assertNotIn("domain.auth", declared["include"])
            self.assertIn("platform.web", declared["include"])

    def test_ios_app_store_capability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ios_project(root)
            write(root, "fastlane/Fastfile", "app_store\n")
            plan = init_mod.build(root)
            self.assertIn("platform.ios", plan["capabilities"])
            self.assertIn("distribution.app_store", plan["capabilities"])
            declared = yaml.safe_load(plan["files"][".kit/capabilities.yaml"])
            self.assertIn("distribution.app_store", declared["include"])
            eco = yaml.safe_load(plan["files"]["ecosystem.yaml"])
            surfaces = eco["products"]["app"]["surfaces"]
            self.assertIn("app_store_connect", surfaces["ios"]["distribution"])

    def test_dotted_repo_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                init_mod.subprocess,
                "check_output",
                return_value="git@github.com:acme/foo.js.git\n",
            ):
                self.assertEqual(
                    init_mod.repo_name(Path(directory)), "acme/foo.js"
                )

    def test_distribution_matches_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root,
                "package.json",
                json.dumps(
                    {
                        "dependencies": {"next": "1", "react": "1"},
                        "scripts": {"test": "vitest"},
                    }
                ),
            )
            write(root, "src/app.ts", "1")
            write(root, "vercel.json", "{}")
            (root / "ios").mkdir()
            (root / "ios/App.xcodeproj").mkdir()
            write(root, "fastlane/Fastfile", "app_store\n")
            plan = init_mod.build(root)
            eco = yaml.safe_load(plan["files"]["ecosystem.yaml"])
            surfaces = eco["products"]["app"]["surfaces"]
            self.assertEqual(surfaces["web"]["distribution"], ["web_deploy"])
            self.assertEqual(surfaces["ios"]["distribution"], ["app_store_connect"])

    def test_apply_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_project(root)
            plan = init_mod.build(root)
            first = init_mod.apply_plan(plan)
            self.assertIn("kit.config.yaml", first["written"])
            gate = root / "scripts" / "gate-behavior.sh"
            self.assertTrue(gate.stat().st_mode & stat.S_IXUSR)
            (root / "kit.config.yaml").write_text("custom\n", encoding="utf-8")
            second = init_mod.apply_plan(plan)
            self.assertIn("kit.config.yaml", second["skipped"])
            self.assertEqual((root / "kit.config.yaml").read_text(), "custom\n")

    def test_force_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_project(root)
            plan = init_mod.build(root)
            init_mod.apply_plan(plan)
            (root / "kit.config.yaml").write_text("custom\n", encoding="utf-8")
            applied = init_mod.apply_plan(plan, force=True)
            self.assertIn("kit.config.yaml", applied["written"])
            self.assertIn("protocol", (root / "kit.config.yaml").read_text())

    def test_build_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_project(root)
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            init_mod.build(root)
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
