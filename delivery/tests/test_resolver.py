"""Tests for capability/variant resolution."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
