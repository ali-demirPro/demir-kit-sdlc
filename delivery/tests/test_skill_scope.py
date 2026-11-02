"""Capability-scoped skill tests (issue #122).

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import importlib.util
import json
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


class InstallProjectRootTest(unittest.TestCase):
    def test_resolve_project_prefers_product_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            product = Path(raw)
            (product / "kit.config.yaml").write_text("kit: {root: kit}\n")
            self.assertEqual(
                skill_scope.resolve_project(product, Path("/kit")), product
            )

    def test_resolve_project_falls_back_to_kit_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            plain = Path(raw)
            self.assertEqual(
                skill_scope.resolve_project(plain, Path("/kit")), Path("/kit")
            )

    def test_cwd_mode_reads_the_product_declaration(self) -> None:
        from unittest.mock import patch
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as raw:
            product = Path(raw)
            (product / "kit.config.yaml").write_text("kit: {root: kit}\n")
            (product / ".kit").mkdir()
            (product / ".kit" / "capabilities.yaml").write_text(
                "version: 1\ninclude: [platform.macos]\nexclude: []\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "skill_scope.py"),
                    "--cwd",
                    str(product),
                    "--root",
                    str(ROOT),
                    "--json",
                ],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(sorted(payload["scoped"]), sorted(SCOPED))


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
            capabilities = {
                "capabilities": {
                    "platform.macos": {"roles": {}},
                    "platform.ios": {"roles": {}},
                }
            }

            def fake_load(path):
                return capabilities if "capabilities" in str(path) else registry

            doctor.ERRORS.clear()
            with patch.object(doctor, "load_yaml", side_effect=fake_load), patch.object(
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


class InstallTargetTest(unittest.TestCase):
    def test_product_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            product = Path(raw)
            (product / "kit.config.yaml").write_text("kit: {root: kit}\n")
            kit = product / "kit"
            kit.mkdir()
            self.assertEqual(
                skill_scope.install_target(product, kit), product.resolve()
            )

    def test_self_host(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            kit = Path(raw) / "kit"
            kit.mkdir()
            (kit / "kit.config.yaml").write_text("kit: {root: .}\n")
            self.assertEqual(skill_scope.install_target(kit, kit), kit.resolve())

    def test_caller_inside_vendored_submodule(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            product = Path(raw)
            (product / "kit.config.yaml").write_text("kit: {root: kit}\n")
            kit = product / "demir-kit"
            kit.mkdir()
            (kit / "kit.config.yaml").write_text("kit: {root: .}\n")
            self.assertEqual(
                skill_scope.install_target(kit, kit), product.resolve()
            )

    def test_product_subdirectory_falls_back_to_kit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            product = Path(raw)
            (product / "kit.config.yaml").write_text("kit: {root: kit}\n")
            kit = product / "kit"
            deep = product / "App" / "Features"
            kit.mkdir()
            deep.mkdir(parents=True)
            self.assertEqual(skill_scope.install_target(deep, kit), kit.resolve())

    def test_plain_directory(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            plain = Path(raw)
            self.assertEqual(
                skill_scope.install_target(plain, ROOT), ROOT.resolve()
            )


class InstallScriptTest(unittest.TestCase):
    """End-to-end: install.sh must read the product's own declaration."""

    def run_install(self, product: Path) -> tuple[int, str]:
        import os
        import subprocess
        import sys

        bindir = product / ".fakebin"
        bindir.mkdir()
        stub = bindir / "npx"
        stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        stub.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{bindir}:{env.get('PATH', '')}"
        result = subprocess.run(
            [
                "bash",
                str(SCRIPTS / "install.sh"),
                "--capabilities",
                "--dry-run",
            ],
            cwd=product,
            capture_output=True,
            text=True,
            env=env,
        )
        return result.returncode, result.stdout + result.stderr

    def product(self, root: Path, include: str = "platform.macos") -> None:
        (root / "kit.config.yaml").write_text("kit: {root: kit}\n", encoding="utf-8")
        (root / ".kit").mkdir()
        (root / ".kit" / "capabilities.yaml").write_text(
            f"version: 1\ninclude: [{include}]\nexclude: []\n", encoding="utf-8"
        )

    def test_product_declaration_adds_scoped_skills(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            product = Path(raw)
            self.product(product)
            code, output = self.run_install(product)
        self.assertEqual(code, 0, output)
        for name in SCOPED:
            self.assertIn(name, output)
        resolved = str(product.resolve())
        self.assertIn(f"Install dir: {resolved}", output)
        self.assertIn(f"(cd {resolved}) npx skills add", output)

    def test_real_run_uses_the_product_directory(self) -> None:
        import os
        import subprocess
        import sys
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            product = Path(raw)
            self.product(product)
            bindir = product / ".fakebin"
            bindir.mkdir()
            record = product / "pwd.log"
            stub = bindir / "npx"
            stub.write_text(
                f'#!/bin/sh\necho "$PWD" >> "{record}"\nexit 0\n',
                encoding="utf-8",
            )
            stub.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = f"{bindir}:{env.get('PATH', '')}"
            result = subprocess.run(
                ["bash", str(SCRIPTS / "install.sh"), "--capabilities"],
                cwd=product,
                capture_output=True,
                text=True,
                env=env,
            )
            recorded = record.read_text(encoding="utf-8").split()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(recorded, "npx hiç çağrılmadı")
        for cwd in recorded:
            self.assertEqual(Path(cwd).resolve(), product.resolve())

    def test_plain_directory_installs_into_the_kit(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            plain = Path(raw)
            code, output = self.run_install(plain)
        self.assertEqual(code, 0, output)
        self.assertIn(f"Install dir: {ROOT.resolve()}", output)

    def test_unknown_capability_fails_the_install(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            product = Path(raw)
            self.product(product, include="platform.nonexistent")
            code, output = self.run_install(product)
        self.assertNotEqual(code, 0, output)
        self.assertIn("bilinmeyen capability", output)
