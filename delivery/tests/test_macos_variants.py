"""macOS variant mapping tests (issue #120).

Run: python3 -m unittest discover -s delivery/tests -v
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"

spec = importlib.util.spec_from_file_location("variants", SCRIPTS / "variants.py")
variants = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(variants)

ROLES = ("designer", "developer", "tester", "architect")
SECTIONS = [
    "Kapsam",
    "Girdiler",
    "Yöntem",
    "Kanıt",
    "Gate rubriği",
    "Anti-pattern'ler",
    "Handoff",
]


class MacosAliasTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.agent_dir = Path(self.temp.name)
        (self.agent_dir / "variants").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_alias_rejected_when_macos_doc_exists(self) -> None:
        (self.agent_dir / "variants" / "macos.md").write_text("x\n", encoding="utf-8")
        message = variants.macos_alias_error(
            "designer", "platform.macos", "variants/ios.md", self.agent_dir
        )
        self.assertIsNotNone(message)
        self.assertIn("macos.md", message or "")

    def test_own_doc_accepted(self) -> None:
        (self.agent_dir / "variants" / "macos.md").write_text("x\n", encoding="utf-8")
        self.assertIsNone(
            variants.macos_alias_error(
                "designer", "platform.macos", "variants/macos.md", self.agent_dir
            )
        )

    def test_role_without_macos_doc_is_not_forced(self) -> None:
        self.assertIsNone(
            variants.macos_alias_error(
                "security", "platform.macos", "variants/mobile.md", self.agent_dir
            )
        )

    def test_other_platforms_are_not_checked(self) -> None:
        (self.agent_dir / "variants" / "macos.md").write_text("x\n", encoding="utf-8")
        self.assertIsNone(
            variants.macos_alias_error(
                "designer", "platform.ios", "variants/ios.md", self.agent_dir
            )
        )


class MacosMappingTest(unittest.TestCase):
    def test_roles_map_macos_to_its_own_doc(self) -> None:
        for role in ROLES:
            with self.subTest(role=role):
                data = yaml.safe_load(
                    (ROOT / "delivery" / "agents" / role / "agent.yaml").read_text(
                        encoding="utf-8"
                    )
                )
                spec_entry = (data.get("variants") or {}).get("platform.macos") or {}
                self.assertEqual(spec_entry.get("doc"), "variants/macos.md")

    def test_roles_map_macos_eval_to_macos_set(self) -> None:
        for role in ROLES:
            with self.subTest(role=role):
                data = yaml.safe_load(
                    (ROOT / "delivery" / "agents" / role / "agent.yaml").read_text(
                        encoding="utf-8"
                    )
                )
                spec_entry = (data.get("variants") or {}).get("platform.macos") or {}
                self.assertEqual(spec_entry.get("eval"), "evals/macos.md")

    def test_api_and_cli_keep_shared_doc(self) -> None:
        for role in ("architect", "developer"):
            data = yaml.safe_load(
                (ROOT / "delivery" / "agents" / role / "agent.yaml").read_text(
                    encoding="utf-8"
                )
            )
            for cap_id in ("platform.api", "platform.cli"):
                with self.subTest(role=role, capability=cap_id):
                    spec_entry = (data.get("variants") or {}).get(cap_id) or {}
                    self.assertEqual(spec_entry.get("doc"), "variants/api.md")

    def test_resolver_json_has_no_ios_paths_for_macos(self) -> None:
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
        variants_out = payload.get("active_variants") or []
        paths = [
            str(item.get("doc")) + " " + str(item.get("eval")) for item in variants_out
        ]
        for path in paths:
            self.assertNotIn("ios.md", path, payload)
        for item in variants_out:
            if item.get("role") in ROLES:
                self.assertEqual(item.get("doc"), "variants/macos.md", item)
                self.assertEqual(item.get("eval"), "evals/macos.md", item)

    def test_variant_docs_have_seven_sections(self) -> None:
        for role in ROLES:
            path = ROOT / "delivery" / "agents" / role / "variants" / "macos.md"
            headings = [
                line[3:].strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.startswith("## ")
            ]
            self.assertEqual(headings, SECTIONS, role)

    def test_validate_agent_reports_alias(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            agent_dir = root / "designer"
            (agent_dir / "variants").mkdir(parents=True)
            (agent_dir / "evals").mkdir()
            (agent_dir / "variants" / "macos.md").write_text("x\n", encoding="utf-8")
            (agent_dir / "variants" / "ios.md").write_text("x\n", encoding="utf-8")
            (agent_dir / "variants" / "web.md").write_text("x\n", encoding="utf-8")
            (agent_dir / "evals" / "macos.md").write_text("x\n", encoding="utf-8")
            agent = {
                "id": "designer",
                "variants": {
                    "platform.macos": {
                        "doc": "variants/ios.md",
                        "eval": "evals/macos.md",
                        "min_level": "expert",
                    }
                },
                "handoffs": [],
                "escalation": ["x"],
            }
            capabilities = {"capabilities": {"platform.macos": {"roles": {}}}}
            errors = variants.validate_agent(
                "designer", agent, capabilities, {"designer"}, root=root
            )
        self.assertTrue(any("macos.md" in item for item in errors), errors)

    def test_repository_variants_validate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "variants.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_resolver_has_no_ios_doc_for_macos(self) -> None:
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
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        docs = [line.strip("- ").strip() for line in result.stdout.splitlines()]
        self.assertFalse(
            [doc for doc in docs if doc.endswith("variants/ios.md")], result.stdout
        )
        self.assertTrue(
            [doc for doc in docs if doc.endswith("variants/macos.md")], result.stdout
        )


if __name__ == "__main__":
    unittest.main()
