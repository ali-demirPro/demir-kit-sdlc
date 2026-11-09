"""doctor.py module split (refactor, issue #117).

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import importlib.util
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
        self.assertLess(lines, 1802, lines)

    def test_skill_lint_behaviour_is_unchanged(self) -> None:
        path = ROOT / "skills" / "demo" / "SKILL.md"
        text = (
            "---\nname: demo\ndescription: >-\n  Demo skill for the module split test. Use when testing.\n"
            "---\n\n# demo\n\n## Steps\n\nDo it.\n\n## Done when\n\nOk.\n"
        )
        errors, warnings = doctor.lint_skill(path, text)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
