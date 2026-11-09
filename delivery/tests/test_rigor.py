"""Tests for process.rigor configuration, schema and spread table.

Run: python3 -m unittest delivery.tests.test_rigor -v
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
RIGOR_PATH = ROOT / "delivery" / "rigor.yaml"
SCHEMA_PATH = ROOT / "delivery" / "schemas" / "rigor.schema.json"
P3_PATH = ROOT / "delivery" / "plans" / "P3.yaml"
QUALITY_GATES_PATH = ROOT / "delivery" / "policies" / "quality-gates.md"

sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("rigor", SCRIPTS / "rigor.py")
rigor = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(rigor)

doctor_spec = importlib.util.spec_from_file_location("doctor", SCRIPTS / "doctor.py")
doctor = importlib.util.module_from_spec(doctor_spec)
assert doctor_spec.loader is not None
doctor_spec.loader.exec_module(doctor)


def document() -> dict:
    return yaml.safe_load(RIGOR_PATH.read_text(encoding="utf-8"))


def p3_levels() -> dict:
    plan = yaml.safe_load(P3_PATH.read_text(encoding="utf-8"))
    return plan["knobs"]["levels"]


def matrix_rows() -> dict[str, list[str]]:
    """quality-gates.md risk matrisi satırları (hücreler sırayla)."""
    rows: dict[str, list[str]] = {}
    for line in QUALITY_GATES_PATH.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*`(low|medium|high|critical)`\s*\|(.+)\|\s*$", line)
        if not match:
            continue
        rows[match.group(1)] = [cell.strip() for cell in match.group(2).split("|")]
    return rows


def project(root: Path, body: str) -> Path:
    (root / "kit.config.yaml").write_text(body, encoding="utf-8")
    return root


class SchemaTest(unittest.TestCase):
    """T-1: valid levels pass; unknown level and missing knob fail."""

    def test_valid_document(self) -> None:
        self.assertEqual(rigor.validate(document()), [])

    def test_unknown_level_rejected(self) -> None:
        data = copy.deepcopy(document())
        data["levels"]["extreme"] = copy.deepcopy(data["levels"]["minimal"])
        errors = rigor.validate(data)
        self.assertTrue(errors, "bilinmeyen seviye kabul edildi")
        self.assertTrue(any("extreme" in message for message in errors))

    def test_missing_knob_rejected(self) -> None:
        data = copy.deepcopy(document())
        del data["levels"]["standard"]["team.size"]
        errors = rigor.validate(data)
        self.assertTrue(errors, "eksik düğme kabul edildi")
        self.assertTrue(any("team.size" in message for message in errors))

    def test_missing_gating_rejected(self) -> None:
        data = copy.deepcopy(document())
        del data["gating"]
        errors = rigor.validate(data)
        self.assertTrue(errors, "gating eksikken kabul edildi")
        self.assertTrue(any("gating" in message for message in errors))

    def test_invalid_reviewer_count_source_rejected(self) -> None:
        data = copy.deepcopy(document())
        data["gating"]["reviewer_count_source"] = "level"
        errors = rigor.validate(data)
        self.assertTrue(errors, "risk dışı reviewer_count_source kabul edildi")

    def test_mapping_required_knob_and_unknown_key(self) -> None:
        data = copy.deepcopy(document())
        del data["mapping"]["team.size"]
        errors = rigor.validate(data)
        self.assertTrue(any("mapping.team.size" in message for message in errors))

        data = copy.deepcopy(document())
        data["mapping"]["bogus.knob"] = "x"
        errors = rigor.validate(data)
        self.assertTrue(any("bogus.knob" in message for message in errors))

        data = copy.deepcopy(document())
        data["mapping"]["team.size"] = 3
        errors = rigor.validate(data)
        self.assertTrue(any("mapping.team.size" in message for message in errors))

    def test_mapping_and_kit_semantics_sections_required(self) -> None:
        for section in ("mapping", "kit_semantics"):
            data = copy.deepcopy(document())
            del data[section]
            errors = rigor.validate(data)
            self.assertTrue(
                any(section in message for message in errors),
                f"{section} bölümü silinince hata yok",
            )

    def test_kit_semantics_required_keys_and_unknown_key(self) -> None:
        data = copy.deepcopy(document())
        del data["kit_semantics"]["reviewer_count"]
        errors = rigor.validate(data)
        self.assertTrue(any("kit_semantics.reviewer_count" in message for message in errors))

        data = copy.deepcopy(document())
        data["kit_semantics"]["bogus"] = "x"
        errors = rigor.validate(data)
        self.assertTrue(any("kit_semantics.bogus" in message for message in errors))

    def test_cli_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "rigor.yaml"
            path.write_text(RIGOR_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            ok = subprocess.run(
                [sys.executable, str(SCRIPTS / "rigor.py"), "--check", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(ok.returncode, 0, ok.stderr)

            data = copy.deepcopy(document())
            data["levels"]["extreme"] = copy.deepcopy(data["levels"]["minimal"])
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            bad = subprocess.run(
                [sys.executable, str(SCRIPTS / "rigor.py"), "--check", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(bad.returncode, 1, bad.stderr)

            data = copy.deepcopy(document())
            del data["levels"]["full"]["docs.density"]
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            missing = subprocess.run(
                [sys.executable, str(SCRIPTS / "rigor.py"), "--check", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(missing.returncode, 1, missing.stderr)

    def test_cli_requires_check_or_effective(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "rigor.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("--check veya --effective gerekli", result.stderr)

    def test_cli_effective_with_project(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = project(Path(raw), "process:\n  rigor: full\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "rigor.py"),
                    "--effective",
                    "--project",
                    str(root),
                ],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["level"], "full")
        self.assertEqual(payload["source"], "kit.config.yaml")


class SpreadTableTest(unittest.TestCase):
    """T-2: 3x6 table matches P3; reviewers risk-only; review_mode inert."""

    def test_table_matches_p3(self) -> None:
        data = document()
        self.assertEqual(set(data["levels"]), set(rigor.LEVELS))
        self.assertEqual(set(p3_levels()), set(rigor.LEVELS))
        for level in rigor.LEVELS:
            self.assertEqual(data["levels"][level], p3_levels()[level], level)
            self.assertEqual(len(data["levels"][level]), 6, level)
            self.assertEqual(set(data["levels"][level]), set(rigor.KNOBS), level)

    def test_reviewer_count_is_risk_only(self) -> None:
        data = document()
        self.assertEqual(data["gating"]["reviewer_count_source"], "risk")
        expected = {"low": 1, "medium": 1, "high": 2, "critical": 2}
        for risk, count in expected.items():
            self.assertEqual(rigor.reviewer_count(risk, data), count)
        # Hiçbir seviye düğmesi reviewer sayısı taşımaz.
        for level in rigor.LEVELS:
            for knob in data["levels"][level]:
                self.assertNotIn("reviewer", knob)

    def test_reviewer_count_requires_gating_and_risk_source(self) -> None:
        data = copy.deepcopy(document())
        del data["gating"]
        with self.assertRaises(rigor.RigorError) as missing:
            rigor.reviewer_count("low", data)
        self.assertIn("gating eksik", str(missing.exception))

        data = copy.deepcopy(document())
        data["gating"]["reviewer_count_source"] = "level"
        with self.assertRaises(rigor.RigorError) as source:
            rigor.reviewer_count("low", data)
        self.assertIn("reviewer_count_source", str(source.exception))

    def test_quality_gates_matrix_matches_gating(self) -> None:
        data = document()
        rows = matrix_rows()
        self.assertEqual(set(rows), {"low", "medium", "high", "critical"})
        for risk, cells in rows.items():
            self.assertEqual(len(cells), 7, f"{risk}: beklenmeyen sütun sayısı")
            match = re.search(r"(\d+)\s*reviewer", cells[4])
            self.assertIsNotNone(match, f"{risk}: reviewer sayısı yok")
            self.assertEqual(
                int(match.group(1)), rigor.reviewer_count(risk, data), risk
            )
        self.assertNotIn("reviews.human", rows["low"][6])
        self.assertNotIn("reviews.human", rows["medium"][6])
        self.assertIn("reviews.human", rows["high"][6])
        self.assertIn("human_second", rows["critical"][6])

    def test_review_mode_stored_not_live(self) -> None:
        self.assertIn("modes.review_mode", rigor.KNOBS)
        self.assertNotIn("modes.review_mode", rigor.LIVE_KNOBS)
        self.assertEqual(rigor.STORED_KNOBS, ("modes.review_mode",))
        effective = rigor.load_effective(ROOT)
        self.assertEqual(effective["knobs"]["modes.review_mode"]["effect"], "stored")

    def test_story_granularity_direction(self) -> None:
        levels = document()["levels"]
        self.assertEqual(levels["minimal"]["modes.story_granularity"], "coarse")
        self.assertEqual(levels["full"]["modes.story_granularity"], "fine")
        order = ["coarse", "balanced", "fine"]
        self.assertLess(
            order.index(levels["minimal"]["modes.story_granularity"]),
            order.index(levels["full"]["modes.story_granularity"]),
        )


class LevelSelectionTest(unittest.TestCase):
    """T-3: missing process.rigor is standard/default; explicit wins."""

    def test_missing_level_defaults_to_standard(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = project(Path(raw), "kit:\n  root: .\n")
            effective = rigor.load_effective(root)
            self.assertEqual(effective["level"], "standard")
            self.assertEqual(effective["source"], "default")
            self.assertEqual(effective["knobs"]["docs.density"]["value"], "balanced")
            self.assertEqual(
                effective["knobs"]["docs.density"]["source"], "rigor:standard"
            )

    def test_explicit_minimal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = project(Path(raw), "process:\n  rigor: minimal\n")
            effective = rigor.load_effective(root)
            self.assertEqual(effective["level"], "minimal")
            self.assertEqual(effective["source"], "kit.config.yaml")
            self.assertEqual(effective["knobs"]["modes.workflow"]["value"], "minimal")

    def test_explicit_full(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = project(Path(raw), "process:\n  rigor: full\n")
            effective = rigor.load_effective(root)
            self.assertEqual(effective["level"], "full")
            self.assertEqual(effective["source"], "kit.config.yaml")
            self.assertEqual(effective["knobs"]["qa.level"]["value"], "full")

    def test_unknown_level_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = project(Path(raw), "process:\n  rigor: extreme\n")
            with self.assertRaises(rigor.RigorError):
                rigor.load_effective(root)


class OverrideTest(unittest.TestCase):
    """T-4: explicit live knob beats spread in both directions."""

    def test_minimal_with_thorough_docs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = project(
                Path(raw),
                "process:\n  rigor: minimal\n  docs:\n    density: thorough\n",
            )
            effective = rigor.load_effective(root)
            self.assertEqual(effective["knobs"]["docs.density"]["value"], "thorough")
            self.assertEqual(
                effective["knobs"]["docs.density"]["source"], "kit.config.yaml"
            )
            self.assertEqual(
                effective["knobs"]["modes.workflow"],
                {"value": "minimal", "source": "rigor:minimal"},
            )

    def test_full_with_terse_docs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = project(
                Path(raw),
                "process:\n  rigor: full\n  docs:\n    density: terse\n",
            )
            effective = rigor.load_effective(root)
            self.assertEqual(effective["knobs"]["docs.density"]["value"], "terse")
            self.assertEqual(
                effective["knobs"]["docs.density"]["source"], "kit.config.yaml"
            )
            self.assertEqual(
                effective["knobs"]["modes.workflow"],
                {"value": "full", "source": "rigor:full"},
            )

    def test_review_mode_does_not_override(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = project(
                Path(raw),
                "process:\n  rigor: minimal\n  modes:\n    review_mode: full\n",
            )
            effective = rigor.load_effective(root)
            stored = effective["knobs"]["modes.review_mode"]
            self.assertEqual(stored["value"], "full")
            self.assertEqual(stored["effect"], "stored")
            self.assertEqual(
                effective["knobs"]["docs.density"]["source"], "rigor:minimal"
            )
            self.assertEqual(rigor.reviewer_count("medium"), 1)


class DoctorRigorTest(unittest.TestCase):
    """T-6: doctor validates rigor.yaml (ADV-1)."""

    def test_doctor_accepts_current_file(self) -> None:
        doctor.ERRORS.clear()
        doctor.check_rigor()
        errors = list(doctor.ERRORS)
        doctor.ERRORS.clear()
        self.assertEqual(errors, [])

    def test_doctor_flags_deleted_section(self) -> None:
        for section in ("mapping", "kit_semantics"):
            data = copy.deepcopy(document())
            del data[section]
            with tempfile.TemporaryDirectory() as raw:
                path = Path(raw) / "rigor.yaml"
                path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
                doctor.ERRORS.clear()
                doctor.check_rigor(path)
                errors = "\n".join(doctor.ERRORS)
                doctor.ERRORS.clear()
            self.assertIn(section, errors)

    def test_doctor_flags_deleted_knob(self) -> None:
        data = copy.deepcopy(document())
        del data["levels"]["standard"]["team.size"]
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "rigor.yaml"
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            doctor.ERRORS.clear()
            doctor.check_rigor(path)
            errors = "\n".join(doctor.ERRORS)
            doctor.ERRORS.clear()
        self.assertIn("team.size", errors)


class DoctorGateTest(unittest.TestCase):
    """T-5: strict doctor stays green with the new rigor block."""

    def test_strict_doctor(self) -> None:
        result = subprocess.run(
            ["bash", str(SCRIPTS / "doctor.sh"), "--strict"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
