"""Capability-scoped skill tests (issue #122).

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"

spec = importlib.util.spec_from_file_location(
    "skill_scope", SCRIPTS / "skill_scope.py"
)
skill_scope = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(skill_scope)

dspec = importlib.util.spec_from_file_location("doctor", SCRIPTS / "doctor.py")
doctor = importlib.util.module_from_spec(dspec)
assert dspec.loader is not None
dspec.loader.exec_module(doctor)

SCOPED = ["mac-verify", "swift-stack"]


class SkillScopeTest(unittest.TestCase):
    def test_no_declaration_means_runtime_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data = skill_scope.select(Path(raw), ROOT)
        self.assertEqual(data["scoped"], [])
        self.assertEqual(data["runtime"], data["install"])

    def test_declared_capability_adds_scoped_skills(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            (project / ".kit").mkdir()
            (project / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: [platform.macos]\nexclude: []\n",
                encoding="utf-8",
            )
            data = skill_scope.select(project, ROOT)
        self.assertEqual(data["scoped"], SCOPED)
        for name in SCOPED:
            self.assertIn(name, data["install"])

    def test_other_capability_does_not_add_them(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            (project / ".kit").mkdir()
            (project / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: [platform.web]\nexclude: []\n",
                encoding="utf-8",
            )
            data = skill_scope.select(project, ROOT)
        self.assertEqual(data["scoped"], [])

    def test_no_duplicates_when_both_declared(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            (project / ".kit").mkdir()
            (project / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: [platform.macos, platform.web]\nexclude: []\n",
                encoding="utf-8",
            )
            data = skill_scope.select(project, ROOT)
        self.assertEqual(sorted(data["scoped"]), sorted(SCOPED))
        self.assertEqual(len(data["install"]), len(set(data["install"])))


class ScopedRegistryTest(unittest.TestCase):
    def test_registered_skills_exist(self) -> None:
        for name in SCOPED:
            with self.subTest(skill=name):
                self.assertTrue((ROOT / "skills" / name / "SKILL.md").is_file())

    def test_runtime_and_scoped_do_not_overlap(self) -> None:
        import yaml

        skills = yaml.safe_load(
            (ROOT / "delivery" / "registry.yaml").read_text(encoding="utf-8")
        )["skills"]
        runtime = set(skills.get("runtime") or [])
        scoped = {name for names in (skills.get("scoped") or {}).values() for name in names}
        self.assertFalse(runtime & scoped)

    def test_unknown_capability_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            (project / ".kit").mkdir()
            (project / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: [platform.macosx]\nexclude: []\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as error:
                skill_scope.select(project, ROOT)
        self.assertIn("bilinmeyen capability", str(error.exception))

    def test_malformed_include_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            (project / ".kit").mkdir()
            (project / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: platform.macos\nexclude: []\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                skill_scope.select(project, ROOT)

    def test_excluded_capability_is_not_installed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            (project / ".kit").mkdir()
            (project / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: [platform.macos]\nexclude: [platform.macos]\n",
                encoding="utf-8",
            )
            data = skill_scope.select(project, ROOT)
        self.assertEqual(data["scoped"], [])

    def test_same_skill_in_two_capabilities_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in ("alpha", "beta"):
                (root / name).mkdir()
                (root / name / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: >-\n  Demo skill. Use when testing.\n---\n\n## Done when\n\nOk.\n",
                    encoding="utf-8",
                )
            registry = {
                "skills": {
                    "dir": "skills",
                    "runtime": ["alpha"],
                    "scoped": {
                        "platform.macos": ["beta"],
                        "platform.ios": ["beta"],
                    },
                }
            }
            doctor.ERRORS.clear()
            with patch.object(doctor, "load_yaml", return_value=registry), patch.object(
                doctor, "skill_dir", return_value=root
            ):
                doctor.check_skills()
        self.assertTrue(
            any("iki capability'de" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_duplicate_scoped_skill_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in ("alpha", "beta"):
                (root / name).mkdir()
                (root / name / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: >-\n  Demo skill. Use when testing.\n---\n\n## Done when\n\nOk.\n",
                    encoding="utf-8",
                )
            registry = {
                "skills": {
                    "dir": "skills",
                    "runtime": ["alpha"],
                    "scoped": {"platform.macos": ["alpha"]},
                }
            }
            doctor.ERRORS.clear()
            with patch.object(doctor, "load_yaml", return_value=registry), patch.object(
                doctor, "skill_dir", return_value=root
            ):
                doctor.check_skills()
        self.assertTrue(
            any("hem runtime hem scoped" in item for item in doctor.ERRORS),
            doctor.ERRORS,
        )


if __name__ == "__main__":
    unittest.main()
