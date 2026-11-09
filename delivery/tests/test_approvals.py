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


def issue_comment(
    login: str,
    association: str,
    issue: int = 48,
    by: str | None = None,
    decision: str = "accepted",
) -> dict:
    body = (
        "```yaml demir-kit-accept\n"
        'demir_kit_version: "2"\n'
        f"issue: {issue}\n"
        f"by: {by or login}\n"
        f"decision: {decision}\n"
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

    def test_human_acceptance_for_issue(self) -> None:
        record = approvals.human_acceptance_for(
            [issue_comment("human", "OWNER")], 48
        )
        self.assertIsNotNone(record)
        self.assertEqual(record["issue"], 48)
        self.assertEqual(record["by"], "human")

    def test_human_acceptance_for_rejects_agent_comment(self) -> None:
        self.assertIsNone(
            approvals.human_acceptance_for(
                [issue_comment("agent", "NONE", by="agent")], 48
            )
        )

    def test_human_acceptance_for_requires_matching_by(self) -> None:
        self.assertIsNone(
            approvals.human_acceptance_for(
                [issue_comment("human", "OWNER", by="someone-else")], 48
            )
        )

    def test_human_acceptance_for_other_issue_is_rejected(self) -> None:
        self.assertIsNone(
            approvals.human_acceptance_for(
                [issue_comment("human", "OWNER", issue=49)], 48
            )
        )

    def test_human_acceptance_for_latest_reject_revokes(self) -> None:
        accepted = issue_comment("human", "OWNER")
        rejected = issue_comment("human", "OWNER", decision="rejected")
        self.assertIsNone(
            approvals.human_acceptance_for([accepted, rejected], 48)
        )


class ApprovalContractTests(unittest.TestCase):
    def test_approval_contract_is_human_only(self) -> None:
        contract = (ROOT / "delivery" / "CONTRACT.md").read_text(encoding="utf-8")
        t2 = next(
            line for line in contract.splitlines() if line.startswith("| T2 |")
        )
        self.assertIn("insan", t2)
        self.assertIn("insan authored demir-kit-accept", t2)
        policy = (ROOT / "delivery" / "policies" / "approval.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Onay etiketi yalnız insan", policy)
        for name in ("VERSION", "README.md", "CHANGELOG.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("2.63.0", text)


if __name__ == "__main__":
    unittest.main()
