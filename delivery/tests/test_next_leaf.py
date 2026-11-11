"""Tests for lease-based leaf claiming."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
        ) as snapshot, patch.object(
            next_leaf, "now", return_value=fixed
        ), patch.object(
            next_leaf, "claim_context", return_value=(0, "")
        ):
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

    def test_dirty_sources_block_when_no_work(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with patch.object(next_leaf, "gh", return_value="[]"), patch.object(
            next_leaf.process_gate, "dirty_sources", return_value=["App/x.swift"]
        ), patch.object(sys, "argv", ["next-leaf.py", "--list"]), redirect_stdout(
            out
        ), redirect_stderr(err):
            code = next_leaf.main()
        self.assertEqual(code, 1)
        self.assertIn("BLOCKED", err.getvalue())
        self.assertIn("App/x.swift", err.getvalue())


def seal_body(epic: int, path: str) -> str:
    return (
        "```yaml demir-kit\n"
        "demir_kit_version: '2'\n"
        f"epic: {epic}\n"
        "reference:\n"
        "  kind: github_paths\n"
        f"  paths: [{path}]\n"
        "```\n"
    )


def leaf(number: int, created: str, epic: int = 11, path: str | None = None) -> dict:
    return {
        "number": number,
        "title": f"leaf {number}",
        "state": "OPEN",
        "body": seal_body(epic, path or f"delivery/scripts/leaf-{number}.py"),
        "labels": [{"name": "agent-approved"}],
        "createdAt": created,
    }


class ClaimRunIdTests(unittest.TestCase):
    """#319: a claim must never repoint an epic run that already owns tasks."""

    def ensure(self, record: dict, responses: dict) -> tuple[dict, list[list[str]]]:
        calls: list[list[str]] = []

        def fake_orca_json(args, _project):
            calls.append(args)
            return responses.get(args[1])

        with patch.object(
            next_leaf.epic_worktree, "orca_json", side_effect=fake_orca_json
        ):
            result = next_leaf.epic_worktree.ensure_run(
                Path("/tmp/repo"), 323, record
            )
        return result, calls

    def test_existing_run_with_tasks_is_kept(self) -> None:
        record = {"epic": 323, "mode": "orca", "run_id": "run_keep", "tasks": []}
        responses = {
            "task-list": {"ok": True, "result": {"tasks": [{"id": "task_1"}]}},
            "run-current": {
                "ok": True,
                "result": {"runId": "run_other", "objective": "epic #323"},
            },
        }
        result, calls = self.ensure(record, responses)
        self.assertEqual(result["run_id"], "run_keep")
        self.assertNotIn("run_warning", result)
        self.assertFalse(any("run-current" in call for call in calls))

    def test_existing_run_without_tasks_warns_and_is_kept(self) -> None:
        record = {"epic": 323, "mode": "orca", "run_id": "run_empty", "tasks": []}
        responses = {
            "task-list": {"ok": True, "result": {"tasks": []}},
            "run-current": {
                "ok": True,
                "result": {"runId": "run_other", "objective": "epic #323"},
            },
        }
        result, calls = self.ensure(record, responses)
        self.assertEqual(result["run_id"], "run_empty")
        self.assertIn("run_warning", result)
        self.assertFalse(any("run-current" in call for call in calls))

    def test_empty_run_id_is_written(self) -> None:
        record = {"epic": 323, "mode": "orca", "run_id": None, "tasks": []}
        responses = {
            "run-current": {
                "ok": True,
                "result": {"runId": "run_new", "objective": "epic #323"},
            },
        }
        result, _ = self.ensure(record, responses)
        self.assertEqual(result["run_id"], "run_new")
        self.assertNotIn("run_warning", result)

    def test_prepare_worktree_surfaces_run_warning(self) -> None:
        record = {
            "name": "epic-44",
            "path": "/tmp/epic-44",
            "branch": "epic-44",
            "run_warning": "run empty-run task içermiyor",
        }
        err = io.StringIO()
        with patch.object(
            next_leaf.epic_worktree, "epic_worktree_enabled", return_value=True
        ), patch.object(
            next_leaf.epic_worktree, "ensure", return_value=record
        ), patch.object(
            next_leaf.budget, "load", return_value={}
        ), redirect_stderr(err):
            self.assertEqual(next_leaf.prepare_worktree(46, 44), 0)
        self.assertIn("task içermiyor", err.getvalue())


class ClaimContextGateTests(unittest.TestCase):
    """T-2 (AC-2): 300k aşımında claim `blocked` üretir ve gerekçe yazar."""

    def test_claim_context_hard_limit_runs_usage_check(self) -> None:
        with patch.object(
            next_leaf.usage, "current_context_tokens", return_value=350_000
        ):
            code, message = next_leaf.claim_context()
        self.assertEqual(code, 1)
        self.assertIn("300,000", message)

    def test_claim_context_below_hard_limit_passes(self) -> None:
        with patch.object(
            next_leaf.usage, "current_context_tokens", return_value=120_000
        ):
            self.assertEqual(next_leaf.claim_context(), (0, ""))

    def test_claim_context_warn_band_warns_but_passes(self) -> None:
        with patch.object(
            next_leaf.usage, "current_context_tokens", return_value=250_000
        ):
            code, message = next_leaf.claim_context()
        self.assertEqual(code, 0)
        self.assertIn("200,000", message)

    def test_claim_context_unmeasurable_skips_check(self) -> None:
        with patch.object(
            next_leaf.usage, "current_context_tokens", return_value=None
        ):
            self.assertEqual(next_leaf.claim_context(), (0, ""))

    def test_measured_hard_limit_blocks_claim_and_writes_rationale(self) -> None:
        before = issue([])
        calls: list[list[str]] = []

        def fake_gh(args):
            calls.append(args)
            return ""

        with patch.object(
            next_leaf, "fetch_issue", return_value=before
        ), patch.object(
            next_leaf, "gh", side_effect=fake_gh
        ), patch.object(
            next_leaf, "gh_optional", side_effect=fake_gh
        ), patch.object(
            next_leaf, "write_snapshot"
        ) as snapshot, patch.object(
            next_leaf.usage, "current_context_tokens", return_value=350_000
        ):
            result = next_leaf.claim(46, 44, "medium")
        self.assertEqual(result, 1)
        joined = [" ".join(call) for call in calls]
        self.assertTrue(
            any("--add-label" in call and "blocked" in call for call in joined),
            joined,
        )
        self.assertTrue(
            any("run blocked:" in call and "300,000" in call for call in joined),
            joined,
        )
        self.assertFalse(any("run claim:" in call for call in joined), joined)
        self.assertFalse(any("--add-label executing" in call for call in joined), joined)
        snapshot.assert_not_called()

    def test_warn_band_claim_proceeds(self) -> None:
        fixed = datetime(2026, 11, 11, 9, 0, 0, tzinfo=timezone.utc)
        run_id = "run-20261111T090000000000Z"
        after = issue([comment(11, f"run claim: `{run_id}`", fixed)])
        calls: list[list[str]] = []

        def fake_gh(args):
            calls.append(args)
            return ""

        with patch.object(
            next_leaf, "fetch_issue", side_effect=[issue([]), after]
        ), patch.object(
            next_leaf, "gh", side_effect=fake_gh
        ), patch.object(
            next_leaf, "gh_optional", side_effect=fake_gh
        ), patch.object(
            next_leaf, "write_snapshot"
        ), patch.object(
            next_leaf, "now", return_value=fixed
        ), patch.object(
            next_leaf, "claim_context", return_value=(
                0,
                "bağlam 250,000 token ≥ 200,000 — özet yaz, yeni oturuma geç",
            )
        ):
            result = next_leaf.claim(46, 44, "medium")
        self.assertEqual(result, 0)
        joined = [" ".join(call) for call in calls]
        self.assertFalse(any("--add-label blocked" in call for call in joined))
        self.assertTrue(any("--add-label executing" in call for call in joined))


class ExplicitIssueTests(unittest.TestCase):
    def test_explicit_issue_ignores_other_leaves_budget(self) -> None:
        # gh returns newest first; the older explicit leaf must still be eligible.
        open_issues = [
            leaf(41, "2026-11-08T12:00:00Z"),
            leaf(40, "2026-11-08T11:00:00Z"),
            leaf(39, "2026-11-08T10:00:00Z"),
        ]
        eligible, skipped = next_leaf.select_eligible(
            open_issues, open_issues, max_parallel=1, only=39
        )
        self.assertEqual([item["number"] for item in eligible], [39])
        self.assertEqual(skipped, [])

    def test_explicit_issue_still_honours_dependencies(self) -> None:
        body = (
            "```yaml demir-kit\n"
            "epic: 11\n"
            "dependencies:\n"
            "- {kind: blocks, issue: 900}\n"
            "```\n"
        )
        target = leaf(39, "2026-11-08T10:00:00Z")
        target["body"] = body
        eligible, skipped = next_leaf.select_eligible(
            [target], [target], max_parallel=2, only=39
        )
        self.assertEqual(eligible, [])
        self.assertEqual(skipped[0]["reason"], "bağımlılık bekliyor")


class OrderTests(unittest.TestCase):
    def test_eligible_order_is_stable(self) -> None:
        rows = [
            leaf(43, "2026-11-08T12:00:00Z"),
            leaf(41, "2026-11-08T10:00:00Z"),
            leaf(42, "2026-11-08T11:00:00Z"),
        ]
        first, _ = next_leaf.select_eligible(rows, rows, max_parallel=5)
        second, _ = next_leaf.select_eligible(list(reversed(rows)), rows, max_parallel=5)
        self.assertEqual([item["number"] for item in first], [41, 42, 43])
        self.assertEqual(
            [item["number"] for item in first], [item["number"] for item in second]
        )


class NoResourceGatingTests(unittest.TestCase):
    def test_control_plane_does_not_gate_on_machine_pressure(self) -> None:
        for name in ("next-leaf.py", "orca_wave.py", "review_wave.py"):
            source = (SCRIPTS / name).read_text(encoding="utf-8")
            self.assertNotIn("resources.blocked", source, name)


if __name__ == "__main__":
    unittest.main()
