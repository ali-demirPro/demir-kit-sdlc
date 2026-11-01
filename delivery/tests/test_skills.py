"""Skill writing contract tests (delivery/policies/skill-writing.md).

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_negated_trigger_is_rejected(self) -> None:
        for phrase in (
            "Do not use when the gate already passed.",
            "Never use when the gate already passed.",
            "Don't use when the gate already passed.",
        ):
            with self.subTest(phrase=phrase):
                text = skill(
                    description=f"Seal one leaf and map every criterion. {phrase}"
                )
                errors, _ = self.lint(text)
                self.assertTrue(
                    any("tetikleyici" in item for item in errors), errors
                )

    def test_whenever_trigger_is_accepted(self) -> None:
        text = skill(
            description="Seal one leaf and map every criterion. Use whenever a seal is rejected."
        )
        errors, _ = self.lint(text)
        self.assertEqual(errors, [])

    def test_verbose_trigger_phrase_is_accepted(self) -> None:
        text = skill(
            description="Seal one leaf and map every criterion. Use this skill when the issue needs a seal."
        )
        errors, _ = self.lint(text)
        self.assertEqual(errors, [])

    def test_turkish_trigger_phrase_is_accepted(self) -> None:
        text = skill(
            description="Leaf mühürler ve her kriteri bir case'e bağlar. Ne zaman mühür gerekliyse."
        )
        errors, _ = self.lint(text)
        self.assertEqual(errors, [])

    def test_short_description_is_error(self) -> None:
        errors, _ = self.lint(skill(description="Use when sealing."))
        self.assertTrue(any("karakter" in item for item in errors), errors)

    def test_missing_done_when_is_error(self) -> None:
        errors, _ = self.lint(skill(done_when=""))
        self.assertTrue(any("Done when" in item for item in errors), errors)

    def test_done_when_only_in_fence_is_error(self) -> None:
        body = "## Steps\n\n```markdown\n## Done when\n\nExample only.\n```\n"
        errors, _ = self.lint(skill(body=body, done_when=""))
        self.assertTrue(any("Done when" in item for item in errors), errors)

    def test_done_when_only_in_nested_fence_is_error(self) -> None:
        body = (
            "## Steps\n\n"
            "````markdown\n```bash\n## Done when\n\nExample only.\n```\n````\n"
        )
        errors, _ = self.lint(skill(body=body, done_when=""))
        self.assertTrue(any("Done when" in item for item in errors), errors)

    def test_nested_fence_link_is_ignored(self) -> None:
        body = (
            "## Steps\n\n"
            "````markdown\n```markdown\n[example](missing.md)\n```\n````\n"
        )
        errors, _ = self.lint(skill(body=body))
        self.assertEqual(errors, [])

    def test_done_when_before_another_section_is_error(self) -> None:
        text = skill(done_when="## Done when\n\nShipped.\n\n## Next\n\nMore.\n")
        errors, _ = self.lint(text)
        self.assertTrue(any("son bölüm" in item for item in errors), errors)

    def test_h1_after_done_when_is_error(self) -> None:
        text = skill(done_when="## Done when\n\nShipped.\n\n# Ek\n\nMore.\n")
        errors, _ = self.lint(text)
        self.assertTrue(any("son bölüm" in item for item in errors), errors)

    def test_setext_heading_after_done_when_is_error(self) -> None:
        text = skill(done_when="## Done when\n\nShipped.\n\nEk\n---\n\nMore.\n")
        errors, _ = self.lint(text)
        self.assertTrue(any("son bölüm" in item for item in errors), errors)

    def test_subsection_does_not_count_as_done_when_content(self) -> None:
        text = skill(done_when="## Done when\n\n### Notlar\n\nDetay.\n")
        errors, _ = self.lint(text)
        self.assertTrue(any("boş" in item for item in errors), errors)

    def test_empty_done_when_is_error(self) -> None:
        errors, _ = self.lint(skill(done_when="## Done when\n\n## Next\n\nmore\n"))
        self.assertTrue(any("boş" in item for item in errors), errors)

    def test_broken_relative_link_is_error(self) -> None:
        body = "## Steps\n\nRead [missing](missing.md).\n"
        errors, _ = self.lint(skill(body=body))
        self.assertTrue(any("göreli link" in item for item in errors), errors)

    def test_broken_link_with_title_is_error(self) -> None:
        body = '## Steps\n\nRead [missing](missing.md "Title").\n'
        errors, _ = self.lint(skill(body=body))
        self.assertTrue(any("göreli link" in item for item in errors), errors)

    def test_broken_reference_link_is_error(self) -> None:
        body = "## Steps\n\nRead [missing][doc].\n\n[doc]: missing.md\n"
        errors, _ = self.lint(skill(body=body))
        self.assertTrue(any("göreli link" in item for item in errors), errors)

    def test_undefined_reference_is_error(self) -> None:
        body = "## Steps\n\nRead [missing][doc].\n"
        errors, _ = self.lint(skill(body=body))
        self.assertTrue(any("referans tanımı yok" in item for item in errors), errors)

    def test_titled_link_with_parenthesis_is_checked(self) -> None:
        body = '## Steps\n\nRead [missing](missing.md "T (v2)").\n'
        errors, _ = self.lint(skill(body=body))
        self.assertTrue(any("göreli link" in item for item in errors), errors)

    def test_broken_link_inside_fence_is_ignored(self) -> None:
        body = "## Steps\n\n```markdown\n[example](missing.md)\n```\n"
        errors, _ = self.lint(skill(body=body))
        self.assertEqual(errors, [])

    def test_existing_relative_link_passes(self) -> None:
        target = Path("..") / ".." / "delivery" / "scripts" / "doctor.py"
        self.assertTrue((self.path.parent / target).resolve().exists())
        body = "## Steps\n\nRead [doctor](../../delivery/scripts/doctor.py).\n"
        errors, _ = self.lint(skill(body=body))
        self.assertEqual(errors, [])

    def test_link_query_and_angle_brackets_pass(self) -> None:
        body = (
            "## Steps\n\n"
            "Read [contract](../../delivery/CONTRACT.md?plain=1) and "
            "[contract](../../delivery/CONTRACT.md#risk).\n"
        )
        errors, _ = self.lint(skill(body=body))
        self.assertEqual(errors, [])

    def test_external_link_is_ignored(self) -> None:
        body = (
            "## Steps\n\nSee [site](https://example.com/docs) and "
            "[site](<https://example.com/docs>).\n"
        )
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


class DoctorWiringTest(unittest.TestCase):
    def setUp(self) -> None:
        self.saved_errors = list(doctor.ERRORS)
        self.saved_warns = list(doctor.WARNS)
        doctor.ERRORS.clear()
        doctor.WARNS.clear()

    def tearDown(self) -> None:
        doctor.ERRORS[:] = self.saved_errors
        doctor.WARNS[:] = self.saved_warns

    def test_bad_skill_reaches_doctor_errors(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "bad").mkdir()
            (root / "bad" / "SKILL.md").write_text(
                skill(description="Seal one leaf and map every criterion."),
                encoding="utf-8",
            )
            doctor.lint_runtime_skills(root)
        self.assertTrue(
            any("tetikleyici" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_check_skills_wires_lint(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "bad").mkdir()
            (root / "bad" / "SKILL.md").write_text(
                skill(description="Seal one leaf and map every criterion."),
                encoding="utf-8",
            )
            with patch.object(doctor, "skill_dir", return_value=root):
                doctor.check_skills()
        self.assertTrue(
            any("tetikleyici" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_good_skill_records_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "good").mkdir()
            (root / "good" / "SKILL.md").write_text(skill(), encoding="utf-8")
            doctor.lint_runtime_skills(root)
        self.assertEqual(doctor.ERRORS, [])
        self.assertEqual(doctor.WARNS, [])


class RuntimeSkillsTest(unittest.TestCase):
    def test_every_runtime_skill_passes_lint(self) -> None:
        failures: list[str] = []
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            errors, warnings = doctor.lint_skill(path, text)
            failures += [f"{path.parent.name}: {item}" for item in errors]
            failures += [f"{path.parent.name} (warning): {item}" for item in warnings]
        self.assertEqual(failures, [])

    def test_lint_scope_matches_registry_runtime(self) -> None:
        import yaml

        registry = yaml.safe_load(
            (ROOT / "delivery" / "registry.yaml").read_text(encoding="utf-8")
        )
        skills = registry.get("skills") or {}
        expected = set(skills.get("runtime") or [])
        for names in (skills.get("scoped") or {}).values():
            expected |= set(names or [])
        linted = {
            path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")
        }
        self.assertEqual(expected, linted)

    def test_runtime_skills_have_trigger_and_done_when(self) -> None:
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            data = doctor.frontmatter_data(text)
            description = " ".join(str(data.get("description") or "").split())
            self.assertTrue(doctor.has_trigger(description), path.parent.name)
            self.assertRegex(
                doctor.strip_code_and_comments(text),
                r"(?m)^## Done when\b",
                path.parent.name,
            )


if __name__ == "__main__":
    unittest.main()
