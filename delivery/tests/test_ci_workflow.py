"""Static checks for the CI dogfood workflows."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_workflow(name: str) -> dict:
    path = ROOT / ".github" / "workflows" / name
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def job_steps(job: dict) -> list[dict]:
    return [
        step
        for step in job.get("steps") or []
        if isinstance(step, dict)
    ]


class CiWorkflowTests(unittest.TestCase):
    def test_issue_workflow_triggers_and_permissions(self) -> None:
        data = load_workflow("issue-doctor.yml")
        triggers = data.get("on") or data.get(True) or {}
        issues = triggers.get("issues") if isinstance(triggers, dict) else None
        self.assertIsInstance(issues, dict)
        self.assertIn("labeled", issues.get("types", []))
        self.assertIn("reopened", issues.get("types", []))
        self.assertIn("closed", issues.get("types", []))
        self.assertNotIn("edited", issues.get("types", []))
        self.assertNotIn("opened", issues.get("types", []))
        permissions = data.get("permissions") or {}
        self.assertEqual(permissions.get("issues"), "read")
        self.assertEqual(permissions.get("actions"), "read")

    def test_issue_workflow_runs_doctor_for_state_labels(self) -> None:
        data = load_workflow("issue-doctor.yml")
        job = (data.get("jobs") or {}).get("doctor") or {}
        self.assertEqual(job.get("name"), "issue-doctor")
        condition = str(job.get("if") or "")
        for label in (
            "agent-approved",
            "leaf-done",
            "epic-done",
        ):
            self.assertIn(label, condition)
        self.assertNotIn("scope-confirmed", condition)
        steps = job_steps(job)
        runs = "\n".join(str(step.get("run") or "") for step in steps)
        self.assertIn("doctor.sh --issue", runs)
        self.assertIn("github.event.issue.number", runs)
        doctor_step = next(step for step in steps if step.get("id") == "doctor")
        self.assertIn("continue-on-error", doctor_step)
        self.assertIn("agent-approved", str(doctor_step["continue-on-error"]))
        self.assertTrue(any("::warning" in str(step.get("run") or "") for step in steps))

    def test_push_workflow_runs_tests_and_strict_doctor(self) -> None:
        data = load_workflow("doctor.yml")
        runs = "\n".join(
            str(step.get("run") or "")
            for job in (data.get("jobs") or {}).values()
            for step in job_steps(job)
        )
        self.assertIn("unittest discover", runs)
        self.assertIn("doctor.sh --strict", runs)
        self.assertIn("eval.py --check", runs)

    def test_pr_template_requires_evidence(self) -> None:
        text = (ROOT / ".github" / "pull_request_template.md").read_text(
            encoding="utf-8"
        )
        for needle in ("doctor.sh --issue", "unittest discover", "Evidence"):
            self.assertIn(needle, text)

    def test_pr_runbook_requires_merge_commit(self) -> None:
        text = (ROOT / "delivery" / "runbooks" / "pr-flow.md").read_text(
            encoding="utf-8"
        )
        for needle in ("merge commit", "delivery-doctor", "issue-doctor", "merge sonrası"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
