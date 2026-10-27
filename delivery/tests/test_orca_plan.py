"""Tests for the Orca plan adapter."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import routing  # noqa: E402

spec = importlib.util.spec_from_file_location("orca_plan", SCRIPTS / "orca_plan.py")
orca_plan = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(orca_plan)

REGISTRY = routing.load_registry(ROOT)

BODY = """```yaml demir-kit
epic: 16
surfaces: [kit.docs]
risk: {level: medium}
checkpoints:
  - {id: CP-1, title: Adapter, gates: {behavior: true}}
  - {id: CP-2, title: UI, depends_on: [CP-1], gates: {behavior: true, ui: true}}
```
"""


class OrcaPlanTests(unittest.TestCase):
    def test_build_plan(self) -> None:
        plan = orca_plan.build_plan(
            REGISTRY, 17, "Orca: plan adapter", BODY, {"agent-approved"}
        )
        self.assertEqual(plan["issue"], 17)
        self.assertEqual(plan["path_id"], "pure_technical")
        self.assertEqual(plan["signal"], "kit_internal")
        self.assertEqual(len(plan["tasks"]), 2)

        first, second = plan["tasks"]
        self.assertEqual(first["id"], "CP-1")
        self.assertEqual(first["role"], "developer")
        self.assertEqual(second["id"], "CP-2")
        self.assertEqual(second["role"], "designer")
        self.assertEqual(second["deps"], ["task:CP-1"])

        self.assertIn("demir-kit #17 CP-1: Adapter", first["spec"])
        self.assertIn("Role: developer", first["spec"])
        self.assertIn(
            "doctor.sh --issue 17 --checkpoint CP-1", first["spec"]
        )
        self.assertNotIn("--product", first["spec"])
        self.assertIn("delivery/agents/designer/SKILL.md", second["spec"])

    def test_capability_aware_web_plan(self) -> None:
        body = """```yaml demir-kit
epic: 16
surfaces: [web.app]
factory: {stacks: [next]}
risk: {level: medium}
checkpoints:
  - {id: CP-1, title: Web, gates: {behavior: true}}
  - {id: CP-2, title: UI, depends_on: [CP-1], gates: {behavior: true, ui: true}}
```"""
        ecosystem = {
            "products": {
                "app": {
                    "surfaces": {
                        "web": {"platforms": ["web"], "stacks": ["next"]}
                    }
                }
            }
        }
        plan = orca_plan.build_plan(
            REGISTRY, 72, "Web leaf", body, {"agent-approved"}, ecosystem=ecosystem
        )
        self.assertIn("platform.web", plan["capabilities"])
        self.assertEqual(plan["tasks"][0]["role"], "developer")
        self.assertEqual(plan["tasks"][1]["role"], "designer")
        self.assertIn("developer/variants/web.md", plan["tasks"][0]["spec"])
        self.assertIn("designer/variants/web.md", plan["tasks"][1]["spec"])
        self.assertIn("tester", plan["tasks"][0]["reviewers"])

    def test_capability_aware_ios_and_api(self) -> None:
        ios_body = """```yaml demir-kit
epic: 16
surfaces: [ios.app]
factory: {stacks: [swiftui]}
risk: {level: critical}
checkpoints:
  - {id: CP-1, title: iOS, gates: {behavior: true}}
```"""
        ios_ecosystem = {
            "products": {
                "app": {
                    "surfaces": {
                        "ios": {
                            "platforms": ["ios"],
                            "stacks": ["swiftui"],
                            "distribution": ["app_store_connect"],
                        }
                    }
                }
            }
        }
        plan = orca_plan.build_plan(
            REGISTRY, 72, "iOS leaf", ios_body, {"agent-approved"}, ecosystem=ios_ecosystem
        )
        self.assertIn("platform.ios", plan["capabilities"])
        self.assertIn("distribution.app_store", plan["capabilities"])
        self.assertIn("developer/variants/ios.md", plan["tasks"][0]["spec"])
        self.assertEqual(plan["effective_risk"], "critical")
        self.assertIn("release", plan["tasks"][0]["reviewers"])
        self.assertIn("marketing/stores", plan["tasks"][0]["reviewers"])
        self.assertIn("architect", plan["tasks"][0]["reviewers"])
        self.assertIn("security", plan["tasks"][0]["reviewers"])

        api_body = """```yaml demir-kit
epic: 16
surfaces: [api]
factory: {stacks: [python]}
risk: {level: medium}
checkpoints:
  - {id: CP-1, title: API, gates: {behavior: true}}
```"""
        api_ecosystem = {
            "products": {
                "app": {
                    "surfaces": {
                        "api": {"platforms": ["api"], "stacks": ["python"]}
                    }
                }
            }
        }
        plan = orca_plan.build_plan(
            REGISTRY, 72, "API leaf", api_body, {"agent-approved"}, ecosystem=api_ecosystem
        )
        self.assertIn("platform.api", plan["capabilities"])
        self.assertIn("developer/variants/api.md", plan["tasks"][0]["spec"])
        self.assertNotIn("designer/variants/web.md", plan["tasks"][0]["spec"])

    def test_high_risk_plan_adds_security_and_architect(self) -> None:
        body = """```yaml demir-kit
epic: 16
surfaces: [web.app]
factory: {stacks: [next]}
risk: {level: high}
checkpoints:
  - {id: CP-1, title: Web, gates: {behavior: true}}
```"""
        plan = orca_plan.build_plan(
            REGISTRY,
            72,
            "High risk web leaf",
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
        self.assertEqual(plan["effective_risk"], "high")
        self.assertIn("architect", plan["tasks"][0]["reviewers"])
        self.assertIn("security", plan["tasks"][0]["reviewers"])
        self.assertFalse(plan["variant_gaps"])

    def test_critical_plan_adds_commercial_reviewers(self) -> None:
        body = """```yaml demir-kit
epic: 16
surfaces: [web.app]
factory: {stacks: [next]}
risk: {level: critical}
checkpoints:
  - {id: CP-1, title: Web, gates: {behavior: true}}
```"""
        plan = orca_plan.build_plan(
            REGISTRY,
            72,
            "Critical web",
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
        self.assertIn("release", plan["tasks"][0]["reviewers"])
        self.assertIn("marketing/stores", plan["tasks"][0]["reviewers"])

    def test_leaf_surface_filters_multi_surface_project(self) -> None:
        body = """```yaml demir-kit
epic: 16
surfaces: [web.app]
factory: {stacks: [next]}
risk: {level: medium}
checkpoints:
  - {id: CP-1, title: Web, gates: {behavior: true}}
```"""
        ecosystem = {
            "products": {
                "app": {
                    "surfaces": {
                        "web": {"platforms": ["web"], "stacks": ["next"]},
                        "ios": {
                            "platforms": ["ios"],
                            "stacks": ["swiftui"],
                            "distribution": ["app_store_connect"],
                        },
                    }
                }
            }
        }
        plan = orca_plan.build_plan(
            REGISTRY, 72, "Web leaf", body, {"agent-approved"}, ecosystem=ecosystem
        )
        self.assertEqual(plan["capabilities"], ["platform.web"])
        self.assertNotIn("platform.ios", plan["capabilities"])
        self.assertNotIn("developer/variants/ios.md", plan["tasks"][0]["spec"])

    def test_distribution_web_uses_landing_not_stores(self) -> None:
        body = """```yaml demir-kit
epic: 16
surfaces: [web.app]
factory: {stacks: [next]}
risk: {level: medium}
checkpoints:
  - {id: CP-1, title: Web, gates: {behavior: true}}
```"""
        ecosystem = {
            "products": {
                "app": {
                    "surfaces": {
                        "web": {
                            "platforms": ["web"],
                            "stacks": ["next"],
                            "distribution": ["web_deploy"],
                        }
                    }
                }
            }
        }
        plan = orca_plan.build_plan(
            REGISTRY, 72, "Web deploy", body, {"agent-approved"}, ecosystem=ecosystem
        )
        self.assertIn("distribution.web", plan["capabilities"])
        self.assertIn("release", plan["tasks"][0]["reviewers"])
        self.assertIn("marketing/landing", plan["tasks"][0]["reviewers"])
        self.assertNotIn("marketing/stores", plan["tasks"][0]["reviewers"])

    def test_product_prefix(self) -> None:
        plan = orca_plan.build_plan(
            REGISTRY, 35, "Product", BODY, {"agent-approved"}, prefix="demir-kit/"
        )
        spec = plan["tasks"][0]["spec"]
        self.assertIn("demir-kit/delivery/CONTRACT.md", spec)
        self.assertIn("demir-kit/delivery/agents/developer/SKILL.md", spec)
        self.assertIn("--product --root .", spec)

    def test_write_plan(self) -> None:
        plan = orca_plan.build_plan(
            REGISTRY, 17, "Orca: plan adapter", BODY, {"agent-approved"}
        )
        with tempfile.TemporaryDirectory() as directory:
            written = orca_plan.write_plan(plan, Path(directory))
            names = {path.name for path in written}
            self.assertEqual(names, {"plan.json", "CP-1.md", "CP-2.md"})
            self.assertIn(
                "demir-kit #17 CP-2",
                (Path(directory) / "CP-2.md").read_text(encoding="utf-8"),
            )

    def test_plan_is_deterministic(self) -> None:
        first = json.dumps(
            orca_plan.build_plan(
                REGISTRY, 17, "x", BODY, {"agent-approved"}
            ),
            sort_keys=True,
        )
        second = json.dumps(
            orca_plan.build_plan(
                REGISTRY, 17, "x", BODY, {"agent-approved"}
            ),
            sort_keys=True,
        )
        self.assertEqual(first, second)

    def test_main_passes_product_prefix(self) -> None:
        captured = {}

        def fake_build(registry, issue, title, body, labels, prefix=""):
            captured["prefix"] = prefix
            return {"issue": issue, "title": title, "tasks": [], "path_id": "x"}

        with patch.object(orca_plan, "repo_name", return_value="owner/product"), patch.object(
            orca_plan, "gh", return_value=json.dumps({"title": "t", "body": "b", "labels": []})
        ), patch.object(orca_plan.routing, "kit_prefix", return_value="demir-kit/"), patch.object(
            orca_plan, "build_plan", fake_build
        ), patch.object(
            sys, "argv", ["orca_plan.py", "35", "--json"]
        ):
            orca_plan.main()
        self.assertEqual(captured["prefix"], "demir-kit/")

    def test_leaf_without_checkpoints(self) -> None:
        body = "```yaml demir-kit\nsurfaces: [kit.docs]\ncheckpoints: []\n```"
        plan = orca_plan.build_plan(
            REGISTRY, 17, "x", body, {"agent-approved"}
        )
        self.assertEqual(plan["tasks"], [])

    def test_unsealed_issue_raises(self) -> None:
        with self.assertRaises(ValueError):
            orca_plan.build_plan(REGISTRY, 17, "x", "no seal", {"agent-approved"})

    def test_unapproved_issue_raises(self) -> None:
        with self.assertRaises(ValueError):
            orca_plan.build_plan(REGISTRY, 17, "x", BODY, set())


if __name__ == "__main__":
    unittest.main()
