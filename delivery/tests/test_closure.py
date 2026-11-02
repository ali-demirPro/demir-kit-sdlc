"""Tests for the closure builder."""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("closure", SCRIPTS / "closure.py")
closure = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(closure)

EPIC_BODY = """```yaml demir-kit-epic
demir_kit_version: "2"
summary: test
children: [10, 11]
```
"""

LEAF_BODY = """```yaml demir-kit
demir_kit_version: "2"
checkpoints:
  - {id: CP-1, title: a, gates: {behavior: true}}
  - {id: CP-2, title: b, gates: {behavior: true}}
```
"""

METRICS = {
    "leaf_count": 2,
    "cp_count": 4,
    "gate_retries": 1,
    "reconcile_issues": 0,
    "human_interventions": 0,
    "lead_time_hours": 2.0,
    "worker_count": 3,
    "tokens_in": 10,
    "tokens_out": 2,
    "cache_read": 100,
    "context_peak": 50,
    "cost_usd": 0.5,
    "coordinator_tokens_in": 7,
    "coordinator_tokens_out": 1,
    "coordinator_cache_read": 70,
    "coordinator_cost_usd": 0.2,
}


class ClosureTests(unittest.TestCase):
    def test_parse_children_and_seal(self) -> None:
        self.assertEqual(
            closure.epic_children({"body": EPIC_BODY}), [10, 11]
        )
        self.assertEqual(len(closure.leaf_seal({"body": LEAF_BODY})["checkpoints"]), 2)
        self.assertEqual(
            closure.cp_count({10: {"checkpoints": [1, 2]}, 11: {"checkpoints": [3]}}),
            3,
        )

    def test_lead_time_hours(self) -> None:
        events = {
            10: [
                {"event": "labeled", "label": {"name": "agent-approved"},
                 "created_at": "2026-11-02T08:00:00Z"},
            ],
            11: [
                {"event": "labeled", "label": {"name": "leaf-done"},
                 "created_at": "2026-11-02T10:00:00Z"},
            ],
        }
        self.assertEqual(closure.lead_time_hours([10, 11], events), 2.0)
        self.assertIsNone(closure.lead_time_hours([10], {}))

    def test_coordinator_totals(self) -> None:
        snapshot = {
            "session_id": "s1",
            "created_at": "2026-11-02T08:00:00Z",
            "cost": 1.0,
            "tokens": {"input": 1},
        }
        delta = {
            "session_id": "s1",
            "cost": 0.4,
            "tokens": {"input": 10, "output": 2, "cache_read": 100},
        }
        with patch.object(
            closure, "snapshot_for", return_value=(snapshot, Path("/tmp"))
        ), patch.object(
            closure.usage, "current_session", return_value={"id": "s1"}
        ), patch.object(
            closure.usage, "api_session_info", return_value={"id": "s1"}
        ), patch.object(closure.usage, "compute_delta", return_value=delta):
            totals = closure.coordinator_totals([10, 11])
        self.assertFalse(totals["unavailable"])
        self.assertEqual(totals["cost_usd"], 0.4)
        self.assertEqual(totals["cache_read"], 100)

    def test_coordinator_totals_unavailable_on_mismatch(self) -> None:
        snapshot = {"session_id": "s1", "created_at": "2026-11-02T08:00:00Z"}
        with patch.object(
            closure, "snapshot_for", return_value=(snapshot, Path("/tmp"))
        ), patch.object(
            closure.usage, "current_session", return_value={"id": "s2"}
        ), patch.object(closure.usage, "compute_delta") as delta:
            totals = closure.coordinator_totals([10])
        self.assertTrue(totals["unavailable"])
        self.assertEqual(totals["reason"], "session mismatch")
        delta.assert_not_called()

    def test_label_events_paginate(self) -> None:
        page1 = [{"event": "labeled"}] * 100
        page2 = [{"event": "labeled"}]
        with patch.object(
            closure, "run", side_effect=[json.dumps(page1), json.dumps(page2)]
        ) as run:
            events = closure.label_events("o/r", 10)
        self.assertEqual(len(events), 101)
        self.assertEqual(run.call_count, 2)

    def test_run_id_prefers_newest_run(self) -> None:
        runs = {
            "runs": [
                {"id": "old", "objective": "epic #1",
                 "created_at": "2026-11-01T08:00:00Z"},
                {"id": "new", "objective": "epic #1",
                 "created_at": "2026-11-02T08:00:00Z"},
            ]
        }
        with patch.object(closure, "state_roots", return_value=[]), patch.object(
            closure.usage, "orca_result", return_value=runs
        ):
            self.assertEqual(closure.run_id_for(1), "new")

    def test_worker_totals_fail_closed(self) -> None:
        zero = {"totals": {"worker_count": 0, "measured": 0, "unavailable": 0}}
        partial = {"totals": {"worker_count": 3, "measured": 1, "unavailable": 2,
                              "cost_usd": 0.1}}
        with patch.object(closure.usage, "run_usage", return_value=zero):
            self.assertTrue(closure.worker_totals("run_x")["unavailable"])
        with patch.object(closure.usage, "run_usage", return_value=partial):
            result = closure.worker_totals("run_x")
        self.assertTrue(result["unavailable"])
        self.assertTrue(result["partial"])

    def test_lead_time_uses_earliest_approval_and_latest_done(self) -> None:
        events = {
            10: [
                {"event": "labeled", "label": {"name": "agent-approved"},
                 "created_at": "2026-11-02T09:00:00Z"},
                {"event": "labeled", "label": {"name": "leaf-done"},
                 "created_at": "2026-11-02T09:30:00Z"},
            ],
            11: [
                {"event": "labeled", "label": {"name": "agent-approved"},
                 "created_at": "2026-11-02T08:00:00Z"},
                {"event": "labeled", "label": {"name": "leaf-done"},
                 "created_at": "2026-11-02T11:00:00Z"},
            ],
        }
        self.assertEqual(closure.lead_time_hours([10, 11], events), 3.0)

    def test_coordinator_uses_earliest_snapshot(self) -> None:
        early = {"session_id": "s1", "created_at": "2026-11-02T08:00:00Z"}
        late = {"session_id": "s1", "created_at": "2026-11-02T10:00:00Z"}
        delta = {"session_id": "s1", "cost": 0.1,
                 "tokens": {"input": 1, "output": 1, "cache_read": 1}}
        with patch.object(
            closure, "snapshot_for",
            side_effect=[(late, Path("/tmp")), (early, Path("/tmp"))],
        ), patch.object(
            closure.usage, "current_session", return_value={"id": "s1"}
        ), patch.object(
            closure.usage, "api_session_info", return_value={"id": "s1"}
        ), patch.object(
            closure.usage, "compute_delta", return_value=delta
        ) as compute:
            closure.coordinator_totals([10, 11])
        self.assertEqual(compute.call_args.args[0], early)

    def test_build_metrics_and_schema(self) -> None:
        metrics = closure.build_metrics(
            [10, 11],
            {10: {"checkpoints": [1, 2]}, 11: {"checkpoints": [3, 4]}},
            {
                10: [{"event": "labeled", "label": {"name": "agent-approved"},
                      "created_at": "2026-11-02T08:00:00Z"}],
                11: [{"event": "labeled", "label": {"name": "leaf-done"},
                      "created_at": "2026-11-02T10:00:00Z"}],
            },
            {"unavailable": False, "worker_count": 3, "tokens_in": 10,
             "tokens_out": 2, "cache_read": 100, "context_peak": 50, "cost_usd": 0.5},
            {"unavailable": False, "tokens_in": 7, "tokens_out": 1,
             "cache_read": 70, "cost_usd": 0.2},
            1,
            0,
            0,
        )
        self.assertEqual(metrics["leaf_count"], 2)
        self.assertEqual(metrics["cp_count"], 4)
        self.assertEqual(metrics["coordinator_cost_usd"], 0.2)
        body = closure.render_closure(154, metrics)
        block = re.search(
            r"```yaml\s+demir-kit-closure\s*\n(.*?)```", body, re.S
        )
        self.assertIsNotNone(block)
        record = yaml.safe_load(block.group(1))
        schema = json.loads(
            (ROOT / "delivery" / "schemas" / "closure.schema.json").read_text()
        )
        import doctor

        self.assertEqual(doctor.validate_schema(record, schema), [])

    def test_worker_unavailable_omits_fields(self) -> None:
        metrics = closure.build_metrics(
            [10], {10: {"checkpoints": [1]}}, {},
            {"unavailable": True}, {"unavailable": True}, 0, 0, 0
        )
        self.assertNotIn("worker_count", metrics)
        self.assertNotIn("coordinator_cost_usd", metrics)
        self.assertNotIn("lead_time_hours", metrics)


class ClosureCliTests(unittest.TestCase):
    def fake_issue(self, repo: str, number: int) -> dict:
        if number == 154:
            return {"body": EPIC_BODY, "labels": []}
        return {"body": LEAF_BODY, "labels": [{"name": "leaf-done"}]}

    def fake_events(self, repo: str, issue: int) -> list[dict]:
        if issue == 10:
            return [{"event": "labeled", "label": {"name": "agent-approved"},
                     "created_at": "2026-11-02T08:00:00Z"}]
        return [{"event": "labeled", "label": {"name": "leaf-done"},
                 "created_at": "2026-11-02T10:00:00Z"}]

    def run_main(self, argv: list[str]):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(closure, "repo_name", return_value="o/r"), \
             patch.object(closure, "issue_payload", side_effect=self.fake_issue), \
             patch.object(closure, "label_events", side_effect=self.fake_events), \
             patch.object(closure, "run_id_for", return_value="run_x"), \
             patch.object(closure, "worker_totals", return_value={"unavailable": True}), \
             patch.object(closure, "coordinator_totals", return_value={"unavailable": True}), \
             patch.object(sys, "argv", ["closure.py", *argv]), \
             redirect_stdout(out), redirect_stderr(err):
            code = closure.main()
        return code, out.getvalue(), err.getvalue()

    def test_plan_does_not_post(self) -> None:
        with patch.object(closure, "post_comment") as post:
            code, out, _ = self.run_main(["--issue", "154"])
        self.assertEqual(code, 0)
        self.assertIn("demir-kit-closure", out)
        post.assert_not_called()

    def test_post_and_verify(self) -> None:
        calls: list[str] = []
        with patch.object(
            closure, "post_comment",
            side_effect=lambda *a: (calls.append("post"), "c1")[1],
        ), patch.object(
            closure, "verify_close",
            side_effect=lambda i: (calls.append("verify"), (0, ""))[1],
        ):
            code, _, _ = self.run_main(["--issue", "154", "--post"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["post", "verify"])

    def test_missing_seal_blocks(self) -> None:
        with patch.object(closure, "repo_name", return_value="o/r"), patch.object(
            closure, "issue_payload", side_effect=self.fake_issue
        ), patch.object(
            closure, "label_events", side_effect=self.fake_events
        ), patch.object(sys, "argv", ["closure.py", "--issue", "154"]):
            with patch.object(
                closure, "issue_payload",
                side_effect=lambda repo, n: (
                    {"body": EPIC_BODY, "labels": []}
                    if n == 154
                    else {"body": "```yaml demir-kit\nepic: 1\n```\n", "labels": [{"name": "leaf-done"}]}
                ),
            ):
                with self.assertRaises(SystemExit):
                    closure.main()

    def test_verify_failure_rolls_back(self) -> None:
        with patch.object(closure, "post_comment", return_value="c1"), patch.object(
            closure, "verify_close", return_value=(1, "kırmızı")
        ), patch.object(closure, "delete_comment") as delete:
            code, _, err = self.run_main(["--issue", "154", "--post"])
        self.assertEqual(code, 1)
        delete.assert_called_once_with("o/r", "c1")
        self.assertIn("geri alındı", err)


if __name__ == "__main__":
    unittest.main()
