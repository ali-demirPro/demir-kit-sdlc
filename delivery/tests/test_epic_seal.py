"""Tests for epic seal validation."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("seal_lint", SCRIPTS / "seal_lint.py")
lint = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(lint)


def block(children: list[int]) -> str:
    return (
        "```yaml demir-kit-epic\n"
        "demir_kit_version: '2'\n"
        "summary: test\n"
        "scope_triage: {keep: [{item: iş}], defer: [], cut: []}\n"
        f"children: {children}\n"
        "```\n"
    )


class EpicSealTests(unittest.TestCase):
    def test_valid_epic_passes(self) -> None:
        labels = {"epic": ["epic", "scope-confirmed"], 10: ["enhancement"], 11: ["bug"]}
        body = block([10, 11])
        self.assertEqual(lint.validate_epic_record(body, ["epic"], {10: ["bug"], 11: ["bug"]}), [])

    def test_missing_block_is_an_error(self) -> None:
        errors = lint.validate_epic_record("## sadece metin\n", ["epic"])
        self.assertTrue(any("bloğu yok" in item for item in errors))

    def test_unterminated_fence_is_an_error(self) -> None:
        body = "```yaml demir-kit-epic\nchildren: [10]\n"
        errors = lint.validate_epic_record(body, ["epic"])
        self.assertTrue(any("kapanmamış" in item for item in errors))

    def test_empty_children_is_an_error(self) -> None:
        errors = lint.validate_epic_record(block([]), ["epic"])
        self.assertTrue(any("children boş" in item for item in errors))

    def test_unknown_child_is_an_error(self) -> None:
        errors = lint.validate_epic_record(block([99]), ["epic"], {})
        self.assertTrue(any("#99 yok" in item for item in errors))

    def test_child_epic_is_an_error(self) -> None:
        errors = lint.validate_epic_record(block([10]), ["epic"], {10: ["epic"]})
        self.assertTrue(any("epic olamaz" in item for item in errors))

    def test_leaf_issues_are_ignored(self) -> None:
        self.assertEqual(lint.validate_epic_record("", ["bug"]), [])


if __name__ == "__main__":
    unittest.main()
