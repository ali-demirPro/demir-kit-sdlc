"""Bağlam bütçesi eşiklerinin doküman ve brief metinleriyle uyumu."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ContextBudgetDocsTests(unittest.TestCase):
    def test_policy_states_the_current_limits(self) -> None:
        text = (ROOT / "delivery" / "policies" / "context-budget.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("200k token", text)
        self.assertIn("300k token", text)

    def test_agents_md_states_the_current_limits(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("200k tokens warns, 300k stops", text)
        self.assertNotIn("120k tokens warns", text)

    def test_brief_states_the_current_limits(self) -> None:
        text = (ROOT / "delivery" / "scripts" / "brief.py").read_text(encoding="utf-8")
        self.assertIn("200k'da uyar, 300k'da dur", text)
        self.assertNotIn("120k'da uyar", text)


if __name__ == "__main__":
    unittest.main()
