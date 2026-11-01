"""apple-macos pack and direct-distribution capability tests (issue #121).

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
PACK = ROOT / "delivery" / "packs" / "apple-macos" / "checklist.md"
PROFILE = ROOT / "delivery" / "profiles" / "macos-app.yaml"


def resolve(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "resolver.py"), "--json", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def pack_items() -> list[str]:
    """Split the numbered checklist into one block per item."""
    items: list[str] = []
    current: list[str] = []
    for line in PACK.read_text(encoding="utf-8").splitlines():
        head = line.split(".", 1)[0]
        if head.isdigit() and ". " in line[:5]:
            if current:
                items.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        items.append("\n".join(current))
    return items


class AppleMacosPackTest(unittest.TestCase):
    def test_pack_has_fourteen_items(self) -> None:
        self.assertEqual(len(pack_items()), 14)

    def test_every_item_cites_a_source(self) -> None:
        for item in pack_items():
            self.assertIn("(", item, item)

    def test_pack_covers_macos_specific_topics(self) -> None:
        text = PACK.read_text(encoding="utf-8").lower()
        for topic in (
            "menü çubuğu",
            "toolbar",
            "sandbox",
            "notarization",
            "liquid glass",
            "kısayol",
        ):
            self.assertIn(topic, text)

    def test_profile_lists_the_pack(self) -> None:
        profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
        self.assertIn("apple-macos", profile.get("platform_packs") or [])

    def test_pack_is_listed_in_readme(self) -> None:
        readme = (ROOT / "delivery" / "packs" / "README.md").read_text(encoding="utf-8")
        self.assertIn("apple-macos", readme)


class ProfilePacksTest(unittest.TestCase):
    def test_every_profile_pack_exists(self) -> None:
        packs_dir = ROOT / "delivery" / "packs"
        available = {path.name for path in packs_dir.iterdir() if path.is_dir()}
        for path in (ROOT / "delivery" / "profiles").glob("*.yaml"):
            profile = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for pack in profile.get("platform_packs") or []:
                with self.subTest(profile=path.name, pack=pack):
                    self.assertIn(pack, available)


class DirectDistributionTest(unittest.TestCase):
    def test_dmg_keyword_activates_capability(self) -> None:
        data = resolve(
            "--surface", "macos.app", "--platform", "macos", "--distribution", "dmg"
        )
        self.assertIn("distribution.direct", data["capabilities"])

    def test_every_distribution_value_activates(self) -> None:
        for value in ("direct", "dmg", "notarize", "notarization", "notarized", "sparkle"):
            with self.subTest(distribution=value):
                data = resolve(
                    "--surface",
                    "macos.app",
                    "--platform",
                    "macos",
                    "--distribution",
                    value,
                )
                self.assertIn("distribution.direct", data["capabilities"])
                self.assertEqual(data["risk_floor"], "medium")

    def test_app_store_only_project_does_not_activate_direct(self) -> None:
        data = resolve(
            "--surface",
            "macos.app",
            "--platform",
            "macos",
            "--distribution",
            "app_store_connect",
        )
        self.assertNotIn("distribution.direct", data["capabilities"])

    def test_risk_floor_is_medium(self) -> None:
        registry = yaml.safe_load(
            (ROOT / "delivery" / "capabilities" / "registry.yaml").read_text(
                encoding="utf-8"
            )
        )
        spec = registry["capabilities"]["distribution.direct"]
        self.assertEqual(spec["risk_floor"], "medium")

    def test_low_risk_dmg_seal_is_rejected(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "doctor", SCRIPTS / "doctor.py"
        )
        doctor = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(doctor)
        doctor.ERRORS.clear()
        seal = {
            "demir_kit_version": "2",
            "package_version": 4,
            "mode": "extend",
            "epic": 119,
            "entry": {"kind": "chore"},
            "factory": {"profile": "kit-internal", "distribution": ["dmg"]},
            "intent": "Dagitim kanali icin risk tabani regresyon testi.",
            "surfaces": ["kit.docs"],
            "reference": {"kind": "github_paths", "summary": "Test referansi."},
            "acceptance_criteria": [{"id": "AC-1", "text": "Bir dogrulama adimi."}],
            "out_of_scope": ["Kapsam disi"],
            "risk": {"level": "low", "reasons": ["test"]},
            "tests_plan": [
                {
                    "checkpoint_id": "CP-1",
                    "cases": [
                        {
                            "id": "T-1",
                            "ac": "AC-1",
                            "text": "Dogrulama.",
                            "check": "unit",
                        }
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
                        "human": True,
                    },
                }
            ],
        }
        body = "```yaml demir-kit\n" + yaml.safe_dump(seal, sort_keys=False) + "```\n"
        doctor.check_issue_body(body, [], None)
        self.assertTrue(
            any("risk_floor" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_capability_human_gate_is_enforced(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "doctor", SCRIPTS / "doctor.py"
        )
        doctor = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(doctor)
        doctor.ERRORS.clear()
        seal = {
            "demir_kit_version": "2",
            "package_version": 4,
            "mode": "extend",
            "epic": 119,
            "entry": {"kind": "chore"},
            "factory": {"profile": "kit-internal", "distribution": ["dmg"]},
            "intent": "Insan kapisi regresyon testi icin seal.",
            "surfaces": ["kit.docs"],
            "reference": {"kind": "github_paths", "summary": "Test referansi."},
            "acceptance_criteria": [{"id": "AC-1", "text": "Bir dogrulama adimi."}],
            "out_of_scope": ["Kapsam disi"],
            "risk": {"level": "medium", "reasons": ["test"]},
            "tests_plan": [
                {
                    "checkpoint_id": "CP-1",
                    "cases": [
                        {
                            "id": "T-1",
                            "ac": "AC-1",
                            "text": "Dogrulama.",
                            "check": "unit",
                        }
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
        body = "```yaml demir-kit\n" + yaml.safe_dump(seal, sort_keys=False) + "```\n"
        doctor.check_issue_body(body, [], None)
        self.assertTrue(
            any("insan kapısı" in item for item in doctor.ERRORS), doctor.ERRORS
        )

    def test_capability_has_gates_and_evidence(self) -> None:
        registry = yaml.safe_load(
            (ROOT / "delivery" / "capabilities" / "registry.yaml").read_text(
                encoding="utf-8"
            )
        )
        spec = registry["capabilities"]["distribution.direct"]
        self.assertIn("human", spec["gates"])
        self.assertIn("notarization", spec["evidence"])
        self.assertEqual(spec["risk_floor"], "medium")

    def test_roles_have_variants(self) -> None:
        for role in ("devops", "security", "tester"):
            with self.subTest(role=role):
                data = yaml.safe_load(
                    (ROOT / "delivery" / "agents" / role / "agent.yaml").read_text(
                        encoding="utf-8"
                    )
                )
                spec = (data.get("variants") or {}).get("distribution.direct") or {}
                doc = str(spec.get("doc") or "")
                self.assertEqual(doc, "variants/direct.md", role)
                self.assertTrue(
                    (ROOT / "delivery" / "agents" / role / doc).is_file(), role
                )

    def test_registry_scripts_are_green(self) -> None:
        for script in ("variants.py", "capabilities.py", "profiles.py"):
            with self.subTest(script=script):
                args = [sys.executable, str(SCRIPTS / script)]
                if script == "variants.py":
                    args.append("--role")
                    args.append("devops")
                elif script == "capabilities.py":
                    args.append("--validate")
                elif script == "profiles.py":
                    args.extend(["--project", str(ROOT), "--check"])
                result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
