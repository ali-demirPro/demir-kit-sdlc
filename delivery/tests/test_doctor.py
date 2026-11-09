"""Regression tests for the demir-kit doctor.

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import importlib.util
import inspect
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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


def write_project(root: Path, *excludes: str) -> None:
    (root / "ecosystem.yaml").write_text("products: {}\n", encoding="utf-8")
    (root / ".kit").mkdir()
    excludes_yaml = "[" + ", ".join(excludes) + "]"
    (root / ".kit" / "capabilities.yaml").write_text(
        f"version: 1\ninclude: []\nexclude: {excludes_yaml}\n",
        encoding="utf-8",
    )


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

    def test_v4_requires_check_kind(self) -> None:
        bad = leaf(package_version=4)
        doctor.check_issue_body(fenced("demir-kit", bad), [], None)
        self.assertTrue(
            any("denetim türü (check) yok" in item for item in doctor.ERRORS),
            doctor.ERRORS,
        )

    def test_v3_check_kind_is_optional(self) -> None:
        good = leaf(package_version=3)
        doctor.check_issue_body(fenced("demir-kit", good), [], None)
        self.assertEqual(doctor.ERRORS, [])

    def test_check_kind_absent_before_v4_across_versions(self) -> None:
        for version in (1, 2, 3):
            with self.subTest(package_version=version):
                doctor.ERRORS.clear()
                doctor.check_issue_body(
                    fenced("demir-kit", leaf(package_version=version)), [], None
                )
                self.assertFalse(
                    any(
                        "denetim türü" in item or "insan onayı" in item
                        for item in doctor.ERRORS
                    ),
                    doctor.ERRORS,
                )

    def test_v5_is_treated_like_v4(self) -> None:
        bad = leaf(package_version=5)
        doctor.check_issue_body(fenced("demir-kit", bad), [], None)
        self.assertTrue(
            any("denetim türü (check) yok" in item for item in doctor.ERRORS),
            doctor.ERRORS,
        )

    def test_check_coupling_applies_when_present_on_v3(self) -> None:
        bad = leaf(package_version=3)
        bad["tests_plan"][0]["cases"][0]["check"] = "snap"
        doctor.check_issue_body(fenced("demir-kit", bad), [], None)
        self.assertTrue(
            any("snap türü" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_v4_with_check_kind_passes(self) -> None:
        good = leaf(package_version=4)
        good["tests_plan"][0]["cases"][0]["check"] = "unit"
        doctor.check_issue_body(fenced("demir-kit", good), [], None)
        self.assertEqual(doctor.ERRORS, [])

    def test_snap_requires_ui_gate(self) -> None:
        bad = leaf(package_version=4)
        bad["tests_plan"][0]["cases"][0]["check"] = "snap"
        doctor.check_issue_body(fenced("demir-kit", bad), [], None)
        self.assertTrue(
            any("snap türü" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_snap_with_ui_gate_passes(self) -> None:
        good = leaf(package_version=4)
        good["checkpoints"][0]["gates"]["ui"] = True
        good["tests_plan"][0]["cases"][0]["check"] = "snap"
        doctor.check_issue_body(fenced("demir-kit", good), [], None)
        self.assertFalse(
            any("snap türü" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_manual_requires_human_gate(self) -> None:
        bad = leaf(package_version=4)
        bad["tests_plan"][0]["cases"][0]["check"] = "manual"
        doctor.check_issue_body(fenced("demir-kit", bad), [], None)
        self.assertTrue(
            any("manual türü" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_manual_with_human_gate_passes(self) -> None:
        good = leaf(package_version=4)
        good["checkpoints"][0]["gates"]["human"] = True
        good["tests_plan"][0]["cases"][0]["check"] = "manual"
        doctor.check_issue_body(fenced("demir-kit", good), [], None)
        self.assertFalse(
            any("manual türü" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def v4_record(self, human: str | None = None) -> dict:
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
        reviews = dict(evidence()["reviews"])
        if human:
            reviews["human"] = human
        return evidence(
            verification=verification,
            worktree={
                "name": "epic-1",
                "path": "/tmp/worktree",
                "branch": "epic-1",
                "epic": 1,
            },
            degrade={"reason": "unit test degrade"},
            reviews=reviews,
        )

    def test_v4_human_gate_requires_human_review(self) -> None:
        data = leaf(package_version=4)
        data["checkpoints"][0]["gates"]["human"] = True
        data["tests_plan"][0]["cases"][0]["check"] = "manual"
        comments = [
            fenced("demir-kit-evidence", self.v4_record()),
            "run degrade: unit test",
        ]
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(fenced("demir-kit", data), ["leaf-done"], comments)
        self.assertTrue(
            any("insan onayı" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_v4_human_gate_with_review_passes(self) -> None:
        data = leaf(package_version=4)
        data["checkpoints"][0]["gates"]["human"] = True
        data["tests_plan"][0]["cases"][0]["check"] = "manual"
        comments = [
            fenced("demir-kit-evidence", self.v4_record(human="approved")),
            "run degrade: unit test",
        ]
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(fenced("demir-kit", data), ["leaf-done"], comments)
        self.assertFalse(
            any("insan onayı" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_v3_human_gate_keeps_old_behaviour(self) -> None:
        data = leaf(package_version=3)
        data["checkpoints"][0]["gates"]["human"] = True
        comments = [
            fenced("demir-kit-evidence", self.v4_record()),
            "run degrade: unit test",
        ]
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(fenced("demir-kit", data), ["leaf-done"], comments)
        self.assertFalse(
            any("insan onayı" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def refactor_leaf(self, version: int = 4) -> dict:
        data = leaf(package_version=version, entry={"kind": "refactor"})
        data["tests_plan"][0]["cases"][0]["check"] = "unit"
        return data

    def test_refactor_leaf_requires_architect_gate(self) -> None:
        doctor.check_issue_body(
            fenced("demir-kit", self.refactor_leaf()), [], None
        )
        self.assertTrue(
            any("gates.architect" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_refactor_leaf_with_architect_gate_seals(self) -> None:
        data = self.refactor_leaf()
        data["checkpoints"][0]["gates"]["architect"] = True
        doctor.check_issue_body(fenced("demir-kit", data), [], None)
        self.assertFalse(
            any("gates.architect" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_refactor_leaf_done_requires_proof(self) -> None:
        data = self.refactor_leaf()
        data["checkpoints"][0]["gates"]["architect"] = True
        comments = [
            fenced("demir-kit-evidence", self.v4_record()),
            "run degrade: unit test",
        ]
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(fenced("demir-kit", data), ["leaf-done"], comments)
        self.assertTrue(
            any("verification.refactor" in item for item in doctor.ERRORS),
            doctor.ERRORS,
        )

    def test_refactor_leaf_done_with_proof_passes(self) -> None:
        data = self.refactor_leaf()
        data["checkpoints"][0]["gates"]["architect"] = True
        record = self.v4_record()
        record["verification"]["refactor"] = {
            "baseline": {"commit": "a" * 40, "tests": "pass"},
            "after": {"commit": "b" * 40, "tests": "pass"},
            "unchanged": True,
            "files_changed": 3,
        }
        comments = [fenced("demir-kit-evidence", record), "run degrade: unit test"]
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(fenced("demir-kit", data), ["leaf-done"], comments)
        self.assertFalse(
            any("refactor" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_refactor_file_split_warning(self) -> None:
        data = self.refactor_leaf()
        data["checkpoints"][0]["gates"]["architect"] = True
        record = self.v4_record()
        record["verification"]["refactor"] = {
            "baseline": {"commit": "a" * 40, "tests": "pass"},
            "after": {"commit": "b" * 40, "tests": "pass"},
            "unchanged": True,
            "files_changed": 15,
        }
        comments = [fenced("demir-kit-evidence", record), "run degrade: unit test"]
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(fenced("demir-kit", data), ["leaf-done"], comments)
        self.assertTrue(any("adımlara böl" in item for item in doctor.WARNS), doctor.WARNS)

    def test_refactor_ui_checkpoint_requires_ui_unchanged(self) -> None:
        data = self.refactor_leaf()
        data["checkpoints"][0]["gates"]["architect"] = True
        data["checkpoints"][0]["gates"]["ui"] = True
        record = self.v4_record()
        record["verification"]["refactor"] = {
            "baseline": {"commit": "a" * 40, "tests": "pass"},
            "after": {"commit": "b" * 40, "tests": "pass"},
            "unchanged": True,
            "files_changed": 3,
        }
        comments = [fenced("demir-kit-evidence", record), "run degrade: unit test"]
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(fenced("demir-kit", data), ["leaf-done"], comments)
        self.assertTrue(
            any("ui_unchanged" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_refactor_ui_checkpoint_with_proof_passes(self) -> None:
        data = self.refactor_leaf()
        data["checkpoints"][0]["gates"]["architect"] = True
        data["checkpoints"][0]["gates"]["ui"] = True
        hashes = "sha256:" + "a" * 64
        record = self.v4_record()
        record["verification"]["refactor"] = {
            "baseline": {"commit": "a" * 40, "tests": "pass", "snapshots": hashes},
            "after": {"commit": "b" * 40, "tests": "pass", "snapshots": hashes},
            "unchanged": True,
            "ui_unchanged": True,
            "files_changed": 3,
        }
        comments = [fenced("demir-kit-evidence", record), "run degrade: unit test"]
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(fenced("demir-kit", data), ["leaf-done"], comments)
        self.assertFalse(
            any("ui_unchanged" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_refactor_block_rejected_on_non_refactor_leaf(self) -> None:
        data = leaf(package_version=4)
        data["tests_plan"][0]["cases"][0]["check"] = "unit"
        record = self.v4_record()
        record["verification"]["refactor"] = {
            "baseline": {"commit": "a" * 40, "tests": "pass"},
            "after": {"commit": "b" * 40, "tests": "pass"},
            "unchanged": True,
            "files_changed": 3,
        }
        comments = [fenced("demir-kit-evidence", record), "run degrade: unit test"]
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(fenced("demir-kit", data), ["leaf-done"], comments)
        self.assertTrue(
            any("yalnız refactor leaf'te" in item for item in doctor.ERRORS),
            doctor.ERRORS,
        )

    def test_refactor_malformed_verification_is_reported(self) -> None:
        data = self.refactor_leaf()
        data["checkpoints"][0]["gates"]["architect"] = True
        data["checkpoints"][0]["gates"]["ui"] = True
        record = self.v4_record()
        record["verification"] = "bozuk"
        comments = [fenced("demir-kit-evidence", record), "run degrade: unit test"]
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(fenced("demir-kit", data), ["leaf-done"], comments)
        self.assertTrue(
            any("verification.refactor" in item for item in doctor.ERRORS),
            doctor.ERRORS,
        )

    def test_refactor_requires_architect_on_every_checkpoint(self) -> None:
        data = self.refactor_leaf()
        data["checkpoints"][0]["gates"]["architect"] = True
        data["checkpoints"].append(
            {
                "id": "CP-2",
                "title": "İkinci adım",
                "depends_on": ["CP-1"],
                "gates": {
                    "behavior": True,
                    "architect": False,
                    "commercial": False,
                    "ui": False,
                    "human": False,
                },
            }
        )
        data["tests_plan"].append(
            {
                "checkpoint_id": "CP-2",
                "cases": [
                    {"id": "T-2", "ac": "AC-1", "text": "İkinci adım.", "check": "unit"}
                ],
            }
        )
        doctor.check_issue_body(fenced("demir-kit", data), [], None)
        self.assertTrue(
            any("CP-2: refactor leaf'te gates.architect" in item for item in doctor.ERRORS),
            doctor.ERRORS,
        )

    def test_unknown_check_kind_is_rejected(self) -> None:
        bad = leaf(package_version=4)
        bad["tests_plan"][0]["cases"][0]["check"] = "vibes"
        errors = doctor.validate_schema(bad, LEAF_SCHEMA)
        self.assertTrue(any("enum dışında" in item for item in errors), errors)

    def test_unknown_check_kind_also_reported_by_doctor(self) -> None:
        bad = leaf(package_version=3)
        bad["tests_plan"][0]["cases"][0]["check"] = "vibes"
        doctor.check_issue_body(fenced("demir-kit", bad), [], None)
        self.assertTrue(
            any("geçersiz" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_test_plan_skill_documents_five_kinds(self) -> None:
        text = (ROOT / "skills" / "test-plan" / "SKILL.md").read_text(encoding="utf-8")
        for kind in ("gate", "unit", "snap", "manual", "doc"):
            self.assertIn(f"| `{kind}` |", text)
        self.assertIn("gates.ui", text)
        self.assertIn("gates.human", text)
        self.assertIn("Seçim kuralı", text)

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

    def test_declared_exclude_does_not_break_sealed_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ecosystem.yaml").write_text(
                "products:\n  app:\n    surfaces:\n      web:\n"
                "        platforms: [web]\n        stacks: [next]\n",
                encoding="utf-8",
            )
            (root / ".kit").mkdir()
            (root / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: []\nexclude: [platform.web]\n",
                encoding="utf-8",
            )
            doctor.check_issue_body(
                fenced("demir-kit", leaf(surfaces=["web.app"])),
                ["leaf-done"],
                [fenced("demir-kit-evidence", evidence(agent="security"))],
                root=root,
            )
            self.assertEqual(doctor.ERRORS, [])

    def test_declared_exclude_lowers_risk_floor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_project(root, "domain.payments")
            doctor.check_issue_body(
                fenced(
                    "demir-kit",
                    leaf(intent="Ödeme listesi metnini güncelle.", risk={"level": "medium"}),
                ),
                [],
                None,
                root=root,
                title="Ödeme",
            )
            self.assertEqual(doctor.ERRORS, [])

    def test_declared_exclude_warns_when_risk_is_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_project(root, "domain.payments")
            doctor.check_issue_body(
                fenced(
                    "demir-kit",
                    leaf(intent="Ödeme listesi metnini güncelle.", risk={"level": "medium"}),
                ),
                [],
                None,
                root=root,
                title="Ödeme",
            )
            self.assertTrue(
                any(
                    "capability exclude: domain.payments" in item
                    for item in doctor.WARNS
                )
            )

    def test_declared_exclude_removes_variant_gap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_project(root, "domain.payments")
            doctor.check_issue_body(
                fenced(
                    "demir-kit",
                    leaf(
                        intent="Ödeme listesi metnini güncelle.",
                        risk={"level": "high", "reasons": ["metadata"]},
                    ),
                ),
                [],
                None,
                root=root,
                title="Ödeme",
            )
            self.assertEqual(doctor.ERRORS, [])

    def test_declared_exclude_keeps_evidence_agent_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_project(root, "domain.payments")
            doctor.check_issue_body(
                fenced("demir-kit", leaf(intent="Ödeme listesi metnini güncelle.")),
                ["leaf-done"],
                [fenced("demir-kit-evidence", evidence(agent="data"))],
                root=root,
                title="Ödeme",
            )
            self.assertFalse(
                any("agent 'data'" in item for item in doctor.ERRORS),
                doctor.ERRORS,
            )

    def test_capability_risk_floor_blocks_seal(self) -> None:
        doctor.check_issue_body(
            fenced("demir-kit", leaf(surfaces=["web.app"], intent="auth login")),
            [],
            None,
        )
        self.assertTrue(
            any("capability risk_floor" in item for item in doctor.ERRORS)
        )

    def test_high_risk_variant_gap_blocks_seal(self) -> None:
        doctor.check_issue_body(
            fenced(
                "demir-kit",
                leaf(
                    risk={"level": "high", "reasons": ["auth"]},
                    surfaces=["web.app"],
                    intent="auth login",
                ),
            ),
            [],
            None,
        )
        self.assertTrue(
            any("capability gap:" in item for item in doctor.ERRORS)
        )

    def test_capability_role_allowed_for_evidence(self) -> None:
        self.run_leaf_done(
            evidence(agent="security"),
            data=leaf(surfaces=["web.app"]),
        )
        self.assertEqual(doctor.ERRORS, [])

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

    def verification(self) -> dict:
        return {
            "commit": "a" * 40,
            "diff_hash": "sha256:" + "0" * 64,
            "ci": {"status": "skipped", "reason": "unit test"},
            "reviewers": [
                {
                    "role": "adversarial",
                    "id": "rev_a",
                    "model": "test-model",
                    "prompt_hash": "sha256:" + "0" * 64,
                    "diff_hash": "sha256:" + "0" * 64,
                }
            ],
        }

    def worktree(self) -> dict:
        return {
            "name": "epic-1",
            "path": "/tmp/epic-1",
            "branch": "epic-1",
            "epic": 1,
        }

    def worker(self) -> dict:
        return {
            "run_id": "run_x",
            "task_id": "task_x",
            "dispatch_id": "ctx_x",
            "agent": "opencode2",
            "outcome": "succeeded",
        }

    def test_package_v3_requires_worktree(self) -> None:
        record = evidence(worker=self.worker(), verification=self.verification())
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            self.run_leaf_done(record, data=leaf(package_version=3))
        self.assertTrue(any("worktree bloğu" in item for item in doctor.ERRORS))

    def test_package_v3_requires_worker_or_degrade(self) -> None:
        record = evidence(worktree=self.worktree(), verification=self.verification())
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            self.run_leaf_done(record, data=leaf(package_version=3))
        self.assertTrue(any("worker kaydı" in item for item in doctor.ERRORS))

    def test_package_v3_valid_with_worker(self) -> None:
        record = evidence(
            worktree=self.worktree(),
            worker=self.worker(),
            orca={
                "run_id": "run_x",
                "task_id": "task_x",
                "dispatch_id": "ctx_x",
                "outcome": "succeeded",
            },
            verification=self.verification(),
        )
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            self.run_leaf_done(record, data=leaf(package_version=3))
        self.assertEqual(doctor.ERRORS, [])

    def test_package_v3_degrade_requires_issue_record(self) -> None:
        record = evidence(
            worktree=self.worktree(),
            degrade={"reason": "Orca kapalı"},
            verification=self.verification(),
        )
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            self.run_leaf_done(record, data=leaf(package_version=3))
        self.assertTrue(any("run degrade" in item for item in doctor.ERRORS))

    def test_package_v3_degrade_with_record_is_valid(self) -> None:
        record = evidence(
            worktree=self.worktree(),
            degrade={"reason": "Orca kapalı"},
            verification=self.verification(),
        )
        with patch.object(doctor.evidence_lib, "verify", return_value=[]):
            doctor.check_issue_body(
                fenced("demir-kit", leaf(package_version=3)),
                ["leaf-done"],
                [
                    fenced("demir-kit-evidence", record),
                    "run degrade: issue #8\nreason: Orca kapalı",
                ],
            )
        self.assertEqual(doctor.ERRORS, [])

    def test_orca_block_schema(self) -> None:
        record = evidence(
            orca={
                "run_id": "run_x",
                "task_id": "task_x",
                "dispatch_id": "ctx_x",
                "outcome": "succeeded",
            }
        )
        self.assertEqual(doctor.validate_schema(record, EVIDENCE_SCHEMA), [])

    def test_orca_block_requires_dispatch(self) -> None:
        record = evidence(orca={"run_id": "run_x"})
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

    def run_issue(
        self,
        body: str,
        labels: list[str],
        comments: list[dict],
        child_labels: set[str] | None = None,
    ) -> None:
        issue = {
            "body": body,
            "labels": [{"name": name} for name in labels],
        }
        normalized = []
        for comment in comments:
            item = dict(comment)
            item.setdefault("user", {"login": "human"})
            item.setdefault("author_association", "MEMBER")
            normalized.append(item)

        def fake_run(command):
            url = command[-1]
            if "/comments" in url:
                return json.dumps(normalized)
            if url.rstrip("/").endswith(("/issues/2", "/issues/3")):
                labels_value = (
                    child_labels if child_labels is not None else {"leaf-done"}
                )
                return json.dumps(
                    {"labels": [{"name": name} for name in labels_value]}
                )
            return json.dumps(issue)

        with patch.object(doctor, "run", side_effect=fake_run):
            doctor.check_issue(1, root=ROOT)

    def epic_block(self) -> str:
        epic = {
            "demir_kit_version": "2",
            "summary": "Yeterince uzun bir epic özeti.",
            "scope_triage": {"keep": [{"item": "bir is"}], "defer": [], "cut": []},
            "children": [2, 3],
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

    def test_reject_after_accept_blocks_epic_done(self) -> None:
        accept = fenced("demir-kit-accept", {
            "demir_kit_version": "2",
            "epic": 1,
            "by": "human",
            "decision": "accepted",
        })
        reject = fenced("demir-kit-accept", {
            "demir_kit_version": "2",
            "epic": 1,
            "by": "human",
            "decision": "rejected",
        })
        self.run_issue(
            self.epic_block(),
            ["epic-done"],
            [
                {"body": fenced("demir-kit-closure", self.closure())},
                {"body": accept},
                {"body": reject},
            ],
        )
        self.assertTrue(
            any("insan authored" in item for item in doctor.ERRORS)
        )

    def test_bot_acceptance_is_rejected(self) -> None:
        accept = fenced(
            "demir-kit-accept",
            {
                "demir_kit_version": "2",
                "epic": 1,
                "by": "github-actions[bot]",
                "decision": "accepted",
            },
        )
        self.run_issue(
            self.epic_block(),
            ["epic-done"],
            [
                {"body": fenced("demir-kit-closure", self.closure())},
                {
                    "body": accept,
                    "user": {"login": "github-actions[bot]"},
                    "author_association": "NONE",
                },
            ],
        )
        self.assertTrue(any("insan authored" in item for item in doctor.ERRORS))

    def test_open_child_blocks_epic_done(self) -> None:
        self.run_issue(
            self.epic_block(),
            ["epic-done"],
            [
                {"body": fenced("demir-kit-closure", self.closure())},
                {"body": fenced("demir-kit-accept", {
                    "demir_kit_version": "2",
                    "epic": 1,
                    "by": "human",
                    "decision": "accepted",
                })},
            ],
            child_labels={"executing"},
        )
        self.assertTrue(any("child #2" in item for item in doctor.ERRORS))

    def test_leaf_count_mismatch_blocks_epic_done(self) -> None:
        closure = self.closure()
        closure["metrics"]["leaf_count"] = 1
        self.run_issue(
            self.epic_block(),
            ["epic-done"],
            [
                {"body": fenced("demir-kit-closure", closure)},
                {"body": fenced("demir-kit-accept", {
                    "demir_kit_version": "2",
                    "epic": 1,
                    "by": "human",
                    "decision": "accepted",
                })},
            ],
        )
        self.assertTrue(
            any("leaf_count" in item for item in doctor.ERRORS)
        )

    def test_epic_done_requires_accept_block(self) -> None:
        self.run_issue(
            self.epic_block(),
            ["epic-done"],
            [{"body": fenced("demir-kit-closure", self.closure())}],
        )
        self.assertTrue(
            any("demir-kit-accept" in item for item in doctor.ERRORS)
        )

    def test_assumed_epic_done_skips_accept_gate(self) -> None:
        issue = {
            "body": self.epic_block(),
            "labels": [{"name": "scope-confirmed"}],
        }
        comments = [{"body": fenced("demir-kit-closure", self.closure())}]

        def fake_run(command):
            if "/comments" in command[-1]:
                return json.dumps(comments)
            return json.dumps(issue)

        with patch.object(doctor, "run", side_effect=fake_run):
            doctor.check_issue(
                1, root=ROOT, assume_labels={"epic-done"}
            )
        self.assertFalse(
            any("demir-kit-accept" in item for item in doctor.ERRORS)
        )

    def test_epic_done_with_accept(self) -> None:
        accept = fenced(
            "demir-kit-accept",
            {
                "demir_kit_version": "2",
                "epic": 1,
                "by": "human",
                "decision": "accepted",
            },
        )
        self.run_issue(
            self.epic_block(),
            ["epic-done"],
            [
                {"body": fenced("demir-kit-closure", self.closure())},
                {"body": accept},
            ],
        )
        self.assertEqual(doctor.ERRORS, [])

    def test_epic_done_requires_pass_closure(self) -> None:
        closure = self.closure(status="fail")
        epic = {
            "demir_kit_version": "2",
            "summary": "Yeterince uzun bir epic özeti.",
            "scope_triage": {"keep": [{"item": "bir is"}], "defer": [], "cut": []},
            "children": [2, 3],
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

    def test_assume_label_runs_leaf_done_checks(self) -> None:
        issue = {
            "body": fenced("demir-kit", leaf()),
            "labels": [{"name": "executing"}],
        }

        def fake_run(command):
            if "/comments" in command[-1]:
                return "[]"
            return json.dumps(issue)

        with patch.object(doctor, "run", side_effect=fake_run):
            doctor.check_issue(
                1,
                root=ROOT,
                assume_labels={"leaf-done"},
                drop_labels={"executing"},
            )
        self.assertTrue(any("evidence yok" in item for item in doctor.ERRORS))

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


class VersionDriftTests(DoctorTestCase):
    def test_aligned_wiring_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text(
                'kit:\n  version: "2.27.1"\n', encoding="utf-8"
            )
            (root / "AGENTS.md").write_text(
                "# AGENTS\n\ndemir-kit 2.27 — test\n", encoding="utf-8"
            )
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 2.27.1 — 2026-01-01\n", encoding="utf-8"
            )
            doctor.check_version_drift(root, "2.27.1")
            self.assertEqual(doctor.ERRORS, [])
            self.assertEqual(doctor.WARNS, [])

    def test_changelog_entry_mismatch_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 2.29.0 — 2026-10-30\n", encoding="utf-8"
            )
            doctor.check_version_drift(root, "2.28.1")
            self.assertTrue(any("CHANGELOG.md" in item for item in doctor.ERRORS))

    def test_config_version_mismatch_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text(
                'kit:\n  version: "2.26.1"\n', encoding="utf-8"
            )
            doctor.check_version_drift(root, "2.27.1")
            self.assertTrue(any("kit.version" in item for item in doctor.ERRORS))

    def test_agents_header_mismatch_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                "# AGENTS\n\ndemir-kit 2.26 — test\n", encoding="utf-8"
            )
            doctor.check_version_drift(root, "2.27.1")
            self.assertEqual(doctor.ERRORS, [])
            self.assertTrue(any("AGENTS.md" in item for item in doctor.WARNS))

    def test_missing_config_version_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text("kit:\n  root: .\n", encoding="utf-8")
            doctor.check_version_drift(root, "2.27.1")
            self.assertTrue(any("kit.version yok" in item for item in doctor.WARNS))

    def test_self_host_wiring_is_aligned(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        doctor.check_version_drift(ROOT, version)
        self.assertEqual(doctor.ERRORS, [])
        self.assertEqual(doctor.WARNS, [])


class InstalledSkillsTests(DoctorTestCase):
    def make_root(self, root: Path, *, stale: bool) -> None:
        (root / "skills" / "demo").mkdir(parents=True)
        (root / "skills" / "demo" / "SKILL.md").write_text(
            "version: 2\n", encoding="utf-8"
        )
        (root / ".agents" / "skills" / "demo").mkdir(parents=True)
        copy = "version: 1\n" if stale else "version: 2\n"
        (root / ".agents" / "skills" / "demo" / "SKILL.md").write_text(
            copy, encoding="utf-8"
        )

    def test_stale_copy_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root, stale=True)
            doctor.check_installed_skills(root)
            self.assertTrue(any("demo" in item for item in doctor.WARNS), doctor.WARNS)

    def test_current_copy_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_root(root, stale=False)
            doctor.check_installed_skills(root)
            self.assertEqual(doctor.WARNS, [])

    def test_missing_install_dir_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            doctor.check_installed_skills(root)
            self.assertEqual(doctor.WARNS, [])


class WorktreeManagementTests(DoctorTestCase):
    def run_check(
        self,
        root: Path,
        *,
        linked: bool = True,
        recorded: str | None = None,
        orca: bool = True,
        ci: bool = False,
    ) -> None:
        def git_stub(path, *args):
            if args[-1] == "--git-dir":
                return str(root / ".git" / "worktrees" / "wt") if linked else str(
                    root / ".git"
                )
            if args[-1] == "--git-common-dir":
                return str(root / ".git")
            return None

        worktree = (
            {"git": {"path": recorded}, "createdAt": 1}
            if recorded is not None
            else None
        )
        env = {"CI": "1"} if ci else {"CI": ""}
        with patch.object(doctor, "_git_output", side_effect=git_stub), patch.object(
            doctor.epic_worktree, "orca_available", return_value=orca
        ), patch.object(
            doctor.epic_worktree, "current_worktree", return_value=worktree
        ), patch.dict(os.environ, env):
            doctor.check_worktree_management(root)

    def test_raw_worktree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_check(root)
            self.assertTrue(
                any("Orca dışında açılmış" in item for item in doctor.ERRORS),
                doctor.ERRORS,
            )

    def test_orca_worktree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_check(root, recorded=str(root))
            self.assertEqual(doctor.ERRORS, [])

    def test_external_worktree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            worktree = {"git": {"path": str(root)}}  # Orca buldu ama açmadı
            env = {"CI": ""}

            def git_stub(path, *args):
                if args[-1] == "--git-dir":
                    return str(root / ".git" / "worktrees" / "wt")
                if args[-1] == "--git-common-dir":
                    return str(root / ".git")
                return None

            with patch.object(doctor, "_git_output", side_effect=git_stub), patch.object(
                doctor.epic_worktree, "orca_available", return_value=True
            ), patch.object(
                doctor.epic_worktree, "current_worktree", return_value=worktree
            ), patch.dict(os.environ, env):
                doctor.check_worktree_management(root)
            self.assertTrue(
                any("Orca dışında açılmış" in item for item in doctor.ERRORS),
                doctor.ERRORS,
            )

    def test_main_checkout_is_not_policed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_check(root, linked=False)
            self.assertEqual(doctor.ERRORS, [])

    def test_missing_orca_degrades_silently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_check(root, orca=False)
            self.assertEqual(doctor.ERRORS, [])

    def test_ci_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_check(root, ci=True)
            self.assertEqual(doctor.ERRORS, [])


class ExplainTests(DoctorTestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(DOCTOR_PATH), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_known_and_unknown_check(self) -> None:
        known = self.run_cli("--explain", "mcp")
        self.assertEqual(known.returncode, 0, known.stderr)
        self.assertIn("enabled: true", known.stdout)
        self.assertIn("source: delivery/scripts/doctor.py:", known.stdout)
        self.assertIn("summary:", known.stdout)
        self.assertNotIn(str(ROOT), known.stdout)

        unknown = self.run_cli("--explain", "yok-boyle-bir-sey")
        self.assertEqual(unknown.returncode, 2)
        self.assertIn("yok-boyle-bir-sey", unknown.stderr + unknown.stdout)

    def test_gates_explain(self) -> None:
        result = self.run_cli("--explain", "gates")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("profile: kit-internal", result.stdout)
        self.assertIn("profile_source:", result.stdout)
        self.assertIn("gates:", result.stdout)

    def test_explain_does_not_run_checks(self) -> None:
        buffer = io.StringIO()
        with patch.object(sys, "argv", ["doctor.py", "--explain", "mcp"]), patch.object(
            doctor.subprocess,
            "run",
            side_effect=AssertionError("explain kontrol/subprocess çalıştırmamalı"),
        ), redirect_stdout(buffer):
            code = doctor.main()
        output = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("explain: mcp", output)
        self.assertNotIn("[fail]", output)
        self.assertNotIn("[warn]", output)


    def test_gates_matches_profiles_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "kit.config.yaml").write_text(
                "factory:\n  default_profile: payments\n", encoding="utf-8"
            )
            explained = self.run_cli(
                "--explain", "gates", "--product", "--root", str(project)
            )
            self.assertEqual(explained.returncode, 0, explained.stderr)
            explained_gates = [
                (match.group(1), match.group(2))
                for match in re.finditer(
                    r"^gate: (\S+) source=(\S+)$", explained.stdout, re.M
                )
            ]
            resolved = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "delivery" / "scripts" / "profiles.py"),
                    "--resolve",
                    "--json",
                    "--project",
                    str(project),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(resolved.returncode, 0, resolved.stderr)
            data = json.loads(resolved.stdout)
            expected = [(gate["value"], gate["source"]) for gate in data["gates"]]
            self.assertEqual(explained_gates, expected)
            self.assertTrue(explained_gates, "payments profili gate üretmeli")

    def test_disabled_check_reports_reason(self) -> None:
        result = self.run_cli("--explain", "product")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("enabled: false", result.stdout)
        self.assertIn("reason: yalnız --product", result.stdout)

        with tempfile.TemporaryDirectory() as directory:
            product = self.run_cli(
                "--explain", "files", "--product", "--root", directory
            )
        self.assertEqual(product.returncode, 0, product.stderr)
        self.assertIn("enabled: false", product.stdout)
        self.assertIn("reason: yalnız kit modu", product.stdout)

    def test_registry_covers_main_checks(self) -> None:
        source = inspect.getsource(doctor.main)
        called = set(re.findall(r"^\s+check_([a-z_]+)\(", source, re.M))
        called |= set(
            re.findall(r"^\s+doctor_[a-z_]+\.check_([a-z_]+)\(", source, re.M)
        )
        called -= {"issue", "issue_body"}  # seal/evidence, explain kapsamı dışı
        aliases = {"worktree_management": "worktree"}
        expected = {aliases.get(raw, raw.replace("_", "-")) for raw in called}
        self.assertTrue(expected)
        self.assertEqual(set(doctor.EXPLAIN_CHECKS), expected)

    def test_delegated_check_call_is_detected(self) -> None:
        source = "        doctor_compat.check_compat(ROOT, error, check)"
        found = set(
            re.findall(r"^\s+doctor_[a-z_]+\.check_([a-z_]+)\(", source, re.M)
        )
        self.assertEqual(found, {"compat"})
        for name, func in doctor.EXPLAIN_CHECKS.items():
            self.assertEqual(func.__module__, "doctor", name)
            self.assertIn(name, doctor.doctor_explain.SUMMARIES)

    def test_empty_and_unknown_name_exit_2(self) -> None:
        empty = self.run_cli("--explain", "")
        self.assertEqual(empty.returncode, 2, empty.stdout)
        unknown = self.run_cli("--explain", "nope")
        self.assertEqual(unknown.returncode, 2, unknown.stdout)
        self.assertIn("bilinmeyen kontrol: nope", unknown.stderr + unknown.stdout)


class LocalOverridesTests(DoctorTestCase):
    """T-2/T-4: beyaz liste tek kaynak; .kit/local.yaml depo dışı kalır."""

    POLICY = ROOT / "delivery" / "local-overrides.yaml"

    def policy_copy(self, directory: str, **overrides) -> Path:
        data = yaml.safe_load(self.POLICY.read_text(encoding="utf-8"))
        data.update(overrides)
        path = Path(directory) / "local-overrides.yaml"
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return path

    def test_canonical_policy_passes(self) -> None:
        doctor.check_local_overrides(ROOT)
        self.assertEqual(doctor.ERRORS, [], doctor.ERRORS)

    def test_read_write_divergence_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.policy_copy(directory, write=["docs.density", "docs.notes"])
            doctor.check_local_overrides(ROOT, policy_path=path)
        self.assertTrue(
            any("read ve write listeleri ayrışıyor" in item for item in doctor.ERRORS),
            doctor.ERRORS,
        )

    def test_values_must_match_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.policy_copy(
                directory,
                values={"docs.density": ["terse"]},  # read'de docs.notes yok
                read=["docs.density", "docs.notes"],
                write=["docs.density", "docs.notes"],
            )
            doctor.check_local_overrides(ROOT, policy_path=path)
        self.assertTrue(
            any("values anahtarları" in item for item in doctor.ERRORS),
            doctor.ERRORS,
        )

    def test_locked_key_cannot_enter_whitelist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.policy_copy(
                directory,
                read=["docs.density", "process.rigor"],
                write=["docs.density", "process.rigor"],
                values={
                    "docs.density": ["terse", "balanced", "thorough"],
                    "process.rigor": ["minimal", "standard", "full"],
                },
            )
            doctor.check_local_overrides(ROOT, policy_path=path)
        self.assertTrue(
            any("kilitli ama read/write" in item for item in doctor.ERRORS),
            doctor.ERRORS,
        )

    def test_required_locked_keys_cannot_be_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = yaml.safe_load(self.POLICY.read_text(encoding="utf-8"))
            data["locked"] = [
                key for key in data["locked"] if key != "risk.level"
            ]
            path = Path(directory) / "local-overrides.yaml"
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            doctor.check_local_overrides(ROOT, policy_path=path)
        self.assertTrue(
            any(
                "zorunlu kilitli anahtar eksik" in item and "risk.level" in item
                for item in doctor.ERRORS
            ),
            doctor.ERRORS,
        )

    def test_missing_reason_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = yaml.safe_load(self.POLICY.read_text(encoding="utf-8"))
            data["reasons"].pop("gates.*")
            path = Path(directory) / "local-overrides.yaml"
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            doctor.check_local_overrides(ROOT, policy_path=path)
        self.assertTrue(
            any("gerekçe yok" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_gitignore_covers_personal_file(self) -> None:
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".kit/local.yaml", lines)

    def test_tracked_personal_file_is_error(self) -> None:
        def git_stub(root, *args):
            if args == ("rev-parse", "--is-inside-work-tree"):
                return "true"
            if args[:1] == ("ls-files",):
                return ".kit/local.yaml"
            return None

        with patch.object(
            doctor.doctor_local, "_git_output", side_effect=git_stub
        ), patch.object(
            doctor.doctor_local.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0),
        ):
            doctor.check_local_overrides(ROOT)
        self.assertTrue(
            any("git'te izleniyor" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_resolution_shows_density_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".kit").mkdir()
            (root / ".kit" / "local.yaml").write_text(
                "docs:\n  density: terse\n", encoding="utf-8"
            )
            data = doctor.resolver_lib.resolve(
                doctor.resolver_lib.load_capabilities(),
                doctor.resolver_lib.load_matrix(),
                doctor.resolver_lib.load_agent_variants(),
                "full_product",
                [],
                project=root,
            )
        self.assertEqual(
            data["local"]["docs"]["density"],
            {"value": "terse", "source": ".kit/local.yaml"},
        )
        # Doküman yolu listesi kişisel dosyadan etkilenmez.
        self.assertTrue(all(isinstance(item, str) for item in data["docs"]))


class RiskBaselineInvariantTest(unittest.TestCase):
    """I24: rigor seviyesi risk tabanını, reviewer sayısını ve insan kapısını düşüremez."""

    LEVELS = ("minimal", "standard", "full")
    RISKS = ("low", "medium", "high", "critical")
    COUNTS = {"low": 1, "medium": 1, "high": 2, "critical": 2}

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = doctor.resolver_lib.load_capabilities()
        cls.matrix = doctor.resolver_lib.load_matrix()
        cls.variants = doctor.resolver_lib.load_agent_variants()

    def make_project(self, root: Path, level: str) -> Path:
        """Rigor seviyesi dışında her şeyi aynı olan gerçek proje."""
        (root / "kit.config.yaml").write_text(
            "kit:\n  root: .\n  protocol: \"2\"\n"
            f"process:\n  rigor: {level}\n"
            "factory:\n  default_profile: web-app\n"
            "  profiles: [web-app, payments]\n",
            encoding="utf-8",
        )
        (root / "ecosystem.yaml").write_text(
            "products:\n  app:\n    surfaces:\n      web.app:\n"
            "        platforms: [web]\n        stacks: [next]\n",
            encoding="utf-8",
        )
        return root

    def test_reviewer_count_is_risk_only(self) -> None:
        for risk, count in self.COUNTS.items():
            self.assertEqual(doctor.rigor_lib.reviewer_count(risk), count, risk)

    def test_high_and_critical_keep_human_reviewer_and_gate(self) -> None:
        for risk in ("high", "critical"):
            reviewers = doctor.routing.evidence_reviewers({}, risk)
            self.assertIn("human", reviewers, risk)
            adversarial = [
                role for role in reviewers if role.startswith("adversarial")
            ]
            self.assertEqual(
                len(adversarial), doctor.rigor_lib.reviewer_count(risk), risk
            )
            self.assertTrue(doctor.routing.human_gates(risk, False), risk)

    def test_rigor_level_cannot_lower_baseline(self) -> None:
        floors: dict[str, str] = {}
        roles: dict[str, tuple[str, ...]] = {}
        matrices: dict[str, tuple] = {}
        reviewer_sets: dict[str, set[tuple[str, ...]]] = {
            risk: set() for risk in self.RISKS
        }
        gate_sets: dict[str, set[tuple[str, ...]]] = {
            risk: set() for risk in self.RISKS
        }
        for level in self.LEVELS:
            with tempfile.TemporaryDirectory() as raw:
                root = self.make_project(Path(raw), level)
                block = doctor.profiles_lib.compose(root)["rigor"]
                gates = doctor.profiles_lib.gates_for(root)
                declared = doctor.resolver_lib.load_declared(root)
                ecosystem = yaml.safe_load(
                    (root / "ecosystem.yaml").read_text(encoding="utf-8")
                )
                resolution = doctor.resolver_lib.resolve(
                    self.registry,
                    self.matrix,
                    self.variants,
                    "full_product",
                    doctor.resolver_lib.project_signals(ecosystem),
                    declared=declared,
                )
                reviewers = {
                    risk: doctor.routing.evidence_reviewers({}, risk, gates)
                    for risk in self.RISKS
                }
                human = {
                    risk: doctor.routing.human_gates(risk, False)
                    for risk in self.RISKS
                }
            # Seviye gerçekten uygulandı: fallback değil, kit.config kazandı.
            self.assertEqual(block["level"], level)
            self.assertEqual(block["source"], "kit.config.yaml", level)
            self.assertEqual(block["warnings"], [], level)
            self.assertEqual(block["knobs"]["modes.workflow"]["value"], level)
            matrices[level] = tuple(
                (name, block["knobs"][name]["value"])
                for name in doctor.rigor_lib.KNOBS
            )
            # Çözümleme rigor'dan bağımsız: aynı risk tabanı ve aktif roller.
            self.assertIn("domain.payments", resolution["capabilities"], level)
            self.assertEqual(
                resolution["risk_floor"],
                self.registry["capabilities"]["domain.payments"]["risk_floor"],
                level,
            )
            floors[level] = resolution["risk_floor"]
            roles[level] = tuple(resolution["active_roles"])
            for risk in self.RISKS:
                label = f"{level}/{risk}"
                count = doctor.rigor_lib.reviewer_count(risk)
                self.assertEqual(count, self.COUNTS[risk], label)
                adversarial = [
                    role for role in reviewers[risk] if role.startswith("adversarial")
                ]
                self.assertEqual(len(adversarial), count, label)
                if risk in {"high", "critical"}:
                    self.assertIn("human", reviewers[risk], label)
                    self.assertTrue(human[risk], label)
                else:
                    self.assertNotIn("human", reviewers[risk], label)
                reviewer_sets[risk].add(tuple(reviewers[risk]))
                gate_sets[risk].add(tuple(human[risk]))
            # full low/medium için ikinci gating reviewer üretmemeli.
            if level == "full":
                for risk in ("low", "medium"):
                    self.assertNotIn(
                        "adversarial-b", reviewers[risk], f"full/{risk}"
                    )
            # minimal high/critical insan kapısını düşürmemeli.
            if level == "minimal":
                for risk in ("high", "critical"):
                    self.assertIn("human", reviewers[risk], f"minimal/{risk}")
                    self.assertTrue(human[risk], f"minimal/{risk}")
        # Seviyeler gerçekten ayrışıyor; yoksa test üç kez aynı şeyi ölçer.
        self.assertEqual(len(set(matrices.values())), len(self.LEVELS), matrices)
        # Rigor seviyesi ne risk tabanını ne rolleri ne de kapıları değiştirir.
        self.assertEqual(len(set(floors.values())), 1, floors)
        self.assertEqual(len(set(roles.values())), 1, roles)
        for risk in self.RISKS:
            self.assertEqual(
                len(reviewer_sets[risk]),
                1,
                f"{risk}: rigor reviewer kümesini değiştirdi: {reviewer_sets[risk]}",
            )
            self.assertEqual(
                len(gate_sets[risk]),
                1,
                f"{risk}: rigor insan kapısını değiştirdi: {gate_sets[risk]}",
            )


if __name__ == "__main__":
    unittest.main()
