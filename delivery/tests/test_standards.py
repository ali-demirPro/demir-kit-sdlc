"""Tests for standards discovery and injection."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "delivery" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("standards", SCRIPTS / "standards.py")
standards = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(standards)


def write(root: Path, name: str, text: str = "") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def node_project(root: Path) -> None:
    write(
        root,
        "package.json",
        json.dumps(
            {
                "scripts": {
                    "test": "vitest",
                    "lint": "eslint .",
                    "typecheck": "tsc --noEmit",
                    "format": "prettier --write .",
                }
            }
        ),
    )
    write(root, "pnpm-lock.yaml", "lockfileVersion: 9\n")
    write(root, "tsconfig.json", "{}")
    write(root, ".editorconfig", "root = true\n")


def python_project(root: Path) -> None:
    write(
        root,
        "pyproject.toml",
        "[tool.pytest.ini_options]\n"
        "[tool.ruff]\n"
        "[tool.mypy]\n",
    )
    write(root, "uv.lock", "version = 1\n")
    write(root, "src/app.py", "print(1)\n")


class DiscoverTests(unittest.TestCase):
    def test_node_pnpm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node_project(root)
            data = standards.discover(root)
            self.assertEqual(data["package_managers"]["javascript"], "pnpm")
            self.assertIn("typescript", data["languages"])
            self.assertEqual(data["commands"]["test"], ["pnpm run test"])
            self.assertEqual(data["commands"]["lint"], ["pnpm run lint"])
            self.assertEqual(data["commands"]["typecheck"], ["pnpm run typecheck"])
            self.assertEqual(data["commands"]["format"], ["pnpm run format"])
            self.assertIn("tsconfig.json", data["configs"])
            self.assertIn(".editorconfig", data["configs"])

    def test_python_uv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python_project(root)
            data = standards.discover(root)
            self.assertEqual(data["package_managers"]["python"], "uv")
            self.assertEqual(data["commands"]["test"], ["uv run pytest"])
            self.assertEqual(data["commands"]["lint"], ["uv run ruff check ."])
            self.assertEqual(data["commands"]["typecheck"], ["uv run mypy ."])
            self.assertEqual(data["commands"]["format"], ["uv run ruff format ."])

    def test_go_module(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "go.mod", "module example.com/app\n")
            write(root, ".golangci.yml", "run: {}\n")
            data = standards.discover(root)
            self.assertEqual(
                data["commands"]["test"], ["go test ./..."]
            )
            self.assertEqual(
                data["commands"]["lint"], ["golangci-lint run"]
            )
            self.assertEqual(data["commands"]["typecheck"], ["go vet ./..."])
            self.assertEqual(data["commands"]["format"], ["gofmt -w ."])

    def test_swift_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "Package.swift", "// swift-tools-version: 5.9\n")
            write(root, ".swiftlint.yml", "disabled_rules: []\n")
            write(root, ".swiftformat", "--indent 4\n")
            data = standards.discover(root)
            self.assertEqual(data["commands"]["test"], ["swift test"])
            self.assertEqual(data["commands"]["lint"], ["swiftlint"])
            self.assertEqual(data["commands"]["format"], ["swiftformat ."])

    def test_polyglot_keeps_both(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node_project(root)
            write(root, "api/pyproject.toml", "[tool.pytest.ini_options]\n")
            write(root, "api/app.py", "print(1)\n")
            data = standards.discover(root)
            self.assertEqual(
                data["commands"]["test"], ["pnpm run test", "cd api && pytest"]
            )
            self.assertIn("javascript", data["package_managers"])
            self.assertIn("python", data["languages"])

    def test_nested_poetry_beats_root_uv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "uv.lock", "version = 1\n")
            write(
                root,
                "api/pyproject.toml",
                "[tool.pytest.ini_options]\n",
            )
            write(root, "api/poetry.lock", "[[package]]\n")
            write(root, "api/app.py", "print(1)\n")
            data = standards.discover(root)
            self.assertEqual(data["package_managers"]["python"], "poetry")
            self.assertEqual(data["commands"]["test"], ["cd api && poetry run pytest"])

    def test_tests_dir_alone_does_not_imply_pytest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "requirements.txt", "requests\n")
            write(root, "app.py", "print(1)\n")
            write(root, "tests/test_app.py", "def test_x(): pass\n")
            data = standards.discover(root)
            self.assertNotIn("pytest", " ".join(data["commands"]["test"]))

    def test_js_tests_dir_is_not_python(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node_project(root)
            write(root, "tests/app.test.ts", "test('x', () => {})\n")
            data = standards.discover(root)
            self.assertEqual(data["languages"], ["typescript"])
            self.assertNotIn("python", data["package_managers"])

    def test_tooling_pyproject_does_not_add_pytest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node_project(root)
            write(root, "pyproject.toml", "[tool.black]\n")
            write(root, "tests/app.test.ts", "test('x', () => {})\n")
            data = standards.discover(root)
            self.assertEqual(data["commands"]["test"], ["pnpm run test"])
            self.assertEqual(data["languages"], ["python", "typescript"])

    def test_scoped_path_with_space_is_quoted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "api app/go.mod", "module example.com/app\n")
            data = standards.discover(root)
            self.assertEqual(
                data["commands"]["test"], ["cd 'api app' && go test ./..."]
            )

    def test_empty_project_has_no_invented_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = standards.discover(Path(directory))
            self.assertEqual(data["languages"], [])
            self.assertEqual(data["commands"], {key: [] for key in standards.KEYS})


class InjectTests(unittest.TestCase):
    def test_apply_creates_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node_project(root)
            result = standards.inject(root, apply=True)
            self.assertTrue(result["applied"])
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Agents"))
            self.assertIn(standards.START, text)
            self.assertIn("`pnpm run test`", text)
            self.assertTrue(text.rstrip().endswith(standards.END))

    def test_apply_preserves_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node_project(root)
            original = "# Agents\n\n## Kurallar\n\n- Kısa diff.\n"
            write(root, "AGENTS.md", original)
            standards.inject(root, apply=True)
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("## Kurallar", text)
            self.assertIn("- Kısa diff.", text)
            self.assertIn(standards.START, text)

    def test_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node_project(root)
            standards.inject(root, apply=True)
            first = (root / "AGENTS.md").read_text(encoding="utf-8")
            result = standards.inject(root, apply=True)
            self.assertFalse(result["changed"])
            self.assertFalse(result["applied"])
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), first)

    def test_existing_block_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node_project(root)
            write(
                root,
                "AGENTS.md",
                "# Agents\n\n"
                + standards.START
                + "\n## Proje standartları\n\n- Eski: `komut`\n"
                + standards.END
                + "\n\n## Son\n",
            )
            result = standards.inject(root, apply=True)
            self.assertTrue(result["changed"])
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertNotIn("Eski: `komut`", text)
            self.assertIn("`pnpm run test`", text)
            self.assertTrue(text.rstrip().endswith("## Son"))

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node_project(root)
            result = standards.inject(root)
            self.assertTrue(result["changed"])
            self.assertFalse((root / "AGENTS.md").exists())

    def test_check_reports_missing_and_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node_project(root)
            self.assertTrue(standards.check(root))
            standards.inject(root, apply=True)
            self.assertEqual(standards.check(root), [])
            package = json.loads((root / "package.json").read_text(encoding="utf-8"))
            package["scripts"] = {"check": "jest"}
            (root / "package.json").write_text(json.dumps(package), encoding="utf-8")
            self.assertTrue(any("bayat" in item for item in standards.check(root)))

    def test_check_missing_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "AGENTS.md", "# Agents\n")
            self.assertTrue(any("standart" in item for item in standards.check(root)))


if __name__ == "__main__":
    unittest.main()
