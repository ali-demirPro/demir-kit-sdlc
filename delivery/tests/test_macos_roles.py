"""macOS variants for the remaining three roles (issue #123).

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
ROLES = ("security", "devops", "marketing/stores")
SECTIONS = [
    "Kapsam",
    "Girdiler",
    "Yöntem",
    "Kanıt",
    "Gate rubriği",
    "Anti-pattern'ler",
    "Handoff",
]


class RemainingRolesTest(unittest.TestCase):
    def test_roles_map_macos_to_own_doc_and_eval(self) -> None:
        for role in ROLES:
            with self.subTest(role=role):
                data = yaml.safe_load(
                    (ROOT / "delivery" / "agents" / role / "agent.yaml").read_text(
                        encoding="utf-8"
                    )
                )
                spec = (data.get("variants") or {}).get("platform.macos") or {}
                self.assertEqual(spec.get("doc"), "variants/macos.md")
                self.assertEqual(spec.get("eval"), "evals/macos.md")

    def test_variant_docs_have_seven_sections(self) -> None:
        for role in ROLES:
            path = ROOT / "delivery" / "agents" / role / "variants" / "macos.md"
            headings = [
                line[3:].strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.startswith("## ")
            ]
            self.assertEqual(headings, SECTIONS, role)

    def test_eval_sets_have_ten_scenarios(self) -> None:
        for role in ROLES:
            path = ROOT / "delivery" / "agents" / role / "evals" / "macos.md"
            rows = [
                line
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.startswith("|") and "---" not in line
            ]
            self.assertGreaterEqual(len(rows) - 1, 10, role)

    def test_eval_check_is_green(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "eval.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_resolver_has_no_mobile_doc_for_macos(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "resolver.py"),
                "--surface",
                "macos.app",
                "--platform",
                "macos",
                "--stack",
                "swiftui",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        for item in payload.get("active_variants") or []:
            self.assertNotIn("mobile.md", str(item.get("doc")), item)
            self.assertNotIn("ios.md", str(item.get("doc")), item)


class AliasLintTest(unittest.TestCase):
    def test_alias_is_rejected_for_new_roles(self) -> None:
        from unittest.mock import patch

        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "variants", SCRIPTS / "variants.py"
        )
        variants = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(variants)
        for role in ROLES:
            with self.subTest(role=role):
                agent_dir = ROOT / "delivery" / "agents" / role
                message = variants.macos_alias_error(
                    role, "platform.macos", "variants/mobile.md", agent_dir
                )
                self.assertIsNotNone(message, role)


if __name__ == "__main__":
    unittest.main()
