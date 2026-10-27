"""Tests for human acceptance parsing."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("approvals", SCRIPTS / "approvals.py")
approvals = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(approvals)


def comment(login: str, association: str, epic: int = 1) -> dict:
    body = (
        "```yaml demir-kit-accept\n"
        'demir_kit_version: "2"\n'
        f"epic: {epic}\n"
        f"by: {login}\n"
        "decision: accepted\n"
        "```\n"
    )
    return {
        "body": body,
        "user": {"login": login},
        "author_association": association,
    }


class ApprovalTests(unittest.TestCase):
    def test_human_acceptance(self) -> None:
        record = approvals.human_acceptance([comment("human", "MEMBER")], 1)
        self.assertIsNotNone(record)
        self.assertEqual(record["by"], "human")

    def test_bot_is_rejected(self) -> None:
        self.assertIsNone(
            approvals.human_acceptance([comment("github-actions[bot]", "NONE")], 1)
        )

    def test_wrong_epic_is_rejected(self) -> None:
        self.assertIsNone(
            approvals.human_acceptance([comment("human", "OWNER", epic=2)], 1)
        )

    def test_by_must_match_author(self) -> None:
        item = comment("human", "MEMBER")
        item["body"] = item["body"].replace("by: human", "by: someone-else")
        self.assertIsNone(approvals.human_acceptance([item], 1))

    def test_latest_reject_revokes_acceptance(self) -> None:
        accepted = comment("human", "MEMBER")
        rejected = comment("human", "MEMBER")
        rejected["body"] = rejected["body"].replace(
            "decision: accepted", "decision: rejected"
        )
        self.assertIsNone(approvals.human_acceptance([accepted, rejected], 1))

    def test_missing_by_is_rejected(self) -> None:
        item = comment("human", "MEMBER").copy()
        item["body"] = (
            "```yaml demir-kit-accept\n"
            'demir_kit_version: "2"\n'
            "epic: 1\n"
            "decision: accepted\n"
            "```\n"
        )
        self.assertIsNone(approvals.human_acceptance([item], 1))

    def test_latest_human_acceptance_wins(self) -> None:
        first = comment("human", "MEMBER")
        second = comment("owner", "OWNER")
        record = approvals.human_acceptance([first, second], 1)
        self.assertEqual(record["by"], "owner")


if __name__ == "__main__":
    unittest.main()
