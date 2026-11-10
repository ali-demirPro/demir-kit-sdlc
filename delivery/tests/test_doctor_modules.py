"""doctor.py module split (refactor, issue #117).

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"

spec = importlib.util.spec_from_file_location("doctor", SCRIPTS / "doctor.py")
doctor = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(doctor)


class ModuleSplitTest(unittest.TestCase):
    def test_modules_exist(self) -> None:
        for name in (
            "doctor_skills.py",
            "doctor_surfaces.py",
            "doctor_explain.py",
            "doctor_compat.py",
            "doctor_version.py",
            "doctor_local.py",
        ):
            self.assertTrue((SCRIPTS / name).is_file(), name)

    def test_doctor_uses_the_modules(self) -> None:
        for name in (
            "lint_skill",
            "frontmatter_name",
            "frontmatter_data",
            "relative_links",
            "strip_code_and_comments",
            "normalize_link",
            "inline_link_targets",
            "undefined_references",
            "has_trigger",
        ):
            with self.subTest(symbol=name):
                self.assertEqual(getattr(doctor, name).__module__, "doctor_skills")
        self.assertEqual(doctor.surface_gate_errors.__module__, "doctor_surfaces")

    def test_interface_is_unchanged(self) -> None:
        for name in (
            "lint_skill",
            "frontmatter_name",
            "frontmatter_data",
            "relative_links",
            "surface_gate_errors",
            "check_issue_body",
            "check_skills",
            "check_ecosystem",
        ):
            self.assertTrue(hasattr(doctor, name), name)

    def test_doctor_shrank(self) -> None:
        lines = len((SCRIPTS / "doctor.py").read_text(encoding="utf-8").splitlines())
        # 1800 + 2: frequency.yaml şema kontrolü (issue 315) doctor.py'ye
        # bir import ve bir report çağrısı ekledi; payda tek satır bırakıldı.
        # +30: rigor.yaml denetimi (issue 325) import, check_rigor ve main çağrısı.
        # +10: local-overrides denetimi (issue 328); gövde doctor_local.py'de,
        # doctor.py'de yalnız import, ince sarmalayıcı ve main çağrısı kaldı.
        # +38: tanımsız surface fail-closed denetimi (#334 CP-1 review fix).
        self.assertLess(lines, 1881, lines)

    def test_skill_lint_behaviour_is_unchanged(self) -> None:
        path = ROOT / "skills" / "demo" / "SKILL.md"
        text = (
            "---\nname: demo\ndescription: >-\n  Demo skill for the module split test. Use when testing.\n"
            "---\n\n# demo\n\n## Steps\n\nDo it.\n\n## Done when\n\nOk.\n"
        )
        errors, warnings = doctor.lint_skill(path, text)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


class ExplainRigorTest(unittest.TestCase):
    """T-2: `--explain rigor` matrisi ve `--explain gates` değişmezliği."""

    def run_doctor(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "doctor.py"), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_explain_rigor_matrix(self) -> None:
        result = self.run_doctor("--explain", "rigor")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], "explain: rigor")
        level_line = next(line for line in lines if line.startswith("level: "))
        self.assertRegex(level_line, r"^level: (minimal|standard|full) source=\S+$")
        knob_lines = [line for line in lines if line.startswith("knob: ")]
        self.assertEqual(len(knob_lines), 6)
        parsed = {}
        for line in knob_lines:
            name, rest = line[len("knob: ") :].split(" ", 1)
            self.assertTrue(rest.startswith("value="), rest)
            self.assertIn(" source=", rest)
            value, source = rest.split(" source=", 1)
            parsed[name] = {"value": value[len("value=") :], "source": source}

        # profiles --json aynı veriyi rigor bloğunda taşır.
        json_result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "profiles.py"),
                "--project",
                str(ROOT),
                "--json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(json_result.returncode, 0, json_result.stderr)
        block = json.loads(json_result.stdout)["rigor"]
        self.assertEqual(len(block["knobs"]), 6)
        self.assertEqual(
            parsed,
            {
                name: {"value": item["value"], "source": item["source"]}
                for name, item in block["knobs"].items()
            },
        )

    def test_explain_gates_is_unchanged(self) -> None:
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = doctor.doctor_explain.gates(ROOT)
        result = self.run_doctor("--explain", "gates")
        self.assertEqual(code, 0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, captured.getvalue())
        self.assertEqual(result.stdout.splitlines()[0], "explain: gates")
        self.assertNotIn("rigor", result.stdout)

    def test_explain_rigor_invalid_config_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kit.config.yaml").write_text(
                'kit:\n  protocol: "2"\nprocess:\n  rigor: extreme\n',
                encoding="utf-8",
            )
            result = self.run_doctor(
                "--explain", "rigor", "--product", "--root", str(root)
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("uyarı: ", result.stdout)
        self.assertIn("fallback: standard (", result.stdout)
        self.assertIn("level: standard source=fallback", result.stdout)


if __name__ == "__main__":
    unittest.main()
