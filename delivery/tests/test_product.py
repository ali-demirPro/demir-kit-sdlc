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

    def test_template_and_profile_exist(self) -> None:
        template = ROOT / "delivery" / "templates" / "product"
        for name in (
            "kit.config.yaml",
            "ecosystem.yaml",
            "scripts/gate-behavior.sh",
            "scripts/install-orca-user-skills.sh",
        ):
            self.assertTrue((template / name).is_file(), name)
        self.assertIn("protocol: \"2\"", (template / "kit.config.yaml").read_text())
        self.assertIn("typecheck", (template / "scripts" / "gate-behavior.sh").read_text())
        self.assertTrue((ROOT / "delivery" / "profiles" / "web-product.yaml").is_file())

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
