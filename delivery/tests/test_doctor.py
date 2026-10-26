"""Regression tests for the demir-kit doctor.

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCTOR_PATH = ROOT / "delivery" / "scripts" / "doctor.py"

spec = importlib.util.spec_from_file_location("doctor", DOCTOR_PATH)
doctor = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(doctor)

LEAF_SCHEMA = json.loads(
    (ROOT / "delivery" / "schemas" / "leaf.schema.json").read_text(encoding="utf-8")
)
EVIDENCE_SCHEMA = json.loads(
    (ROOT / "delivery" / "schemas" / "evidence.schema.json").read_text(encoding="utf-8")
)
CLOSURE_SCHEMA = json.loads(
    (ROOT / "delivery" / "schemas" / "closure.schema.json").read_text(encoding="utf-8")
)


def leaf(**overrides) -> dict:
    data = {
        "demir_kit_version": "2",
        "package_version": 1,
        "mode": "extend",
        "epic": 1,
        "entry": {"kind": "chore"},
        "factory": {"profile": "kit-internal"},
        "intent": "Regression testleri için geçerli bir niyet metni.",
        "surfaces": ["kit.docs"],
        "reference": {
            "kind": "github_paths",
            "summary": "Regression test referansı.",
            "paths": ["delivery/CONTRACT.md"],
        },
        "acceptance_criteria": [
            {"id": "AC-1", "text": "Doğrulanabilir bir kabul kriteri."}
        ],
        "out_of_scope": ["Kapsam dışı iş"],
        "risk": {"level": "low", "reasons": ["test"]},
        "tests_plan": [
            {
                "checkpoint_id": "CP-1",
                "cases": [
                    {"id": "T-1", "ac": "AC-1", "text": "Bir doğrulama adımı."}
                ],
            }
        ],
        "checkpoints": [
            {
                "id": "CP-1",
                "title": "Test",
                "gates": {
                    "behavior": True,
                    "architect": False,
                    "commercial": False,
                    "ui": False,
                    "human": False,
                },
            }
        ],
    }
    data.update(overrides)
    return data


def evidence(**overrides) -> dict:
    record = {
        "demir_kit_version": "2",
        "cp_id": "CP-1",
        "issue": 8,
        "agent": "developer",
        "behavior": {"command": "true", "exit_code": 0},
        "reviews": {
            "architect": "skipped",
            "commercial": "skipped",
            "ui": "skipped",
            "adversarial": {"reviewer_a": "approved"},
            "risk": "low",
        },
        "tests": [{"case": "T-1", "result": "pass"}],
        "findings": [],
        "status": "pass",
    }
    record.update(overrides)
    return record


def fenced(tag: str, data) -> str:
    return f"```yaml {tag}\n{yaml.safe_dump(data, sort_keys=False)}\n```\n"


class DoctorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        doctor.ERRORS.clear()
        doctor.WARNS.clear()


class LeafSchemaTests(DoctorTestCase):
    def test_valid_leaf(self) -> None:
        self.assertEqual(doctor.validate_schema(leaf(), LEAF_SCHEMA), [])

    def test_unknown_gate_rejected(self) -> None:
        bad = leaf()
        bad["checkpoints"][0]["gates"]["adversarial"] = True
        errors = doctor.validate_schema(bad, LEAF_SCHEMA)
        self.assertTrue(any("izin verilmeyen alan" in item for item in errors))

    def test_test_plan_must_cover_every_ac(self) -> None:
        bad = leaf()
        bad["tests_plan"][0]["cases"] = []
        doctor.check_issue_body(fenced("demir-kit", bad), [], None)
        self.assertTrue(any("kapsamıyor" in item for item in doctor.ERRORS))

    def test_checkpoint_membership(self) -> None:
        doctor.check_issue_body(
            fenced("demir-kit", leaf()), [], None, checkpoint="CP-9"
        )
        self.assertTrue(any("seal'inde yok" in item for item in doctor.ERRORS))

    def test_known_checkpoint_passes(self) -> None:
        doctor.check_issue_body(
            fenced("demir-kit", leaf()), [], None, checkpoint="CP-1"
        )
        self.assertEqual(doctor.ERRORS, [])

    def test_risk_enum(self) -> None:
        bad = leaf(risk={"level": "extreme"})
        errors = doctor.validate_schema(bad, LEAF_SCHEMA)
        self.assertTrue(any("enum" in item for item in errors))


class EvidenceTests(DoctorTestCase):
    def run_leaf_done(self, record: dict, data: dict | None = None) -> None:
        doctor.check_issue_body(
            fenced("demir-kit", data or leaf()),
            ["leaf-done"],
            [fenced("demir-kit-evidence", record)],
        )

    def test_latest_evidence_wins(self) -> None:
        failed = evidence(findings=[{"id": "ADV-1", "status": "open"}], status="fail")
        doctor.check_issue_body(
            fenced("demir-kit", leaf()),
            ["leaf-done"],
            [
                fenced("demir-kit-evidence", failed),
                fenced("demir-kit-evidence", evidence()),
            ],
        )
        self.assertEqual(doctor.ERRORS, [])

    def test_package_version_2_requires_verification(self) -> None:
        self.run_leaf_done(evidence(), data=leaf(package_version=2))
        self.assertTrue(
            any("verification" in item for item in doctor.ERRORS)
        )

    def test_package_version_2_with_verification(self) -> None:
        verification = {
            "commit": "a" * 7,
            "diff_hash": "sha256:" + "0" * 64,
            "ci": {"status": "skipped", "reason": "unit test"},
            "reviewers": [
                {
                    "role": "adversarial",
                    "id": "ses_reviewer",
                    "model": "test-model",
                    "prompt_hash": "sha256:" + "1" * 64,
                    "diff_hash": "sha256:" + "0" * 64,
                }
            ],
        }
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            self.run_leaf_done(
                evidence(verification=verification),
                data=leaf(package_version=2),
            )
        self.assertEqual(doctor.ERRORS, [])

    def test_valid_evidence(self) -> None:
        self.assertEqual(doctor.validate_schema(evidence(), EVIDENCE_SCHEMA), [])
        self.run_leaf_done(evidence())
        self.assertEqual(doctor.ERRORS, [])

    def test_open_finding_blocks_pass(self) -> None:
        self.run_leaf_done(evidence(findings=[{"id": "ADV-1", "status": "open"}]))
        self.assertTrue(any("açık bulgu" in item for item in doctor.ERRORS))

    def test_nonzero_exit_blocks_pass(self) -> None:
        bad = evidence(behavior={"command": "false", "exit_code": 1})
        self.assertTrue(doctor.validate_schema(bad, EVIDENCE_SCHEMA))
        self.run_leaf_done(bad)
        self.assertTrue(
            any("behavior exit_code 0 değil" in item for item in doctor.ERRORS)
        )

    def test_malformed_evidence_is_reported(self) -> None:
        doctor.check_issue_body(
            fenced("demir-kit", leaf()),
            ["leaf-done"],
            ["```yaml demir-kit-evidence\n- not-a-mapping\n```\n"],
        )
        self.assertTrue(any("mapping değil" in item for item in doctor.ERRORS))

    def test_inactive_agent_blocks_pass(self) -> None:
        self.run_leaf_done(evidence(agent="designer"))
        self.assertTrue(any("aktif değil" in item for item in doctor.ERRORS))

    def test_on_demand_agent_allowed(self) -> None:
        self.run_leaf_done(evidence(agent="architect"))
        self.assertEqual(doctor.ERRORS, [])

    def test_missing_agent_warns(self) -> None:
        record = evidence()
        record.pop("agent")
        self.run_leaf_done(record)
        self.assertEqual(doctor.ERRORS, [])
        self.assertTrue(any("agent alanı yok" in item for item in doctor.WARNS))

    def test_high_risk_requires_human_approval(self) -> None:
        high = leaf(risk={"level": "high", "reasons": ["auth"]})
        record = evidence(
            reviews={
                "architect": "approved",
                "commercial": "skipped",
                "ui": "skipped",
                "adversarial": {"reviewer_a": "approved", "reviewer_b": "approved"},
                "human": "skipped",
                "risk": "high",
            }
        )
        doctor.check_issue_body(
            fenced("demir-kit", high),
            ["leaf-done"],
            [fenced("demir-kit-evidence", record)],
        )
        self.assertTrue(any("insan onayı" in item for item in doctor.ERRORS))

    def test_high_risk_with_human_approval_passes(self) -> None:
        high = leaf(risk={"level": "high", "reasons": ["auth"]})
        record = evidence(
            reviews={
                "architect": "approved",
                "commercial": "skipped",
                "ui": "skipped",
                "adversarial": {"reviewer_a": "approved", "reviewer_b": "approved"},
                "human": "approved",
                "risk": "high",
            }
        )
        doctor.check_issue_body(
            fenced("demir-kit", high),
            ["leaf-done"],
            [fenced("demir-kit-evidence", record)],
        )
        self.assertEqual(doctor.ERRORS, [])

    def test_critical_requires_second_human_and_commercial(self) -> None:
        critical = leaf(risk={"level": "critical", "reasons": ["store"]})
        record = evidence(
            reviews={
                "architect": "approved",
                "commercial": "skipped",
                "ui": "skipped",
                "adversarial": {"reviewer_a": "approved", "reviewer_b": "approved"},
                "human": "approved",
                "human_second": "skipped",
                "risk": "critical",
            }
        )
        doctor.check_issue_body(
            fenced("demir-kit", critical),
            ["leaf-done"],
            [fenced("demir-kit-evidence", record)],
        )
        self.assertTrue(any("ikinci insan" in item for item in doctor.ERRORS))
        self.assertTrue(any("commercial" in item for item in doctor.ERRORS))

    def test_commercial_gate_requires_approval(self) -> None:
        gated = leaf()
        gated["checkpoints"][0]["gates"]["commercial"] = True
        record = evidence(
            reviews={
                "architect": "skipped",
                "commercial": "skipped",
                "ui": "skipped",
                "adversarial": {"reviewer_a": "approved"},
                "risk": "medium",
            }
        )
        doctor.check_issue_body(
            fenced("demir-kit", gated),
            ["leaf-done"],
            [fenced("demir-kit-evidence", record)],
        )
        self.assertTrue(any("commercial" in item for item in doctor.ERRORS))

    def test_ui_gate_requires_valid_comparison(self) -> None:
        gated = leaf()
        gated["checkpoints"][0]["gates"]["ui"] = True
        record = evidence(
            reviews={
                "architect": "skipped",
                "commercial": "skipped",
                "ui": "pass",
                "comparison_valid": False,
                "adversarial": {"reviewer_a": "approved"},
                "risk": "medium",
            }
        )
        doctor.check_issue_body(
            fenced("demir-kit", gated),
            ["leaf-done"],
            [fenced("demir-kit-evidence", record)],
        )
        self.assertTrue(any("comparison_valid" in item for item in doctor.ERRORS))

    def test_ui_gate_requires_both_reviewers(self) -> None:
        gated = leaf()
        gated["checkpoints"][0]["gates"]["ui"] = True
        record = evidence(
            reviews={
                "architect": "skipped",
                "commercial": "skipped",
                "ui": "pass",
                "ui_visual": "skipped",
                "ui_interaction": "pass",
                "comparison_valid": True,
                "adversarial": {"reviewer_a": "approved"},
                "risk": "medium",
            }
        )
        doctor.check_issue_body(
            fenced("demir-kit", gated),
            ["leaf-done"],
            [fenced("demir-kit-evidence", record)],
        )
        self.assertTrue(any("visual reviewer" in item for item in doctor.ERRORS))

    def test_worker_block_valid(self) -> None:
        record = evidence(
            worker={
                "run_id": "run_x",
                "task_id": "task_x",
                "dispatch_id": "ctx_x",
                "agent": "opencode2",
                "outcome": "succeeded",
            }
        )
        self.assertEqual(doctor.validate_schema(record, EVIDENCE_SCHEMA), [])

    def test_worker_block_bad_outcome(self) -> None:
        record = evidence(
            worker={"run_id": "run_x", "task_id": "task_x", "outcome": "unknown"}
        )
        self.assertTrue(doctor.validate_schema(record, EVIDENCE_SCHEMA))

    def test_workers_array_valid(self) -> None:
        record = evidence(
            workers=[
                {
                    "run_id": "run_x",
                    "task_id": "task_a",
                    "dispatch_id": "ctx_a",
                    "agent": "opencode2",
                    "outcome": "succeeded",
                },
                {
                    "run_id": "run_x",
                    "task_id": "task_b",
                    "dispatch_id": "ctx_b",
                    "agent": "opencode2",
                    "outcome": "succeeded",
                },
            ]
        )
        self.assertEqual(doctor.validate_schema(record, EVIDENCE_SCHEMA), [])

    def test_workers_array_requires_dispatch(self) -> None:
        record = evidence(
            workers=[{"run_id": "run_x", "task_id": "task_a", "agent": "opencode2"}]
        )
        self.assertTrue(doctor.validate_schema(record, EVIDENCE_SCHEMA))


class ClosureTests(DoctorTestCase):
    def closure(self, **overrides) -> dict:
        data = {
            "demir_kit_version": "2",
            "epic": 1,
            "status": "pass",
            "gaps": [],
            "unnecessary": [],
            "deferred": [],
            "metrics": {
                "leaf_count": 2,
                "cp_count": 2,
                "gate_retries": 0,
                "reconcile_issues": 0,
                "human_interventions": 0,
                "lead_time_hours": 0.5,
            },
            "ready_for_human_qa": True,
        }
        data.update(overrides)
        return data

    def run_issue(self, body: str, labels: list[str], comments: list[dict]) -> None:
        issue = {
            "body": body,
            "labels": [{"name": name} for name in labels],
        }

        def fake_run(command):
            if "/comments" in command[-1]:
                return json.dumps(comments)
            return json.dumps(issue)

        with patch.object(doctor, "run", side_effect=fake_run):
            doctor.check_issue(1, root=ROOT)

    def epic_block(self) -> str:
        epic = {
            "demir_kit_version": "2",
            "summary": "Yeterince uzun bir epic özeti.",
            "scope_triage": {"keep": [{"item": "bir is"}], "defer": [], "cut": []},
            "children": [1],
        }
        return fenced("demir-kit-epic", epic)

    def test_epic_done_requires_ready_for_human_qa(self) -> None:
        closure = self.closure(ready_for_human_qa=False)
        self.run_issue(
            self.epic_block(),
            ["epic-done"],
            [{"body": fenced("demir-kit-closure", closure)}],
        )
        self.assertTrue(
            any("ready_for_human_qa" in item for item in doctor.ERRORS)
        )

    def test_closure_must_be_a_mapping(self) -> None:
        self.run_issue(
            self.epic_block(),
            ["epic-done"],
            [{"body": "```yaml demir-kit-closure\n- status: fail\n```\n"}],
        )
        self.assertTrue(any("mapping değil" in item for item in doctor.ERRORS))

    def test_latest_closure_wins(self) -> None:
        passing = fenced("demir-kit-closure", self.closure())
        failing = fenced("demir-kit-closure", self.closure(status="fail"))
        self.run_issue(
            self.epic_block() + passing,
            ["epic-done"],
            [{"body": failing}],
        )
        self.assertTrue(
            any("closure status 'pass' değil" in item for item in doctor.ERRORS)
        )

    def test_epic_done_requires_pass_closure(self) -> None:
        closure = self.closure(status="fail")
        epic = {
            "demir_kit_version": "2",
            "summary": "Yeterince uzun bir epic özeti.",
            "scope_triage": {"keep": [{"item": "bir is"}], "defer": [], "cut": []},
            "children": [1],
        }
        issue = {
            "body": fenced("demir-kit-epic", epic),
            "labels": [{"name": "epic-done"}],
        }
        comments = [{"body": fenced("demir-kit-closure", closure)}]

        def fake_run(command):
            if "/comments" in command[-1]:
                return json.dumps(comments)
            return json.dumps(issue)

        with patch.object(doctor, "run", side_effect=fake_run):
            doctor.check_issue(1, root=ROOT)
        self.assertTrue(
            any("closure status 'pass' değil" in item for item in doctor.ERRORS)
        )

    def test_valid_closure(self) -> None:
        self.assertEqual(
            doctor.validate_schema(self.closure(), CLOSURE_SCHEMA), []
        )

    def test_zero_metrics_rejected(self) -> None:
        bad = self.closure()
        bad["metrics"]["leaf_count"] = 0
        bad["metrics"]["cp_count"] = 0
        errors = doctor.validate_schema(bad, CLOSURE_SCHEMA)
        self.assertGreaterEqual(len([e for e in errors if "en az 1" in e]), 2)

    def test_pass_requires_no_gaps(self) -> None:
        bad = self.closure(gaps=[{"kind": "test_gap", "note": "eksik test"}])
        self.assertTrue(doctor.validate_schema(bad, CLOSURE_SCHEMA))


class PaginationTests(DoctorTestCase):
    def test_fetch_comments_paginates(self) -> None:
        pages = {
            1: [{"body": str(index)} for index in range(100)],
            2: [{"body": "last"}],
        }

        def fake_run(command):
            page = int(command[-1].rsplit("page=", 1)[1])
            return json.dumps(pages.get(page, []))

        with patch.object(doctor, "run", side_effect=fake_run):
            comments = doctor.fetch_comments("owner/repo", 1)
        self.assertEqual(len(comments), 101)

    def test_human_qa_label_with_leaf_done_is_allowed(self) -> None:
        issue = {
            "body": fenced("demir-kit", leaf()),
            "labels": [{"name": "leaf-done"}, {"name": "human-qa"}],
        }
        comments = [{"body": fenced("demir-kit-evidence", evidence())}]

        def fake_run(command):
            if "/comments" in command[-1]:
                return json.dumps(comments)
            return json.dumps(issue)

        with patch.object(doctor, "run", side_effect=fake_run):
            doctor.check_issue(1, root=ROOT)
        self.assertFalse(
            any("çelişen etiketler" in item for item in doctor.ERRORS)
        )

    def test_conflicting_labels_error(self) -> None:
        issue = {
            "body": fenced("demir-kit", leaf()),
            "labels": [{"name": "leaf-done"}, {"name": "executing"}],
        }

        def fake_run(command):
            if "/comments" in command[-1]:
                return "[]"
            return json.dumps(issue)

        with patch.object(doctor, "run", side_effect=fake_run):
            doctor.check_issue(1, root=ROOT)
        self.assertTrue(
            any("çelişen etiketler" in item for item in doctor.ERRORS)
        )


class FrontmatterTests(DoctorTestCase):
    def test_frontmatter_name(self) -> None:
        text = "---\nname: work-package\ndescription: x\n---\n\n# body\n"
        self.assertEqual(doctor.frontmatter_name(text), "work-package")

    def test_missing_frontmatter(self) -> None:
        self.assertIsNone(doctor.frontmatter_name("# body\n"))

    def test_registry_runtime_skills_exist(self) -> None:
        registry = yaml.safe_load(
            (ROOT / "delivery" / "registry.yaml").read_text(encoding="utf-8")
        )
        for name in (registry.get("skills") or {}).get("runtime") or []:
            path = ROOT / "skills" / name / "SKILL.md"
            self.assertTrue(path.is_file(), f"missing {path}")
            self.assertEqual(doctor.frontmatter_name(path.read_text()), name)


if __name__ == "__main__":
    unittest.main()
