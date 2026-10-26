"""Regression tests for the demir-kit doctor.

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

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
    def run_leaf_done(self, record: dict) -> None:
        doctor.check_issue_body(
            fenced("demir-kit", leaf()),
            ["leaf-done"],
            [fenced("demir-kit-evidence", record)],
        )

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
