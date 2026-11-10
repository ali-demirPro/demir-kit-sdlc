"""Tests for vendored kit sync."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("vendor_sync", SCRIPTS / "vendor_sync.py")
vendor_sync = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(vendor_sync)


def make_source(root: Path) -> None:
    (root / "delivery").mkdir()
    (root / "delivery" / "CONTRACT.md").write_text("v2 contract\n")
    (root / "skills" / "s1").mkdir(parents=True)
    (root / "skills" / "s1" / "SKILL.md").write_text("skill\n")
    (root / "VERSION").write_text("2.2.0\n")
    (root / "install.sh").write_text("#!/bin/sh\n")
    (root / "CHANGELOG.md").write_text("changelog\n")
    (root / "README.md").write_text("readme\n")


def make_product(root: Path) -> None:
    (root / "kit.config.yaml").write_text(
        "kit:\n  root: demir-kit\n  version: \"1.0.0\"\n  protocol: \"1\"\n"
    )
    kit = root / "demir-kit"
    (kit / "delivery").mkdir(parents=True)
    (kit / "delivery" / "CONTRACT.md").write_text("v1 contract\n")
    (kit / "references").mkdir()
    (kit / "references" / "old.md").write_text("old\n")
    (kit / "VERSION").write_text("1.0.0\n")
    (root / "product.txt").write_text("keep\n")


class VendorSyncTests(unittest.TestCase):
    def test_check_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            product = Path(directory) / "product"
            source.mkdir()
            product.mkdir()
            make_source(source)
            make_product(product)
            plan = vendor_sync.build_plan(source, product)
            self.assertFalse(plan["clean"])
            self.assertIn("delivery/CONTRACT.md", plan["changed"])
            self.assertIn("references", plan["legacy"])
            self.assertTrue(plan["config"]["version"])
            self.assertTrue(plan["config"]["protocol"])

    def test_apply_copies_removes_and_updates_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            product = Path(directory) / "product"
            source.mkdir()
            product.mkdir()
            make_source(source)
            make_product(product)
            plan = vendor_sync.apply_plan(source, product)
            self.assertTrue(plan["clean"])
            kit = product / "demir-kit"
            self.assertEqual((kit / "delivery" / "CONTRACT.md").read_text(), "v2 contract\n")
            self.assertTrue((kit / "skills" / "s1" / "SKILL.md").is_file())
            self.assertFalse((kit / "references").exists())
            self.assertEqual((product / "product.txt").read_text(), "keep\n")
            config = yaml.safe_load((product / "kit.config.yaml").read_text())
            self.assertEqual(config["kit"]["version"], "2.2.0")
            self.assertEqual(config["kit"]["protocol"], "2")
            self.assertTrue(vendor_sync.build_plan(source, product)["clean"])

    def test_apply_refuses_self_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "kit.config.yaml").write_text(
                "kit:\n  root: .\n  version: \"2.2.0\"\n  protocol: \"2\"\n"
            )
            (source / "VERSION").write_text("2.2.0\n")
            with self.assertRaises(ValueError):
                vendor_sync.apply_plan(source, source)

    def test_config_update_respects_kit_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text(
                "meta:\n  version: \"9\"\nkit:\n  root: demir-kit\n  version: \"1.0.0\"\n  protocol: \"1\"\n"
            )
            vendor_sync.update_config(root, "2.2.0")
            text = (root / "kit.config.yaml").read_text()
            self.assertIn('meta:\n  version: "9"', text)
            self.assertIn('kit:\n  root: demir-kit\n  version: "2.2.0"', text)
            self.assertIn('protocol: "2"', text)

    def test_apply_refuses_git_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            product = Path(directory) / "product"
            source.mkdir()
            product.mkdir()
            make_source(source)
            make_product(product)
            (product / "demir-kit" / ".git").mkdir()
            with self.assertRaises(ValueError) as ctx:
                vendor_sync.apply_plan(source, product)
            self.assertIn("submodule", str(ctx.exception))
            self.assertTrue((product / "demir-kit" / "delivery" / "CONTRACT.md").is_file())

    def test_apply_copies_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            product = Path(directory) / "product"
            source.mkdir()
            product.mkdir()
            make_source(source)
            (source / ".gitignore").write_text("__pycache__/\n*.pyc\n")
            make_product(product)
            plan = vendor_sync.apply_plan(source, product)
            self.assertTrue(plan["clean"])
            self.assertEqual(
                (product / "demir-kit" / ".gitignore").read_text(),
                "__pycache__/\n*.pyc\n",
            )

    def test_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            product = Path(directory) / "product"
            source.mkdir()
            product.mkdir()
            make_source(source)
            make_product(product)
            vendor_sync.apply_plan(source, product)
            plan = vendor_sync.build_plan(source, product)
            self.assertTrue(plan["clean"])
            self.assertEqual(plan["changed"], [])
            self.assertEqual(plan["legacy"], [])

    def test_apply_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            product = Path(directory) / "product"
            source.mkdir()
            product.mkdir()
            make_source(source)
            make_product(product)
            vendor_sync.apply_plan(source, product)
            kit = product / "demir-kit"
            self.assertTrue((kit / vendor_sync.MANIFEST_NAME).is_file())
            result = vendor_sync.check_manifest(kit)
            self.assertEqual(result["status"], "pass", result)
            self.assertEqual(result["missing"], [])
            self.assertEqual(result["extra"], [])
            self.assertEqual(result["changed"], [])


class KitManifestTests(unittest.TestCase):
    def make_tree(self, root: Path) -> None:
        make_source(root)
        (root / "delivery" / "tests").mkdir()
        (root / "delivery" / "tests" / "test_x.py").write_text("x\n")
        (root / "delivery" / "__pycache__").mkdir()
        (root / "delivery" / "__pycache__" / "x.pyc").write_bytes(b"x")
        (root / "notes.txt").write_text("not in allowlist\n")

    def seal(self, root: Path) -> dict:
        return vendor_sync.seal(root, commit="a" * 40)

    def test_manifest_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            payload = self.seal(root)
            first = (root / vendor_sync.MANIFEST_NAME).read_bytes()
            self.seal(root)
            second = (root / vendor_sync.MANIFEST_NAME).read_bytes()
            self.assertEqual(first, second)
            self.assertEqual(payload["version"], "2.2.0")
            self.assertEqual(payload["source_commit"], "a" * 40)
            self.assertEqual(payload["generator_version"], 1)
            paths = [item["path"] for item in payload["files"]]
            self.assertEqual(paths, sorted(paths))
            for item in payload["files"]:
                self.assertEqual(
                    item["bytes"], (root / item["path"]).stat().st_size
                )

    def test_manifest_scope_excludes_tests_and_pycache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            payload = self.seal(root)
            paths = {item["path"] for item in payload["files"]}
            self.assertIn("delivery/CONTRACT.md", paths)
            self.assertIn("skills/s1/SKILL.md", paths)
            self.assertIn("VERSION", paths)
            self.assertIn("install.sh", paths)
            self.assertFalse(any("/tests/" in path for path in paths))
            self.assertFalse(any("__pycache__" in path for path in paths))
            self.assertNotIn("notes.txt", paths)

    def test_offline_check_detects_missing_extra_and_changed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            self.seal(root)
            self.assertEqual(vendor_sync.check_manifest(root)["status"], "pass")

            (root / "delivery" / "CONTRACT.md").unlink()
            result = vendor_sync.check_manifest(root)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["missing"], ["delivery/CONTRACT.md"])

            self.seal(root)
            (root / "delivery" / "extra.md").write_text("extra\n")
            result = vendor_sync.check_manifest(root)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["extra"], ["delivery/extra.md"])

            self.seal(root)
            (root / "README.md").write_text("tampered\n")
            result = vendor_sync.check_manifest(root)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(len(result["changed"]), 1)
            changed = result["changed"][0]
            self.assertEqual(changed["path"], "README.md")
            self.assertRegex(changed["expected"], r"^[0-9a-f]{64}$")
            self.assertRegex(changed["actual"], r"^[0-9a-f]{64}$")
            self.assertNotEqual(changed["expected"], changed["actual"])

    def test_offline_check_accepts_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            (root / "delivery" / "EMPTY.md").write_text("")
            self.seal(root)
            result = vendor_sync.check_manifest(root)
            self.assertEqual(result["status"], "pass", result)
            self.assertEqual(result["changed"], [])

    def test_offline_check_without_manifest_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            result = vendor_sync.check_manifest(root)
            self.assertEqual(result["status"], "not_run")
            self.assertIn("KIT-MANIFEST.json", result["reason"])

    def test_manifest_validation_rejects_unknown_duplicate_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            payload = self.seal(root)

            unknown = json.loads(json.dumps(payload))
            unknown["surprise"] = True
            self.assertTrue(
                any("izin verilmeyen" in item for item in vendor_sync.validate_manifest(unknown))
            )

            duplicate = json.loads(json.dumps(payload))
            duplicate["files"].append(dict(duplicate["files"][0]))
            self.assertTrue(
                any("tekrarlı yol" in item for item in vendor_sync.validate_manifest(duplicate))
            )

            invalid = json.loads(json.dumps(payload))
            invalid["files"][0]["sha256"] = "not-a-digest"
            self.assertTrue(vendor_sync.validate_manifest(invalid))

            outside = json.loads(json.dumps(payload))
            outside["files"][0]["path"] = "notes.txt"
            self.assertTrue(
                any("allowlist dışı" in item for item in vendor_sync.validate_manifest(outside))
            )

    def test_check_cli_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            command = [
                sys.executable,
                str(SCRIPTS / "vendor_sync.py"),
                "--check",
                "--kit",
                str(root),
                "--json",
            ]
            missing = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(missing.returncode, 2)
            self.assertEqual(json.loads(missing.stdout)["status"], "not_run")

            self.seal(root)
            clean = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(clean.returncode, 0, clean.stderr)
            self.assertEqual(json.loads(clean.stdout)["status"], "pass")

            (root / "README.md").write_text("tampered\n")
            dirty = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(dirty.returncode, 1)
            self.assertEqual(json.loads(dirty.stdout)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
