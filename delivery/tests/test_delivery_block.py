"""Tests for the AGENTS.md delivery entry block."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "delivery_block", SCRIPTS / "delivery_block.py"
)
delivery_block = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(delivery_block)


class DeliveryBlockTests(unittest.TestCase):
    def test_render_names_epic_worktree(self) -> None:
        block = delivery_block.render_block("demir-kit")
        self.assertIn("Epic başına **tek worktree**", block)
        self.assertIn("./demir-kit/delivery/scripts/next-leaf.sh --claim", block)
        self.assertIn("guard.sh --issue", block)
        self.assertIn("native subagent yalnız degrade modda", block)
        self.assertIn("Rebase yok", block)

    def test_inject_creates_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = delivery_block.inject(root, "demir-kit", apply=True)
            self.assertTrue(result["applied"])
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn(delivery_block.START, text)
            self.assertIn("epic-<N>", text)

    def test_inject_preserves_existing_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Agents\n\n- Kural\n", encoding="utf-8")
            delivery_block.inject(root, "", apply=True)
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("- Kural", text)
            self.assertIn(delivery_block.START, text)

    def test_inject_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delivery_block.inject(root, "", apply=True)
            first = (root / "AGENTS.md").read_text(encoding="utf-8")
            second = delivery_block.inject(root, "", apply=True)
            self.assertFalse(second["changed"])
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), first)

    def test_check_reports_missing_and_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(any("AGENTS.md yok" in item for item in delivery_block.check(root)))
            delivery_block.inject(root, "", apply=True)
            self.assertEqual(delivery_block.check(root, ""), [])
            (root / "AGENTS.md").write_text(
                (root / "AGENTS.md").read_text(encoding="utf-8").replace(
                    "Epic başına **tek worktree**", "Epic başına worktree"
                ),
                encoding="utf-8",
            )
            self.assertTrue(any("bayat" in item for item in delivery_block.check(root, "")))


if __name__ == "__main__":
    unittest.main()
