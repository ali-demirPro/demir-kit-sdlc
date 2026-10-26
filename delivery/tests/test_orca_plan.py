"""Tests for the Orca plan adapter."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
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
        self.assertIn("delivery/agents/designer/SKILL.md", second["spec"])

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
