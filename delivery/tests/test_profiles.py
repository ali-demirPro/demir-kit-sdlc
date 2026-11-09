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

spec_rigor = importlib.util.spec_from_file_location("rigor", SCRIPTS / "rigor.py")
rigor = importlib.util.module_from_spec(spec_rigor)
assert spec_rigor.loader is not None
spec_rigor.loader.exec_module(rigor)

spec_routing = importlib.util.spec_from_file_location("routing", SCRIPTS / "routing.py")
routing = importlib.util.module_from_spec(spec_routing)
assert spec_routing.loader is not None
spec_routing.loader.exec_module(routing)


def project(root: Path, factory: str) -> Path:
    (root / "kit.config.yaml").write_text(
        "kit:\n  root: demir-kit\n  protocol: \"2\"\nfactory:\n" + factory,
        encoding="utf-8",
    )
    return root


def rigor_project(root: Path, process: str) -> Path:
    """kit.config with a `process:` block plus a valid profile selection."""
    (root / "kit.config.yaml").write_text(
        "kit:\n  root: demir-kit\n  protocol: \"2\"\nprocess:\n"
        + process
        + "factory:\n  default_profile: web-app\n  profiles: [web-app]\n",
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

    def test_project_config_source_is_relative(self) -> None:
        """Proje kökü kit dışında olsa da kaynak `kit.config.yaml:<satır>` olur."""
        with tempfile.TemporaryDirectory() as directory:
            root = project(Path(directory), config(["web-app"], "web-app"))
            data = profiles.resolve(root)
        source = data["profile"]["source"]
        self.assertEqual(source, "kit.config.yaml:6")
        self.assertFalse(Path(source.rpartition(":")[0]).is_absolute(), source)
        self.assertNotIn(str(root), json.dumps(data, ensure_ascii=False))

    def test_in_repo_config_source_is_relative(self) -> None:
        data = profiles.resolve(ROOT)
        source = data["profile"]["source"]
        self.assertRegex(str(source), r"^kit\.config\.yaml:\d+$")
        self.assertFalse(Path(str(source).rpartition(":")[0]).is_absolute(), source)

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


class RigorProfileTests(unittest.TestCase):
    def test_compose_carries_effective_rigor(self) -> None:
        """T-1: compose/resolve rigor bloğu load_effective ile birebir aynı."""
        expected = rigor.load_effective(ROOT)
        for data in (profiles.compose(ROOT), profiles.resolve(ROOT)):
            block = data["rigor"]
            self.assertEqual(block["level"], expected["level"])
            self.assertEqual(block["source"], expected["source"])
            self.assertEqual(sorted(block["knobs"]), sorted(rigor.KNOBS))
            self.assertEqual(len(block["knobs"]), 6)
            for name, item in expected["knobs"].items():
                self.assertEqual(block["knobs"][name]["value"], item["value"], name)
                self.assertEqual(block["knobs"][name]["source"], item["source"], name)
            self.assertEqual(block["warnings"], [])
            self.assertIsNone(block["fallback"])

    def test_invalid_rigor_warns_and_falls_back(self) -> None:
        """T-3: geçersiz seviye ve çözülemeyen düğme sessizce yutulmaz."""
        cases = {
            "geçersiz seviye": "  rigor: extreme\n",
            "çözülemeyen düğme": "  qa.level: extreme\n",
        }
        fallback = rigor.fallback_effective()
        for label, process in cases.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory:
                root = rigor_project(Path(directory), process)
                block = profiles.compose(root)["rigor"]
            self.assertEqual(block["level"], "standard")
            self.assertEqual(block["source"], "fallback")
            self.assertEqual(len(block["warnings"]), 1)
            self.assertTrue(block["warnings"][0].startswith("uyarı: "))
            self.assertIn("geçersiz", block["warnings"][0])
            self.assertTrue(block["fallback"].startswith("standard ("))
            self.assertIn("geçersiz", block["fallback"])
            for name, item in fallback["knobs"].items():
                self.assertEqual(block["knobs"][name], item, name)

    def test_matrix_levels_and_off_diagonals(self) -> None:
        """T-4: standart, açık minimal/full ve iki off-diagonal vakası.

        Her vaka kendi etkin rigor bloğunu ve profil gate kümesini kullanır:
        (a) gating reviewer sayısı yalnız riskten gelir, (b) evidence_reviewers
        aynı gate/risk için seviyeden bağımsız aynı rolleri verir, (c) düğme
        değerleri seviyeleri gerçekten ayırır.
        """
        gates = {"behavior": True}
        risks = ("medium", "high")
        cases = {
            "standard": ("  rigor: standard\n", "standard", "kit.config.yaml", {}),
            "minimal": ("  rigor: minimal\n", "minimal", "kit.config.yaml", {}),
            "full": ("  rigor: full\n", "full", "kit.config.yaml", {}),
            "full+terse": (
                "  rigor: full\n  docs.density: terse\n",
                "full",
                "kit.config.yaml",
                {"docs.density": "terse"},
            ),
            "minimal+qa-full": (
                "  rigor: minimal\n  qa.level: full\n",
                "minimal",
                "kit.config.yaml",
                {"qa.level": "full"},
            ),
        }
        table = rigor.load_rigor()["levels"]
        reviewers: dict[str, set[tuple[str, ...]]] = {risk: set() for risk in risks}
        matrices: dict[str, tuple[tuple[str, str], ...]] = {}
        for label, (process, level, source, overrides) in cases.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory:
                root = rigor_project(Path(directory), process)
                block = profiles.compose(root)["rigor"]
                profile_gates = profiles.gates_for(root, "web-app")
                counts = {risk: rigor.reviewer_count(risk) for risk in risks}
                roles = {
                    risk: tuple(
                        routing.evidence_reviewers(gates, risk, profile_gates)
                    )
                    for risk in risks
                }
            self.assertTrue(profile_gates, label)
            self.assertEqual(block["level"], level)
            self.assertEqual(block["source"], source)
            self.assertEqual(block["warnings"], [])
            for name in rigor.KNOBS:
                expected_value = overrides.get(name, table[level][name])
                expected_source = (
                    "kit.config.yaml" if name in overrides else f"rigor:{level}"
                )
                self.assertEqual(block["knobs"][name]["value"], expected_value, name)
                self.assertEqual(block["knobs"][name]["source"], expected_source, name)
            # (a) Gating sayısı risk-only: seviye tablosunda da düğmeden başka
            # anahtar yok; düğme değerleri bu sayıya girmiyor.
            self.assertEqual(counts, {"medium": 1, "high": 2}, label)
            self.assertEqual(set(table[level]), set(rigor.KNOBS), label)
            # (b) Aynı gate/risk girdisi seviyeden bağımsız aynı rolleri verir.
            for risk in risks:
                reviewers[risk].add(roles[risk])
            matrices[label] = tuple(
                (name, block["knobs"][name]["value"]) for name in rigor.KNOBS
            )
        for risk in risks:
            self.assertEqual(len(reviewers[risk]), 1, f"{risk}: {reviewers[risk]}")
        # (c) Düğmeler gerçekten ayrışıyor; yoksa test seviyeleri ayırmaz.
        self.assertEqual(len(set(matrices.values())), len(cases), matrices)
        self.assertNotEqual(matrices["minimal"], matrices["standard"])
        self.assertNotEqual(matrices["standard"], matrices["full"])
        self.assertNotEqual(matrices["full+terse"], matrices["full"])
        self.assertNotEqual(matrices["minimal+qa-full"], matrices["minimal"])


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
