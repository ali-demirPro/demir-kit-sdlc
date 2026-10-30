"""Tests for product-mode doctor checks."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("doctor", SCRIPTS / "doctor.py")
doctor = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(doctor)


def make_product(root: Path, protocol: str = "2", gate_script: bool = True) -> None:
    (root / "demir-kit" / "delivery" / "scripts").mkdir(parents=True)
    (root / "demir-kit" / "delivery" / "scripts" / "doctor.py").write_text("# kit\n")
    (root / "scripts").mkdir()
    if gate_script:
        (root / "scripts" / "gate-behavior.sh").write_text("#!/bin/sh\nexit 0\n")
    (root / "src").mkdir()
    (root / "kit.config.yaml").write_text(
        "kit:\n"
        "  root: demir-kit\n"
        "  protocol: \"%s\"\n"
        "factory:\n"
        "  app_paths: [src]\n" % protocol
    )
    (root / "ecosystem.yaml").write_text(
        "name: test\n"
        "products:\n"
        "  app:\n"
        "    surfaces:\n"
        "      web:\n"
        "        path: src\n"
        "        gates:\n"
        "          behavior: ./scripts/gate-behavior.sh {checkpoint}\n"
    )
    (root / "package.json").write_text(
        json.dumps({"scripts": {"typecheck": "tsc --noEmit", "lint": "eslint ."}})
    )
    (root / "AGENTS.md").write_text("# Agents\n")


class ProductDoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        doctor.ERRORS.clear()
        doctor.WARNS.clear()

    def test_valid_product(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            doctor.check_product(root)
            self.assertEqual(doctor.ERRORS, [])

    def test_protocol_must_be_v2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root, protocol="1")
            doctor.check_product(root)
            self.assertTrue(any("protocol" in item for item in doctor.ERRORS))

    def test_declared_capability_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            (root / ".kit").mkdir()
            (root / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: [platform.unknown]\nexclude: []\n"
            )
            doctor.check_product(root)
            self.assertTrue(
                any("bilinmeyen capability" in item for item in doctor.ERRORS)
            )

    def test_declared_capability_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            (root / ".kit").mkdir()
            (root / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: [platform.web]\nexclude: []\n"
            )
            doctor.check_product(root)
            self.assertEqual(doctor.ERRORS, [])

    def test_risk_overlay_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            (root / ".kit").mkdir()
            (root / ".kit" / "risk.yaml").write_text(
                "auto_escalate:\n  high: ['RenderKit/**']\n  critical: ['**/Signing/**']\n",
                encoding="utf-8",
            )
            doctor.check_product(root)
            self.assertEqual(doctor.ERRORS, [])

    def test_risk_overlay_invalid_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            (root / ".kit").mkdir()
            (root / ".kit" / "risk.yaml").write_text(
                "auto_escalate:\n  high: 'RenderKit/**'\n", encoding="utf-8"
            )
            doctor.check_product(root)
            self.assertTrue(
                any("auto_escalate.high" in item for item in doctor.ERRORS)
            )

    def test_priorities_paths_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            (root / "docs").mkdir()
            (root / "docs" / "design.md").write_text("# design\n")
            (root / "docs" / "arch.md").write_text("# arch\n")
            config = root / "kit.config.yaml"
            config.write_text(
                config.read_text(encoding="utf-8")
                + "product:\n"
                "  priorities:\n"
                "    design_system: docs/design.md\n"
                "    architecture: [docs/arch.md]\n",
                encoding="utf-8",
            )
            doctor.check_product(root)
            self.assertEqual(doctor.ERRORS, [])

    def test_priorities_missing_path_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            config = root / "kit.config.yaml"
            config.write_text(
                config.read_text(encoding="utf-8")
                + "product:\n"
                "  priorities:\n"
                "    design_system: docs/design.md\n",
                encoding="utf-8",
            )
            doctor.check_product(root)
            self.assertTrue(
                any("design_system" in item for item in doctor.ERRORS)
            )

    def set_profiles(self, root: Path, names: list[str], default: str) -> None:
        config = root / "kit.config.yaml"
        config.write_text(
            config.read_text()
            + "  default_profile: %s\n  profiles: [%s]\n"
            % (default, ", ".join(names)),
            encoding="utf-8",
        )

    def test_profile_composition_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            self.set_profiles(root, ["web-app", "api-service", "auth"], "web-app")
            doctor.check_product(root)
            self.assertEqual(doctor.ERRORS, [])

    def test_profile_unknown_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            self.set_profiles(root, ["web-app", "ghost"], "web-app")
            doctor.check_product(root)
            self.assertTrue(any("profil yok" in item for item in doctor.ERRORS))

    def test_profile_overlay_only_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            self.set_profiles(root, ["auth"], "auth")
            doctor.check_product(root)
            self.assertTrue(any("base" in item for item in doctor.ERRORS))

    def test_missing_gate_script(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root, gate_script=False)
            doctor.check_product(root)
            self.assertTrue(any("gate script" in item for item in doctor.ERRORS))

    def test_missing_surface_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_product(root)
            (root / "src").rmdir()
            doctor.check_product(root)
            self.assertTrue(any("path yok" in item for item in doctor.ERRORS))

    def test_guard_uses_product_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "app.ts").write_text("before\n")
            (root / "kit.config.yaml").write_text(
                "kit:\n  root: demir-kit\n  protocol: \"2\"\nfactory:\n  app_paths: [src]\n"
            )
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
                cwd=root,
                check=True,
            )
            (root / "src" / "app.ts").write_text("after\n")
            env = os.environ.copy()
            env["PRODUCT_ROOT"] = str(root)
            result = subprocess.run(
                ["bash", str(SCRIPTS / "guard.sh")],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("BLOCKED", result.stdout + result.stderr)
            self.assertIn("src/app.ts", result.stdout + result.stderr)

    def test_legacy_profile_exists(self) -> None:
        self.assertTrue(
            (ROOT / "delivery" / "profiles" / "web-product.yaml").is_file()
        )
        self.assertFalse((ROOT / "delivery" / "templates" / "product").exists())

    def test_product_issue_reads_product_tracker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ecosystem.yaml").write_text(
                "tracker:\n  provider: github\n  repo: owner/product\nproducts: {}\n"
            )
            calls = []

            def fake_run(args):
                calls.append(args)
                if "comments" in args[2]:
                    return "[]"
                return json.dumps({"body": "x", "labels": [], "title": "t"})

            original_run = doctor.run
            original_body = doctor.check_issue_body
            doctor.run = fake_run
            doctor.check_issue_body = lambda *args, **kwargs: None
            try:
                doctor.check_issue(42, None, root)
            finally:
                doctor.run = original_run
                doctor.check_issue_body = original_body
            self.assertTrue(any("repos/owner/product/issues/42" in call for call in calls))


if __name__ == "__main__":
    unittest.main()
