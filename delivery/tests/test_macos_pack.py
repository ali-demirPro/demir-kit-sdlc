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


class DirectDistributionTest(unittest.TestCase):
    def test_dmg_keyword_activates_capability(self) -> None:
        data = resolve(
            "--surface", "macos.app", "--platform", "macos", "--distribution", "dmg"
        )
        self.assertIn("distribution.direct", data["capabilities"])

    def test_risk_floor_is_medium(self) -> None:
        data = resolve(
            "--surface", "macos.app", "--platform", "macos", "--distribution", "dmg"
        )
        self.assertEqual(data["risk_floor"], "medium")

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
                self.assertTrue(spec.get("doc"), role)

    def test_registry_scripts_are_green(self) -> None:
        for script in ("variants.py", "capabilities.py", "profiles.py"):
            with self.subTest(script=script):
                args = [sys.executable, str(SCRIPTS / script)]
                if script == "variants.py":
                    args.append("--role")
                    args.append("devops")
                elif script == "profiles.py":
                    args.extend(["--project", str(ROOT)])
                result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
