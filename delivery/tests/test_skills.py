"""Skill writing contract tests (delivery/policies/skill-writing.md).

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTOR_PATH = ROOT / "delivery" / "scripts" / "doctor.py"

spec = importlib.util.spec_from_file_location("doctor", DOCTOR_PATH)
doctor = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(doctor)

DESCRIPTION = (
    "Seal one leaf and map every acceptance criterion to a test case. "
    "Use when a leaf needs its seal or doctor rejects a seal body."
)


def skill(
    description: str = DESCRIPTION,
    body: str = "## Steps\n\n1. Do the thing.\n",
    done_when: str = "## Done when\n\nThe gate exits 0.\n",
) -> str:
    return f"---\nname: demo\ndescription: >-\n  {description}\n---\n\n# demo\n\n{body}\n{done_when}"


class LintSkillTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / "skills" / "demo" / "SKILL.md"

    def lint(self, text: str) -> tuple[list[str], list[str]]:
        return doctor.lint_skill(self.path, text)

    def test_valid_skill_passes(self) -> None:
        errors, warnings = self.lint(skill())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_missing_description_trigger_is_error(self) -> None:
        text = skill(description="Seal one leaf and map acceptance criteria to cases.")
        errors, _ = self.lint(text)
        self.assertTrue(any("tetikleyici" in item for item in errors), errors)

    def test_short_description_is_error(self) -> None:
        errors, _ = self.lint(skill(description="Use when sealing."))
        self.assertTrue(any("karakter" in item for item in errors), errors)

    def test_missing_done_when_is_error(self) -> None:
        errors, _ = self.lint(skill(done_when=""))
        self.assertTrue(any("Done when" in item for item in errors), errors)

    def test_empty_done_when_is_error(self) -> None:
        errors, _ = self.lint(skill(done_when="## Done when\n\n## Next\n\nmore\n"))
        self.assertTrue(any("boş" in item for item in errors), errors)

    def test_broken_relative_link_is_error(self) -> None:
        body = "## Steps\n\nRead [missing](missing.md).\n"
        errors, _ = self.lint(skill(body=body))
        self.assertTrue(any("göreli link" in item for item in errors), errors)

    def test_existing_relative_link_passes(self) -> None:
        target = Path("..") / ".." / "delivery" / "scripts" / "doctor.py"
        self.assertTrue((self.path.parent / target).resolve().exists())
        body = "## Steps\n\nRead [doctor](../../delivery/scripts/doctor.py).\n"
        errors, _ = self.lint(skill(body=body))
        self.assertEqual(errors, [])

    def test_external_link_is_ignored(self) -> None:
        body = "## Steps\n\nSee [site](https://example.com/docs).\n"
        errors, _ = self.lint(skill(body=body))
        self.assertEqual(errors, [])

    def test_long_body_warns_and_very_long_body_fails(self) -> None:
        _, warnings = self.lint(skill(body="## Steps\n\n" + "line\n" * 210))
        self.assertTrue(any("satır" in item for item in warnings), warnings)
        errors, _ = self.lint(skill(body="## Steps\n\n" + "line\n" * 320))
        self.assertTrue(any("satır" in item for item in errors), errors)

    def test_todo_warns(self) -> None:
        _, warnings = self.lint(skill(body="## Steps\n\nTODO write this.\n"))
        self.assertTrue(any("TODO" in item for item in warnings), warnings)


class RuntimeSkillsTest(unittest.TestCase):
    def test_every_runtime_skill_passes_lint(self) -> None:
        failures: list[str] = []
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            errors, warnings = doctor.lint_skill(path, text)
            failures += [f"{path.parent.name}: {item}" for item in errors]
            failures += [f"{path.parent.name} (warning): {item}" for item in warnings]
        self.assertEqual(failures, [])

    def test_runtime_skills_have_trigger_and_done_when(self) -> None:
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            data = doctor.frontmatter_data(text)
            description = " ".join(str(data.get("description") or "").split())
            self.assertRegex(description, doctor.SKILL_TRIGGER_RE, path.parent.name)
            self.assertIn("## Done when", text, path.parent.name)


if __name__ == "__main__":
    unittest.main()
