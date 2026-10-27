"""Tests for project capability adaptation."""

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

spec = importlib.util.spec_from_file_location("adapt", SCRIPTS / "adapt.py")
adapt = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(adapt)


def make_project(root: Path) -> None:
    (root / "ecosystem.yaml").write_text(
        "products:\n"
        "  app:\n"
        "    surfaces:\n"
        "      web:\n"
        "        platforms: [web]\n"
        "        stacks: [next]\n",
        encoding="utf-8",
    )


def run(*args: str) -> int:
    with patch.object(sys, "argv", ["adapt.py", *args]):
        return adapt.main()


class AdaptTests(unittest.TestCase):
    def test_build_declared_add_and_remove(self) -> None:
        current = {"include": ["platform.web"], "exclude": ["platform.ios"]}
        target = adapt.build_declared(
            current, ["platform.android", "platform.ios"], ["platform.web"]
        )
        self.assertEqual(target["include"], ["platform.android", "platform.ios"])
        self.assertEqual(target["exclude"], ["platform.web"])

    def test_unknown_capability_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            with self.assertRaises(SystemExit):
                run("--project", str(root), "--add", "platform.unknown")

    def test_add_android_writes_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    run(
                        "--project",
                        str(root),
                        "--add",
                        "platform.android",
                        "--apply",
                        "--json",
                    ),
                    0,
                )
            declared = adapt.resolver.load_declared(root)
            self.assertIn("platform.android", declared["include"])
            self.assertTrue((root / ".kit" / "capabilities.yaml").is_file())

    def test_diff_web_to_android(self) -> None:
        registry = adapt.resolver.load_capabilities()
        matrix = adapt.resolver.load_matrix()
        variants = adapt.resolver.load_agent_variants()
        signals = [
            {
                "name": "web",
                "surfaces": ["web"],
                "platforms": ["web"],
                "stacks": ["next"],
                "distribution": [],
            }
        ]
        before = adapt.resolver.resolve(
            registry, matrix, variants, "ui_feature", signals
        )
        after = adapt.resolver.resolve(
            registry,
            matrix,
            variants,
            "ui_feature",
            signals,
            declared={"include": ["platform.android"], "exclude": []},
        )
        delta = adapt.diff(before, after)
        self.assertIn("platform.android", delta["capabilities_added"])
        self.assertIn(
            ("designer", "platform.android"), delta["variants_added"]
        )

    def test_remove_web_excludes_capability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            (root / ".kit").mkdir()
            (root / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: []\nexclude: []\n",
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    run(
                        "--project",
                        str(root),
                        "--remove",
                        "platform.web",
                        "--apply",
                        "--json",
                    ),
                    0,
                )
            declared = adapt.resolver.load_declared(root)
            self.assertIn("platform.web", declared["exclude"])

    def test_ios_to_web_diff(self) -> None:
        registry = adapt.resolver.load_capabilities()
        matrix = adapt.resolver.load_matrix()
        variants = adapt.resolver.load_agent_variants()
        signals = [
            {
                "name": "ios",
                "surfaces": ["ios"],
                "platforms": ["ios"],
                "stacks": ["swiftui"],
                "distribution": ["app_store_connect"],
            }
        ]
        before = adapt.resolver.resolve(
            registry, matrix, variants, "full_product", signals
        )
        after = adapt.resolver.resolve(
            registry,
            matrix,
            variants,
            "full_product",
            signals,
            declared={
                "include": ["platform.web"],
                "exclude": ["platform.ios"],
            },
        )
        delta = adapt.diff(before, after)
        self.assertIn("platform.web", delta["capabilities_added"])
        self.assertIn("platform.ios", delta["capabilities_removed"])
        self.assertTrue(
            any(doc.endswith("designer/variants/web.md") for doc in after["docs"])
        )
        self.assertFalse(
            any(doc.endswith("designer/variants/ios.md") for doc in after["docs"])
        )

    def test_apply_does_not_persist_profile_caps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            (root / "kit.config.yaml").write_text(
                "kit:\n  protocol: \"2\"\n"
                "factory:\n  default_profile: web-app\n"
                "  profiles: [web-app]\n",
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    run(
                        "--project",
                        str(root),
                        "--add",
                        "platform.ios",
                        "--apply",
                        "--json",
                    ),
                    0,
                )
            raw = adapt.resolver.load_declared(root, include_profiles=False)
            self.assertIn("platform.ios", raw["include"])
            self.assertNotIn("platform.web", raw["include"])
            self.assertNotIn("quality.a11y", raw["include"])
            merged = adapt.resolver.load_declared(root)
            self.assertIn("platform.web", merged["include"])
            self.assertIn("platform.ios", merged["include"])

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    run("--project", str(root), "--add", "platform.android"),
                    0,
                )
            self.assertFalse((root / ".kit" / "capabilities.yaml").exists())


if __name__ == "__main__":
    unittest.main()
