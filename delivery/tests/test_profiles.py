"""Tests for base + overlay profile composition."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
PROFILES = ROOT / "delivery" / "profiles"
PACKS = ROOT / "delivery" / "packs"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("profiles", SCRIPTS / "profiles.py")
profiles = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(profiles)

spec_resolver = importlib.util.spec_from_file_location("resolver", SCRIPTS / "resolver.py")
resolver = importlib.util.module_from_spec(spec_resolver)
assert spec_resolver.loader is not None
spec_resolver.loader.exec_module(resolver)


def project(root: Path, factory: str) -> Path:
    (root / "kit.config.yaml").write_text(
        "kit:\n  root: demir-kit\n  protocol: \"2\"\nfactory:\n" + factory,
        encoding="utf-8",
    )
    return root


def config(names: list[str], default: str | None = None) -> str:
    lines = ["  app_paths: [src]"]
    if default:
        lines.append(f"  default_profile: {default}")
    lines.append("  profiles: [" + ", ".join(names) + "]")
    return "\n".join(lines) + "\n"


def capability_ids() -> set[str]:
    registry = yaml.safe_load(
        (ROOT / "delivery" / "capabilities" / "registry.yaml").read_text(
            encoding="utf-8"
        )
    )
    return set((registry.get("capabilities") or {}).keys())


def pack_names() -> set[str]:
    return {path.name for path in PACKS.iterdir() if path.is_dir()}


class ComposeTests(unittest.TestCase):
    def test_web_api_auth_union(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(
                Path(directory), config(["web-app", "api-service", "auth"], "web-app")
            )
            data = profiles.compose(root)
            self.assertEqual(data["default"], "web-app")
            self.assertEqual(data["base"], ["web-app", "api-service"])
            self.assertEqual(data["overlays"], ["auth"])
            self.assertIn("platform.web", data["capabilities"])
            self.assertIn("platform.api", data["capabilities"])
            self.assertIn("domain.auth", data["capabilities"])
            self.assertIn("web-ux", data["platform_packs"])
            self.assertIn("architect", data["extra_gates"])
            self.assertIn("work-package", data["required_skills"])

    def test_web_ios_mobile_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), config(["web-app", "ios-app"], "ios-app"))
            data = profiles.compose(root)
            self.assertEqual(data["base"], ["web-app", "ios-app"])
            self.assertIn("platform.ios", data["capabilities"])
            self.assertTrue(data["commercial_baseline_required"])
            self.assertIn("apple-hig", data["platform_packs"])
            # Store capability yalnız kanıtla gelir; profil tek başına
            # critical risk tabanı üretmez.
            self.assertNotIn("distribution.app_store", data["capabilities"])
            self.assertNotIn("quality.security", data["capabilities"])

    def test_legacy_default_profile_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), "  default_profile: web-product\n")
            data = profiles.compose(root)
            self.assertEqual(data["profiles"], ["web-product"])
            self.assertEqual(data["default"], "web-product")

    def test_default_falls_back_to_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), config(["web-app", "auth"]))
            data = profiles.compose(root)
            self.assertEqual(data["default"], "web-app")

    def test_unknown_profile_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), config(["web-app", "nope"], "web-app"))
            with self.assertRaises(ValueError):
                profiles.compose(root)

    def test_profile_capabilities_union(self) -> None:
        caps = profiles.profile_capabilities(["web-app", "api-service"])
        self.assertIn("platform.web", caps)
        self.assertIn("platform.api", caps)
        self.assertEqual(caps, sorted(caps))


class ValidateTests(unittest.TestCase):
    def check(self, factory: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), factory)
            return profiles.validate_project(root, capability_ids(), pack_names())

    def test_unconfigured_product_is_valid(self) -> None:
        self.assertEqual(self.check("  app_paths: [src]\n"), [])

    def test_valid_composition(self) -> None:
        self.assertEqual(
            self.check(config(["web-app", "api-service", "auth"], "web-app")), []
        )

    def test_default_must_be_in_profiles(self) -> None:
        errors = self.check(config(["web-app"], "api-service"))
        self.assertTrue(any("default_profile" in item for item in errors))

    def test_duplicate_profile(self) -> None:
        errors = self.check(config(["web-app", "web-app"], "web-app"))
        self.assertTrue(any("tekrarlı" in item for item in errors))

    def test_overlay_only_rejected(self) -> None:
        errors = self.check(config(["auth", "payments"], "auth"))
        self.assertTrue(any("base" in item for item in errors))

    def test_legacy_unknown_default_skipped(self) -> None:
        # 2.20 init mobil projelerde 'mobile-app' yazabiliyordu.
        self.assertEqual(
            self.check("  default_profile: mobile-app\n  app_paths: [src]\n"), []
        )
        self.assertEqual(
            self.check("  default_profile: unknown\n  app_paths: [src]\n"), []
        )

    def test_unknown_profile(self) -> None:
        errors = self.check(config(["web-app", "ghost"], "web-app"))
        self.assertTrue(any("profil yok" in item for item in errors))

    def test_all_library_profiles_valid(self) -> None:
        capabilities = capability_ids()
        packs = pack_names()
        for path in sorted(PROFILES.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            self.assertEqual(data.get("id"), path.stem, path.name)
            for cap_id in data.get("capabilities") or []:
                self.assertIn(cap_id, capabilities, f"{path.name}: {cap_id}")
            for pack in data.get("platform_packs") or []:
                self.assertIn(pack, packs, f"{path.name}: {pack}")
            self.assertEqual(
                data.get("product_class") == "overlay",
                path.stem in profiles.OVERLAYS,
                f"{path.name}: overlay sınıflandırması",
            )

    def test_base_library_covers_all_platforms(self) -> None:
        caps = profiles.profile_capabilities(
            [path.stem for path in PROFILES.glob("*.yaml") if path.stem not in profiles.OVERLAYS]
        )
        for expected in (
            "platform.web",
            "platform.ios",
            "platform.android",
            "platform.api",
        ):
            self.assertIn(expected, caps)


class ResolveTests(unittest.TestCase):
    def entries(self, data: dict) -> list[tuple[dict, str]]:
        found = [(data["profile"], str(data["profile"]["value"]))]
        found.extend((item, str(item["value"])) for item in data["profiles"])
        for key in ("overlays", "packs", "gates", "capabilities", "required_skills"):
            found.extend((item, str(item["value"])) for item in data[key])
        found.append(
            (
                data["architecture_baseline_required"],
                str(data["architecture_baseline_required"]["value"]),
            )
        )
        found.append(
            (
                data["commercial_baseline_required"],
                str(data["commercial_baseline_required"]["value"]),
            )
        )
        found.append((data["risk"]["human_gate"], str(data["risk"]["human_gate"]["value"])))
        found.extend(
            (item, item["value"].split(":", 1)[1]) for item in data["risk"]["matches"]
        )
        return found

    def assert_line_content(self, root: Path, source: str, value: str) -> None:
        path, _, number = source.rpartition(":")
        self.assertFalse(Path(path).is_absolute(), source)
        line = (root / path).read_text(encoding="utf-8").splitlines()[
            int(number) - 1
        ]
        self.assertIn(value.lower(), line.lower(), source)

    def test_json_provenance(self) -> None:
        data = profiles.resolve(ROOT)
        self.assertEqual(data["profile"]["value"], "kit-internal")
        for key in ("profile", "overlays", "packs", "gates", "risk"):
            self.assertIn(key, data)
        for entry, value in self.entries(data):
            source = entry["source"]
            if source is None:
                continue
            self.assertRegex(source, r"^[^:]+:\d+$")
            self.assert_line_content(ROOT, source, value)

        # Overlay gate kaynağı gerçek satır olmalı (architect, auth.yaml).
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), config(["web-app", "auth"], "web-app"))
            gates = {
                item["value"]: item["source"]
                for item in profiles.resolve(root)["gates"]
            }
        self.assertIn("architect", gates)
        self.assertEqual(
            profiles.item_source(PROFILES / "auth.yaml", "extra_gates", "architect"),
            gates["architect"],
        )
        self.assert_line_content(ROOT, gates["architect"], "architect")

    def test_risk_excluded_paths(self) -> None:
        data = profiles.resolve(ROOT, ["delivery/tests/auth_test.py"])
        self.assertEqual(data["risk"]["level"], "none")
        self.assertEqual(data["risk"]["matches"], [])
        self.assertEqual(data["risk"]["origin"], "derived")
        self.assertIsNone(data["risk"]["level_source"])

    def test_risk_project_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), config(["web-app"], "web-app"))
            (root / ".kit").mkdir()
            (root / ".kit" / "risk.yaml").write_text(
                'auto_escalate:\n  high:\n    - "**/special/**"\n',
                encoding="utf-8",
            )
            data = profiles.resolve(root, ["src/special/pay.py"])
            self.assertEqual(data["risk"]["level"], "high")
            self.assertEqual(data["risk"]["origin"], "match")
            self.assertEqual(data["risk"]["human_gate"]["value"], "leaf")
            self.assertEqual(
                data["risk"]["matches"],
                [{"value": "high:**/special/**", "source": ".kit/risk.yaml:3"}],
            )
            self.assertEqual(data["risk"]["level_source"], ".kit/risk.yaml:3")
            self.assert_line_content(root, ".kit/risk.yaml:3", "**/special/**")

    def test_order_is_deterministic(self) -> None:
        outputs = []
        for seed in ("0", "1"):
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "profiles.py"),
                    "--project",
                    str(ROOT),
                    "--resolve",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHASHSEED": seed},
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(
            json.loads(outputs[0])["order"],
            ["base", "overlays", "packs", "risk_globs"],
        )

        # Overlay config'te önce gelse de base değeri kazanır.
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), config(["auth", "web-app"], "web-app"))
            data = profiles.resolve(root)
        skills = {item["value"]: item["source"] for item in data["required_skills"]}
        self.assertEqual(skills["work-package"], "delivery/profiles/web-app.yaml:8")


class ResolverMergeTests(unittest.TestCase):
    def test_profile_capabilities_merge_into_declared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), config(["api-service", "auth"], "api-service"))
            (root / ".kit").mkdir()
            (root / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: [quality.performance]\nexclude: []\n",
                encoding="utf-8",
            )
            declared = resolver.load_declared(root)
            self.assertIn("quality.performance", declared["include"])
            self.assertIn("platform.api", declared["include"])
            self.assertIn("domain.auth", declared["include"])

    def test_profile_caps_merge_without_declared_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), config(["ios-app"], "ios-app"))
            declared = resolver.load_declared(root)
            self.assertIn("platform.ios", declared["include"])
            self.assertNotIn("distribution.app_store", declared["include"])

    def test_unconfigured_project_keeps_declared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), "  app_paths: [src]\n")
            (root / ".kit").mkdir()
            (root / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: [platform.web]\nexclude: []\n",
                encoding="utf-8",
            )
            declared = resolver.load_declared(root)
            self.assertEqual(declared["include"], ["platform.web"])


if __name__ == "__main__":
    unittest.main()
