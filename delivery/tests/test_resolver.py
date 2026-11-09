"""Tests for capability/variant resolution."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("resolver", SCRIPTS / "resolver.py")
resolver = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(resolver)

spec_brief = importlib.util.spec_from_file_location("brief", SCRIPTS / "brief.py")
brief = importlib.util.module_from_spec(spec_brief)
assert spec_brief.loader is not None
spec_brief.loader.exec_module(brief)

REGISTRY = resolver.load_capabilities()
MATRIX = resolver.load_matrix()
VARIANTS = resolver.load_agent_variants()


def signal(name: str, platforms=(), stacks=(), distribution=()):
    return {
        "name": name,
        "surfaces": [name],
        "platforms": list(platforms),
        "stacks": list(stacks),
        "distribution": list(distribution),
    }


def run(path: str, signals: list[dict], text: str = "") -> dict:
    return resolver.resolve(REGISTRY, MATRIX, VARIANTS, path, signals, text)


class ResolverTests(unittest.TestCase):
    def test_web_only_loads_web_not_mobile(self) -> None:
        data = run(
            "ui_feature",
            [signal("web", platforms=["web"], stacks=["next"])],
        )
        self.assertIn("platform.web", data["capabilities"])
        self.assertNotIn("platform.ios", data["capabilities"])
        self.assertNotIn("platform.android", data["capabilities"])
        docs = "\n".join(data["docs"])
        self.assertIn("designer/variants/web.md", docs)
        self.assertNotIn("designer/variants/ios.md", docs)
        self.assertNotIn("tester/variants/android.md", docs)
        self.assertTrue(
            any(
                item["role"] == "designer" and item["capability"] == "platform.ios"
                for item in data["inactive_variants"]
            )
        )
        self.assertIn("marketing/stores", data["inactive_roles"])

    def test_ios_only_loads_apple(self) -> None:
        data = run(
            "full_product",
            [
                signal(
                    "ios",
                    platforms=["ios"],
                    stacks=["swiftui"],
                    distribution=["app_store_connect"],
                )
            ],
        )
        self.assertIn("platform.ios", data["capabilities"])
        self.assertIn("distribution.app_store", data["capabilities"])
        docs = "\n".join(data["docs"])
        self.assertIn("designer/variants/ios.md", docs)
        self.assertIn("tester/variants/ios.md", docs)
        self.assertIn("marketing/stores/variants/apple.md", docs)
        self.assertNotIn("designer/variants/web.md", docs)

    def test_web_and_ios_are_both_loaded(self) -> None:
        data = run(
            "full_product",
            [
                signal("web", platforms=["web"], stacks=["next"]),
                signal(
                    "ios",
                    platforms=["ios"],
                    stacks=["swiftui"],
                    distribution=["app_store_connect"],
                ),
            ],
        )
        docs = "\n".join(data["docs"])
        self.assertIn("designer/variants/web.md", docs)
        self.assertIn("designer/variants/ios.md", docs)
        self.assertIn("platform.web", data["capabilities"])
        self.assertIn("platform.ios", data["capabilities"])

    def test_api_only_loads_api_variants(self) -> None:
        data = run(
            "pure_technical",
            [signal("api", platforms=["api"], stacks=["python"])],
        )
        self.assertIn("platform.api", data["capabilities"])
        docs = "\n".join(data["docs"])
        self.assertIn("developer/variants/api.md", docs)
        self.assertIn("tester/variants/api.md", docs)
        self.assertNotIn("designer/variants/web.md", docs)
        self.assertTrue(
            not any(
                item["capability"] == "platform.api" for item in data["variant_gaps"]
            )
        )

    def test_keyword_capability_raises_risk_floor(self) -> None:
        data = run("pure_technical", [], "Add auth login and session")
        self.assertIn("domain.auth", data["capabilities"])
        self.assertEqual(data["risk_floor"], "high")

    def test_brief_web_only_hides_mobile_docs(self) -> None:
        body = """```yaml demir-kit
epic: 55
surfaces: [web.app]
factory: {stacks: [next]}
risk: {level: medium}
```"""
        data = brief.build_brief(
            resolver.load_yaml(ROOT / "delivery" / "registry.yaml"),
            55,
            "Web page",
            body,
            {"agent-approved"},
            ecosystem={
                "products": {
                    "app": {
                        "surfaces": {
                            "web": {"platforms": ["web"], "stacks": ["next"]}
                        }
                    }
                }
            },
        )
        self.assertIn("platform.web", data["capabilities"])
        docs = "\n".join(data["docs"])
        self.assertNotIn("designer/variants/ios.md", docs)
        self.assertIn("capabilities:", brief.render(data))

    def test_prose_does_not_activate_ios_auth_or_store(self) -> None:
        data = run(
            "ui_feature",
            [signal("web", platforms=["web"], stacks=["next"])],
            "conversion ratios author bio PR incelemesi",
        )
        self.assertEqual(data["capabilities"], ["platform.web"])

    def test_ui_feature_keeps_designer_active(self) -> None:
        data = run("ui_feature", [])
        self.assertIn("designer", data["active_roles"])
        self.assertNotIn("designer", data["inactive_roles"])

    def test_on_demand_not_duplicated(self) -> None:
        data = run(
            "ui_feature",
            [signal("web", platforms=["web"], stacks=["next"])],
        )
        self.assertFalse(
            set(data["active_roles"]) & set(data["on_demand_roles"])
        )

    def test_pure_technical_architect_stays_on_demand(self) -> None:
        data = run("pure_technical", [])
        self.assertIn("architect", data["on_demand_roles"])
        self.assertNotIn("architect", data["active_roles"])

    def test_matrix_is_returned(self) -> None:
        data = run("pure_technical", [])
        self.assertIn("roles", data["matrix"])


class KeywordFloorTests(unittest.TestCase):
    def test_surfaces_disable_free_text_keywords(self) -> None:
        registry = {
            "capabilities": {
                "domain.auth": {
                    "kind": "domain",
                    "match": {"keywords": ["oturum"]},
                    "roles": {},
                    "risk_floor": "high",
                }
            }
        }
        signals = [
            {"platforms": [], "stacks": [], "surfaces": ["kit.docs"], "distribution": []}
        ]
        self.assertEqual(
            resolver.match_capabilities(registry, signals, "oturum", allow_keywords=False),
            {},
        )
        self.assertEqual(
            resolver.match_capabilities(registry, signals, "oturum"), {}
        )
        oauth = {
            "capabilities": {
                "domain.auth": {
                    "kind": "domain",
                    "match": {"keywords": ["oauth"]},
                    "roles": {},
                    "risk_floor": "high",
                }
            }
        }
        self.assertIn(
            "domain.auth", resolver.match_capabilities(oauth, signals, "oauth")
        )


class LocalOverrideTests(unittest.TestCase):
    """T-1/T-3: kişisel dosya yalnız beyaz listedeki deneyim anahtarını ezer."""

    SIGNALS = [signal("web", platforms=["web"], stacks=["next"])]

    def make_project(self, directory: str, local: dict | None = None) -> Path:
        root = Path(directory)
        (root / "ecosystem.yaml").write_text(
            "products:\n  app:\n    surfaces:\n      web.app:\n"
            "        platforms: [web]\n        stacks: [next]\n",
            encoding="utf-8",
        )
        if local is not None:
            (root / ".kit").mkdir(parents=True)
            (root / ".kit" / "local.yaml").write_text(
                yaml.safe_dump(local, sort_keys=False), encoding="utf-8"
            )
        return root

    def resolve_in(self, root: Path) -> dict:
        return resolver.resolve(
            REGISTRY,
            MATRIX,
            VARIANTS,
            "full_product",
            self.SIGNALS,
            project=root,
        )

    def test_whitelisted_density_is_applied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(
                directory,
                {
                    "docs": {"density": "terse"},
                    "process": {"rigor": "full"},
                    "routing": {"evidence_reviewers": 2},
                },
            )
            data = self.resolve_in(root)
        local = data["local"]
        self.assertEqual(local["values"], {"docs.density": "terse"})
        self.assertEqual(local["sources"], {"docs.density": ".kit/local.yaml"})
        self.assertEqual(
            local["docs"]["density"],
            {"value": "terse", "source": ".kit/local.yaml"},
        )
        warnings = "\n".join(local["warnings"])
        self.assertIn("'process.rigor' kilitli", warnings)
        self.assertIn("'routing.evidence_reviewers' kilitli", warnings)
        self.assertEqual(len(local["warnings"]), 2, local["warnings"])

    def test_unlisted_and_invalid_values_are_ignored_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(
                directory,
                {
                    "docs": {"density": "deep"},
                    "theme": {"name": "dark"},
                    "gates": {"human": False},
                },
            )
            data = self.resolve_in(root)
        local = data["local"]
        self.assertEqual(local["values"], {})
        self.assertNotEqual(local["docs"]["density"]["value"], "deep")
        self.assertEqual(local["docs"]["density"]["source"], "default")
        warnings = "\n".join(local["warnings"])
        self.assertIn("'docs.density' geçersiz — beklenen: terse, balanced, thorough", warnings)
        self.assertIn("'theme.name' beyaz listede değil", warnings)
        self.assertIn("'gates.human' kilitli", warnings)

    def test_locked_keys_cannot_change_risk_reviewers_or_gates(self) -> None:
        locked = {
            "process": {"rigor": "minimal"},
            "qa": {"level": "minimal"},
            "team": {"size": "studio"},
            "risk": {"level": "critical", "auto_escalate": {"high": []}},
            "routing": {"evidence_reviewers": 0},
            "gates": {"human": False},
            "modes": {"workflow": "minimal", "review_mode": "solo"},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory, locked)
            data = self.resolve_in(root)
            baseline = resolver.resolve(
                REGISTRY,
                MATRIX,
                VARIANTS,
                "full_product",
                self.SIGNALS,
                project=Path(directory) / "empty",
            )
            effective = resolver.rigor_lib.load_effective(root)
            density = data["local"]["docs"]["density"]["value"]
        self.assertEqual(effective["level"], "standard")
        self.assertEqual(effective["knobs"]["qa.level"]["value"], "standard")
        self.assertEqual(density, "balanced")
        self.assertEqual(data["risk_floor"], baseline["risk_floor"])
        self.assertEqual(data["capabilities"], baseline["capabilities"])
        self.assertEqual(data["active_roles"], baseline["active_roles"])
        for risk, count in {"low": 1, "medium": 1, "high": 2, "critical": 2}.items():
            self.assertEqual(resolver.rigor_lib.reviewer_count(risk), count)
        reviewers = resolver.routing.evidence_reviewers({}, "high")
        self.assertIn("human", reviewers)
        self.assertEqual(
            len([role for role in reviewers if role.startswith("adversarial")]), 2
        )
        self.assertTrue(resolver.routing.human_gates("high", False))
        warnings = "\n".join(data["local"]["warnings"])
        for key in ("process.rigor", "qa.level", "risk.level", "gates.human"):
            self.assertIn(f"'{key}' kilitli", warnings)

    def test_nested_locked_keys_are_locked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(
                directory,
                {
                    "risk": {"auto_escalate": {"high": ["security"]}},
                    "gates": {"human": {"force": True}},
                },
            )
            data = self.resolve_in(root)
        local = data["local"]
        self.assertEqual(local["values"], {})
        warnings = "\n".join(local["warnings"])
        self.assertIn("'risk.auto_escalate.high' kilitli", warnings)
        self.assertIn("'gates.human.force' kilitli", warnings)
        self.assertNotIn("beyaz listede değil", warnings)

    def test_set_local_writes_allowed_and_rejects_locked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(
                directory,
                {"docs": {"density": "balanced"}, "team": {"size": "studio"}},
            )
            self.assertEqual(resolver.set_local(root, "docs.density=terse"), 0)
            written = yaml.safe_load(
                (root / ".kit" / "local.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(written["docs"]["density"], "terse")
            self.assertEqual(written["team"]["size"], "studio")
            self.assertEqual(resolver.set_local(root, "process.rigor=full"), 2)
            self.assertEqual(
                resolver.set_local(root, "routing.evidence_reviewers=2"), 2
            )
            self.assertEqual(resolver.set_local(root, "docs.density=deep"), 2)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "resolver.py"), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


class SetLocalCliTests(unittest.TestCase):
    def test_set_local_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ok = run_cli("--project", str(root), "--set-local", "docs.density=thorough")
            self.assertEqual(ok.returncode, 0, ok.stderr)
            locked = run_cli(
                "--project", str(root), "--set-local", "process.rigor=minimal"
            )
            self.assertEqual(locked.returncode, 2, locked.stderr)
            self.assertIn("kilitli", locked.stderr)


if __name__ == "__main__":
    unittest.main()
