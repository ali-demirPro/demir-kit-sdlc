"""Tests for single-writer state transitions."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("transition", SCRIPTS / "transition.py")
transition = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(transition)


def fenced(tag: str, data: dict) -> str:
    import yaml

    return f"```yaml {tag}\n{yaml.safe_dump(data, sort_keys=False)}\n```\n"


def leaf_issue(labels: list[str], comments: list[dict] | None = None) -> dict:
    return {
        "number": 48,
        "title": "Transition",
        "state": "OPEN",
        "body": fenced("demir-kit", {"epic": 44, "risk": {"level": "medium"}}),
        "labels": [{"name": name} for name in labels],
        "comments": comments or [],
    }


def epic_issue(labels: list[str], comments: list[dict] | None = None) -> dict:
    return {
        "number": 44,
        "title": "Epic",
        "state": "OPEN",
        "body": fenced(
            "demir-kit-epic",
            {
                "demir_kit_version": "2",
                "summary": "Yeterince uzun bir epic ozeti.",
                "scope_triage": {
                    "keep": [{"item": "bir is"}],
                    "defer": [],
                    "cut": [],
                },
                "children": [48],
            },
        ),
        "labels": [{"name": name} for name in labels],
        "comments": comments or [],
    }


def closure(status: str = "pass") -> dict:
    return {
        "demir_kit_version": "2",
        "epic": 44,
        "status": status,
        "gaps": [] if status == "pass" else [{"kind": "gap", "note": "eksik"}],
        "unnecessary": [],
        "deferred": [],
        "metrics": {
            "leaf_count": 1,
            "cp_count": 1,
            "gate_retries": 0,
            "reconcile_issues": 0,
            "human_interventions": 0,
            "lead_time_hours": 0.1,
        },
        "ready_for_human_qa": True,
    }


def run_transition(argv: list[str]) -> int:
    with patch.object(sys, "argv", ["transition.py", *argv]):
        return transition.main()


class TransitionTests(unittest.TestCase):
    def test_scope_confirmed_epic_writes_labels(self) -> None:
        issue = epic_issue(["intake"])
        calls: list[list[str]] = []
        comments: list[str] = []
        with patch.object(transition, "fetch_issue", return_value=issue), patch.object(
            transition, "doctor_ok", return_value=(True, "")
        ), patch.object(
            transition, "gh", side_effect=lambda args: calls.append(args) or ""
        ), patch.object(
            transition, "post_comment", side_effect=lambda number, body: comments.append(body)
        ):
            self.assertEqual(run_transition(["--issue", "44", "--to", "scope-confirmed"]), 0)
        self.assertTrue(any("--add-label" in call and "scope-confirmed" in call for call in calls))
        self.assertTrue(any("--remove-label" in call and "intake" in call for call in calls))
        self.assertTrue(any("run transition:" in body for body in comments))

    def test_leaf_done_preflight_failure_writes_nothing(self) -> None:
        issue = leaf_issue(["executing"])
        calls: list[list[str]] = []
        with patch.object(transition, "fetch_issue", return_value=issue), patch.object(
            transition, "doctor_ok", return_value=(False, "bad gate")
        ), patch.object(
            transition, "gh", side_effect=lambda args: calls.append(args) or ""
        ):
            with self.assertRaises(SystemExit):
                run_transition(["--issue", "48", "--to", "leaf-done"])
        self.assertEqual(calls, [])

    def test_dry_run_does_not_write(self) -> None:
        issue = leaf_issue(["executing"])
        calls: list[list[str]] = []
        with patch.object(transition, "fetch_issue", return_value=issue), patch.object(
            transition, "doctor_ok", return_value=(True, "")
        ), patch.object(
            transition, "gh", side_effect=lambda args: calls.append(args) or ""
        ):
            self.assertEqual(
                run_transition(["--issue", "48", "--to", "leaf-done", "--dry-run"]), 0
            )
        self.assertEqual(calls, [])

    def test_idempotent_noop(self) -> None:
        issue = leaf_issue(["leaf-done"])
        with patch.object(transition, "fetch_issue", return_value=issue), patch.object(
            transition, "doctor_ok"
        ) as doctor, patch.object(transition, "gh") as gh:
            self.assertEqual(run_transition(["--issue", "48", "--to", "leaf-done"]), 0)
        doctor.assert_not_called()
        gh.assert_not_called()

    def test_epic_done_requires_accept(self) -> None:
        issue = epic_issue(
            ["scope-confirmed"],
            comments=[{"body": fenced("demir-kit-closure", closure())}],
        )
        child = leaf_issue(["leaf-done"])
        with patch.object(
            transition, "fetch_issue", side_effect=lambda n: issue if n == 44 else child
        ):
            with self.assertRaises(SystemExit) as error:
                run_transition(["--issue", "44", "--to", "epic-done"])
        self.assertIn("insan authored", str(error.exception))

    def test_accept_flag_alone_is_rejected(self) -> None:
        issue = epic_issue(
            ["scope-confirmed"],
            comments=[{"body": fenced("demir-kit-closure", closure())}],
        )
        child = leaf_issue(["leaf-done"])
        with patch.object(
            transition, "fetch_issue", side_effect=lambda n: issue if n == 44 else child
        ):
            with self.assertRaises(SystemExit) as error:
                run_transition(["--issue", "44", "--to", "epic-done", "--accept", "human"])
        self.assertIn("insan authored", str(error.exception))

    def test_human_reject_revokes_acceptance(self) -> None:
        accepted = {
            "body": fenced("demir-kit-accept", {
                "demir_kit_version": "2",
                "epic": 44,
                "by": "human",
                "decision": "accepted",
            }),
            "user": {"login": "human"},
            "author_association": "MEMBER",
        }
        rejected = dict(accepted)
        rejected["body"] = accepted["body"].replace(
            "decision: accepted", "decision: rejected"
        )
        issue = epic_issue(
            ["scope-confirmed"],
            comments=[
                {"body": fenced("demir-kit-closure", closure())},
                accepted,
                rejected,
            ],
        )
        child = leaf_issue(["leaf-done"])
        with patch.object(
            transition, "fetch_issue", side_effect=lambda n: issue if n == 44 else child
        ):
            with self.assertRaises(SystemExit) as error:
                run_transition(["--issue", "44", "--to", "epic-done"])
        self.assertIn("insan authored", str(error.exception))

    def test_epic_done_accepts_human_comment(self) -> None:
        accept = {
            "body": fenced(
                "demir-kit-accept",
                {
                    "demir_kit_version": "2",
                    "epic": 44,
                    "by": "human",
                    "decision": "accepted",
                },
            ),
            "user": {"login": "human"},
            "author_association": "MEMBER",
        }
        issue = epic_issue(
            ["scope-confirmed", "human-qa"],
            comments=[
                {"body": fenced("demir-kit-closure", closure())},
                accept,
            ],
        )
        child = leaf_issue(["leaf-done"])
        comments: list[str] = []
        with patch.object(
            transition, "fetch_issue", side_effect=lambda n: issue if n == 44 else child
        ), patch.object(
            transition, "doctor_ok", return_value=(True, "")
        ), patch.object(transition, "gh", return_value=""), patch.object(
            transition, "post_comment", side_effect=lambda number, body: comments.append(body)
        ):
            self.assertEqual(
                run_transition(["--issue", "44", "--to", "epic-done"]),
                0,
            )
        self.assertTrue(any("run transition:" in body for body in comments))
        self.assertFalse(any("demir-kit-accept" in body for body in comments))

    def test_agent_approved_requires_parent_scope(self) -> None:
        leaf = leaf_issue(["intake"])
        parent = epic_issue(["intake"])
        with patch.object(
            transition, "fetch_issue", side_effect=[leaf, parent]
        ):
            with self.assertRaises(SystemExit) as error:
                run_transition(["--issue", "48", "--to", "agent-approved"])
        self.assertIn("parent", str(error.exception))

    def test_executing_delegates_to_claim(self) -> None:
        issue = leaf_issue(["agent-approved"])
        comments: list[str] = []
        with patch.object(transition, "fetch_issue", return_value=issue), patch.object(
            transition, "doctor_ok", return_value=(True, "")
        ) as doctor, patch.object(
            transition, "claim_issue", return_value=0
        ) as claim, patch.object(
            transition, "post_comment", side_effect=lambda number, body: comments.append(body)
        ):
            self.assertEqual(run_transition(["--issue", "48", "--to", "executing"]), 0)
        doctor.assert_called_once_with(48, "executing", [])
        claim.assert_called_once_with(48)
        self.assertTrue(any("to: executing" in body for body in comments))

    def test_blocked_to_executing_cleans_blocked(self) -> None:
        issue = leaf_issue(["agent-approved", "executing", "blocked"])
        calls: list[list[str]] = []
        with patch.object(transition, "fetch_issue", return_value=issue), patch.object(
            transition, "doctor_ok", return_value=(True, "")
        ), patch.object(
            transition, "gh", side_effect=lambda args: calls.append(args) or ""
        ), patch.object(transition, "post_comment", return_value=None):
            self.assertEqual(run_transition(["--issue", "48", "--to", "executing"]), 0)
        self.assertTrue(
            any("--remove-label" in call and "blocked" in call for call in calls)
        )

    def test_blocked_requires_reason(self) -> None:
        issue = leaf_issue(["executing"])
        with patch.object(transition, "fetch_issue", return_value=issue):
            with self.assertRaises(SystemExit):
                run_transition(["--issue", "48", "--to", "blocked"])


if __name__ == "__main__":
    unittest.main()
