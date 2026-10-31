"""Tests for lease-based leaf claiming."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("next_leaf", SCRIPTS / "next-leaf.py")
next_leaf = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(next_leaf)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def comment(identifier: int, body: str, created: datetime | None = None) -> dict:
    """REST comment payload, which is what `fetch_comments` consumes."""
    return {
        "id": identifier,
        "url": f"https://api.github.com/repos/owner/repo/issues/comments/{identifier}",
        "body": body,
        "created_at": iso(created or next_leaf.now()),
    }


def issue(comments: list[dict], **overrides) -> dict:
    data = {
        "number": 46,
        "title": "Claim lease",
        "state": "OPEN",
        "body": "",
        "labels": [],
        "assignees": [],
        "comments": comments,
    }
    data.update(overrides)
    return data


class LeaseTests(unittest.TestCase):
    def test_comment_id_reads_rest_int(self) -> None:
        self.assertEqual(next_leaf.comment_id(comment(42, "x")), 42)

    def test_comment_id_reads_issuecomment_url(self) -> None:
        item = {
            "id": "IC_kwDOUzM8Nc8AAAABftzJeA",
            "url": "https://github.com/o/r/issues/46#issuecomment-6423366008",
        }
        self.assertEqual(next_leaf.comment_id(item), 6423366008)

    def test_naive_lease_until_is_treated_as_utc(self) -> None:
        current = datetime(2026, 10, 26, 18, 0, tzinfo=timezone.utc)
        data = issue(
            [
                comment(
                    10,
                    "run claim: `r1`\nlease_until: `2026-10-26T20:00:00`",
                    current - timedelta(minutes=30),
                )
            ]
        )
        state = next_leaf.lease_state(data, at=current)
        self.assertFalse(state["expired"])

    def test_fetch_comments_paginates(self) -> None:
        pages = {1: [comment(index, "x") for index in range(100)], 2: [comment(100, "last")]}

        def fake_gh(args):
            page = int(args[-1].rsplit("page=", 1)[1])
            return json.dumps(pages.get(page, []))

        with patch.object(next_leaf, "gh", side_effect=fake_gh):
            comments = next_leaf.fetch_comments("owner/repo", 46)
        self.assertEqual(len(comments), 101)

    def test_claim_winner_ignores_before_release(self) -> None:
        current = next_leaf.now()
        data = issue(
            [
                comment(1, "run claim: `old`", current - timedelta(hours=3)),
                comment(2, "run release: `old`\nreason: stale", current - timedelta(hours=2)),
                comment(3, "run claim: `new-a`", current - timedelta(minutes=5)),
                comment(4, "run claim: `new-b`", current - timedelta(minutes=4)),
            ]
        )
        self.assertEqual(next_leaf.claim_winner(data), 3)

    def test_lease_expires_after_two_hours(self) -> None:
        current = next_leaf.now()
        data = issue([comment(10, "run claim: `r1`", current - timedelta(hours=3))])
        state = next_leaf.lease_state(data, at=current)
        self.assertTrue(state["expired"])
        self.assertEqual(state["run_id"], "r1")

    def test_active_lease_is_not_expired(self) -> None:
        current = next_leaf.now()
        data = issue([comment(10, "run claim: `r1`", current - timedelta(minutes=30))])
        state = next_leaf.lease_state(data, at=current)
        self.assertFalse(state["expired"])

    def test_release_refuses_active_lease(self) -> None:
        current = next_leaf.now()
        data = issue(
            [comment(10, "run claim: `r1`", current - timedelta(minutes=30))],
            labels=[{"name": "executing"}],
        )
        with patch.object(next_leaf, "fetch_issue", return_value=data):
            with self.assertRaises(SystemExit):
                next_leaf.release(46, False, "stale")

    def test_release_refuses_evidence_without_force(self) -> None:
        current = next_leaf.now()
        data = issue(
            [
                comment(10, "run claim: `r1`", current - timedelta(minutes=30)),
                comment(11, "```yaml demir-kit-evidence\nstatus: pass\n```", current),
            ],
            labels=[{"name": "executing"}],
        )
        with patch.object(next_leaf, "fetch_issue", return_value=data):
            with self.assertRaises(SystemExit):
                next_leaf.release(46, False, "stale")

    def test_release_stale_cleans_label_and_assignee(self) -> None:
        current = next_leaf.now()
        data = issue(
            [comment(10, "run claim: `r1`", current - timedelta(hours=3))],
            labels=[{"name": "executing"}],
            assignees=[{"login": "alice"}],
        )
        calls: list[list[str]] = []
        with patch.object(next_leaf, "fetch_issue", return_value=data), patch.object(
            next_leaf, "gh_optional", side_effect=lambda args: calls.append(args) or ""
        ), patch.object(
            next_leaf, "gh", side_effect=lambda args: calls.append(args) or ""
        ):
            self.assertEqual(next_leaf.release(46, False, "stale"), 0)
        self.assertTrue(any("--remove-label" in call for call in calls))
        self.assertTrue(any("--remove-assignee" in call for call in calls))
        self.assertTrue(any("run release:" in " ".join(call) for call in calls))

    def test_claim_refuses_active_lease_without_label(self) -> None:
        current = next_leaf.now()
        data = issue([comment(10, "run claim: `r1`", current - timedelta(minutes=30))])
        with patch.object(next_leaf, "fetch_issue", return_value=data):
            with self.assertRaises(SystemExit):
                next_leaf.claim(46, 44, "medium")

    def test_claim_loser_removes_assignee(self) -> None:
        fixed = datetime(2026, 10, 26, 18, 0, 0, tzinfo=timezone.utc)
        run_id = "run-20261026T180000000000Z"
        before = issue([])
        after = issue(
            [
                comment(10, "run claim: `other`", fixed),
                comment(11, f"run claim: `{run_id}`", fixed),
            ]
        )
        calls: list[list[str]] = []

        def fake_optional(args):
            calls.append(args)
            return ""

        with patch.object(
            next_leaf, "fetch_issue", side_effect=[before, after]
        ), patch.object(next_leaf, "gh", return_value=""), patch.object(
            next_leaf, "gh_optional", side_effect=fake_optional
        ), patch.object(
            next_leaf, "write_snapshot"
        ) as snapshot, patch.object(next_leaf, "now", return_value=fixed):
            self.assertEqual(next_leaf.claim(46, 44, "medium"), 1)
        snapshot.assert_not_called()
        self.assertTrue(
            any("--remove-assignee" in call for call in calls)
        )

    def test_prepare_worktree_is_noop_when_disabled(self) -> None:
        with patch.object(
            next_leaf.epic_worktree, "epic_worktree_enabled", return_value=False
        ):
            self.assertEqual(next_leaf.prepare_worktree(46, 44), 0)

    def test_prepare_worktree_reports_failure(self) -> None:
        with patch.object(
            next_leaf.epic_worktree, "epic_worktree_enabled", return_value=True
        ), patch.object(
            next_leaf.epic_worktree,
            "ensure",
            side_effect=next_leaf.epic_worktree.WorktreeError("boom"),
        ):
            self.assertEqual(next_leaf.prepare_worktree(46, 44), 1)


if __name__ == "__main__":
    unittest.main()
