"""Tests for parallel leaves inside one epic."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("next_leaf_p", SCRIPTS / "next-leaf.py")
next_leaf = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(next_leaf)


def issue(
    number: int,
    epic: int | None = 213,
    paths: list[str] | None = None,
    labels: tuple[str, ...] = ("agent-approved",),
    deps: list[int] | None = None,
    created: str = "2026-11-01T00:00:00Z",
) -> dict:
    seal = {
        "demir_kit_version": "2",
        "epic": epic,
        "reference": {"kind": "github_paths", "paths": paths or []},
        "dependencies": [{"issue": dep} for dep in deps or []],
        "risk": {"level": "low"},
    }
    body = "```yaml demir-kit\n" + yaml.safe_dump(seal, sort_keys=False) + "```\n"
    return {
        "number": number,
        "title": f"#{number}",
        "state": "OPEN",
        "labels": [{"name": name} for name in labels],
        "body": body,
        "createdAt": created,
    }


class SelectTests(unittest.TestCase):
    def test_disjoint_leaves_run_together(self) -> None:
        issues = [
            issue(1, paths=["delivery/scripts/a.py"]),
            issue(2, paths=["delivery/scripts/b.py"]),
        ]
        eligible = next_leaf.select_eligible(issues, issues)
        self.assertEqual([item["number"] for item in eligible], [1, 2])

    def test_same_file_waits(self) -> None:
        issues = [
            issue(1, paths=["delivery/scripts/a.py"]),
            issue(2, paths=["delivery/scripts/a.py"]),
        ]
        eligible = next_leaf.select_eligible(issues, issues)
        self.assertEqual([item["number"] for item in eligible], [1])

    def test_max_parallel_one_keeps_the_old_behaviour(self) -> None:
        issues = [
            issue(1, paths=["a.py"]),
            issue(2, paths=["b.py"]),
        ]
        eligible = next_leaf.select_eligible(issues, issues, max_parallel=1)
        self.assertEqual([item["number"] for item in eligible], [1])

    def test_running_leaves_fill_the_budget(self) -> None:
        issues = [
            issue(1, labels=("agent-approved", "executing"), paths=["a.py"]),
            issue(2, labels=("agent-approved", "executing"), paths=["b.py"]),
            issue(3, paths=["c.py"]),
        ]
        eligible = next_leaf.select_eligible(issues, issues, max_parallel=2)
        self.assertEqual(eligible, [])

    def test_running_leaf_blocks_same_surface(self) -> None:
        issues = [
            issue(1, labels=("agent-approved", "executing"), paths=["a.py"]),
            issue(2, paths=["a.py"]),
            issue(3, paths=["c.py"]),
        ]
        eligible = next_leaf.select_eligible(issues, issues, max_parallel=2)
        self.assertEqual([item["number"] for item in eligible], [3])

    def test_dependency_blocks_until_done(self) -> None:
        issues = [issue(2, paths=["b.py"], deps=[1])]
        self.assertEqual(next_leaf.select_eligible(issues, issues), [])
        closed = [dict(issue(1, paths=["a.py"]), state="CLOSED")]
        eligible = next_leaf.select_eligible(issues, closed + issues)
        self.assertEqual([item["number"] for item in eligible], [2])


if __name__ == "__main__":
    unittest.main()
