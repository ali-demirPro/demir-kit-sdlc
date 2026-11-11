"""Doküman komut duman testi: AGENTS.md ve README.md içindeki `./...`
yolları mevcut ve çalıştırılabilir olmalı."""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ("AGENTS.md", "README.md")
# `../Product` gibi göreli yolları dışlamak için `./` önünde kelime/nokta olmamalı.
COMMAND_RE = re.compile(r"(?<![A-Za-z0-9_.])(\./[A-Za-z0-9_./-]+)")
EXECUTABLE_SUFFIXES = {".py", ".sh"}


def extract_commands(text: str) -> list[str]:
    """Doküman metninden `./...` komut yollarını çıkarır (sıra korunur, tekrar yok)."""
    commands: list[str] = []
    for raw in COMMAND_RE.findall(text):
        token = raw.rstrip(".,;:!?)]")
        if token and token not in commands:
            commands.append(token)
    return commands


def check_commands(commands: list[str], root: Path) -> list[str]:
    """Her komut yolu için sorun açıklamaları döner; boş liste = temiz."""
    problems: list[str] = []
    for rel in commands:
        path = root / rel[2:]  # baştaki "./" kaldır
        if not path.exists():
            problems.append(f"{rel}: dosya yok")
            continue
        if not path.is_file():
            problems.append(f"{rel}: dosya değil")
            continue
        if path.suffix in EXECUTABLE_SUFFIXES and not os.access(path, os.X_OK):
            problems.append(f"{rel}: çalıştırılabilir değil (X_OK yok)")
    return problems


class DocsCommandsTests(unittest.TestCase):
    def test_agents_md_commands_exist_and_executable(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        problems = check_commands(extract_commands(text), ROOT)
        self.assertEqual([], problems)

    def test_readme_md_commands_exist_and_executable(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        problems = check_commands(extract_commands(text), ROOT)
        self.assertEqual([], problems)

    def test_missing_command_fixture_fails(self) -> None:
        fake = "```bash\n./delivery/scripts/definitely-not-there.sh --flag\n```\n"
        problems = check_commands(extract_commands(fake), ROOT)
        self.assertTrue(problems)
        self.assertIn("dosya yok", problems[0])

    def test_non_executable_fixture_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "script.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            script.chmod(0o644)
            problems = check_commands(extract_commands("./script.sh --run\n"), root)
            self.assertTrue(
                any("çalıştırılabilir değil" in p for p in problems),
                problems,
            )

    def test_valid_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "script.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            script.chmod(0o755)
            problems = check_commands(extract_commands("./script.sh\n"), root)
            self.assertEqual([], problems)

    def test_parent_relative_paths_are_not_extracted(self) -> None:
        text = "./delivery/scripts/doctor.sh --target ../Product --check\n"
        commands = extract_commands(text)
        self.assertIn("./delivery/scripts/doctor.sh", commands)
        self.assertNotIn("./Product", commands)


if __name__ == "__main__":
    unittest.main()
