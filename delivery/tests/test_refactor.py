"""Refactor policy and playbook content tests (issue #114).

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRIGGERS = ROOT / "delivery" / "policies" / "refactor-triggers.md"
PLAYBOOK = ROOT / "delivery" / "agents" / "architect" / "variants" / "refactor.md"
CLOSURE = ROOT / "delivery" / "runbooks" / "epic-closure.md"


class RefactorDocsTest(unittest.TestCase):
    def test_policy_has_six_triggers_each_with_a_command(self) -> None:
        rows = [
            line
            for line in TRIGGERS.read_text(encoding="utf-8").splitlines()
            if line.startswith("| ")
        ]
        body = [
            line
            for line in rows
            if not line.startswith("| Tetik")
            and not set(line) <= set("|-: ")
        ]
        self.assertEqual(len(body), 6, body)
        for row in body:
            self.assertIn("`", row, row)

    def test_playbook_has_the_seven_sections(self) -> None:
        headings = [
            line[3:].strip()
            for line in PLAYBOOK.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")
        ]
        self.assertEqual(
            headings,
            [
                "Kapsam",
                "Girdiler",
                "Yöntem",
                "Kanıt",
                "Gate rubriği",
                "Anti-pattern'ler",
                "Handoff",
            ],
        )

    def test_closure_runbook_has_debt_check_in(self) -> None:
        text = CLOSURE.read_text(encoding="utf-8")
        self.assertIn("Borç check-in", text)
        self.assertIn("refactor-triggers.md", text)


if __name__ == "__main__":
    unittest.main()
