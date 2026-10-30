"""Tests for vendored kit sync."""

from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
