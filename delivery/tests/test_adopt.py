"""Tests for one-command adoption."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("adopt", SCRIPTS / "adopt.py")
adopt = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(adopt)


def write(root: Path, name: str, text: str = "") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def api_project(root: Path) -> None:
    write(
        root,
        "pyproject.toml",
        "[tool.pytest.ini_options]\n[tool.ruff]\n",
    )
    write(root, "app/main.py", "print(1)\n")


def web_project(root: Path) -> None:
    write(
        root,
        "package.json",
        json.dumps(
            {
                "dependencies": {"next": "1", "react": "1"},
                "scripts": {"test": "vitest", "lint": "eslint ."},
            }
        ),
    )
    write(root, "src/app.ts", "export default 1\n")


class AdoptTests(unittest.TestCase):
    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_project(root)
            data = adopt.plan(root)
            self.assertFalse((root / "kit.config.yaml").exists())
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / "demir-kit").exists())
            self.assertEqual(data["profiles"], ["web-app"])
            self.assertTrue(data["vendor"])
            self.assertIn("surfaces", data)
            self.assertIn("verify", data)
            self.assertTrue(data["verify"]["ok"], data["verify"]["issues"])

    def test_apply_installs_sdlc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_project(root)
            data = adopt.apply(root)
            self.assertTrue(data["applied"], data["issues"])
            self.assertTrue(data["verify"]["ok"], data["verify"]["issues"])
            self.assertTrue((root / "kit.config.yaml").is_file())
            self.assertTrue((root / ".kit/capabilities.yaml").is_file())
            self.assertTrue((root / "scripts/gate-behavior.sh").is_file())
            self.assertTrue((root / "demir-kit/delivery/scripts/doctor.py").is_file())
            self.assertTrue((root / "demir-kit/skills").is_dir())
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn(adopt.standards_mod.START, agents)
            self.assertIn("`npm run test`", agents)

    def test_apply_api_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api_project(root)
            data = adopt.apply(root)
            self.assertTrue(data["verify"]["ok"], data["verify"]["issues"])
            self.assertEqual(data["profiles"], ["api-service"])
            gate = (root / "scripts/gate-behavior.sh").read_text(encoding="utf-8")
            self.assertIn("pytest", gate)

    def test_cli_apply_and_failure_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_project(root)
            output = io.StringIO()
            with patch.object(
                sys, "argv", ["adopt.py", "--project", str(root), "--apply", "--json"]
            ), contextlib.redirect_stdout(output):
                self.assertEqual(adopt.main(), 0)
            self.assertTrue(json.loads(output.getvalue())["verify"]["ok"])
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.object(
                sys, "argv", ["adopt.py", "--project", directory, "--apply", "--json"]
            ), contextlib.redirect_stdout(output):
                self.assertEqual(adopt.main(), 1)
            self.assertFalse(json.loads(output.getvalue())["verify"]["ok"])

    def test_missing_project_and_bad_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(adopt.plan(root / "missing")["issues"])
            write(root, "kit.config.yaml", "factory: [\n")
            data = adopt.plan(root)
            self.assertTrue(any("okunamadı" in item for item in data["issues"]))

    def test_apply_preserves_existing_agents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_project(root)
            write(root, "AGENTS.md", "# Agents\n\n## Kural\n\n- Kısa diff.\n")
            adopt.apply(root)
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("## Kural", agents)
            self.assertIn("- Kısa diff.", agents)
            self.assertIn(adopt.standards_mod.START, agents)

    def test_second_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web_project(root)
            adopt.apply(root)
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            data = adopt.apply(root)
            self.assertTrue(data["verify"]["ok"])
            init_step = next(
                step for step in data["steps"] if step["step"] == "init"
            )
            standards_step = next(
                step for step in data["steps"] if step["step"] == "standards"
            )
            self.assertEqual(init_step["written"], [])
            self.assertFalse(standards_step["changed"])
            self.assertEqual(
                (root / "AGENTS.md").read_text(encoding="utf-8"), agents
            )

    def test_overlap_is_refused_without_writes(self) -> None:
        before = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        data = adopt.apply(ROOT)
        self.assertFalse(data["applied"])
        self.assertTrue(data["issues"])
        self.assertEqual((ROOT / "AGENTS.md").read_text(encoding="utf-8"), before)

    def test_empty_project_apply_fails_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = adopt.apply(Path(directory))
            self.assertTrue(data["applied"])
            self.assertFalse(data["verify"]["ok"])
            self.assertTrue(any("yüzey" in item for item in data["verify"]["issues"]))


if __name__ == "__main__":
    unittest.main()
