#!/usr/bin/env python3
"""Discover project engineering standards and inject them into AGENTS.md."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

START = "<!-- demir-kit:standards:start -->"
END = "<!-- demir-kit:standards:end -->"
KEYS = ("test", "typecheck", "lint", "format")
IGNORE = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    "target",
    "DerivedData",
    "__pycache__",
}

NODE_LOCKS = (
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("bun.lock", "bun"),
    ("package-lock.json", "npm"),
)
NODE_CONFIGS = (
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.json",
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.yaml",
    "tsconfig.json",
    ".editorconfig",
    "vitest.config.ts",
    "jest.config.js",
)
PYTHON_CONFIGS = (
    "pyproject.toml",
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".flake8",
    ".editorconfig",
)
GO_CONFIGS = (".golangci.yml", ".golangci.yaml", ".editorconfig")
SWIFT_CONFIGS = (".swiftlint.yml", ".swiftformat", ".editorconfig")
RUST_CONFIGS = ("rustfmt.toml", ".rustfmt.toml", "clippy.toml", ".editorconfig")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def load_json(path: Path) -> dict:
    try:
        data = json.loads(read_text(path))
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def add_command(commands: dict[str, list[str]], key: str, value: str | None) -> None:
    if not value:
        return
    value = value.strip()
    if value and value not in commands[key]:
        commands[key].append(value)


def scoped(root: Path, base: Path, command: str) -> str:
    if base == root:
        return command
    return f"cd {shlex.quote(str(base.relative_to(root)))} && {command}"


def add_config(found: dict, root: Path, base: Path, names: tuple[str, ...]) -> None:
    for name in names:
        path = base / name
        if path.exists():
            value = str(path.relative_to(root))
            if value not in found["configs"]:
                found["configs"].append(value)


def manager_for(root: Path, base: Path, locks: tuple) -> str:
    for directory in (base, root):
        for name, manager in locks:
            if (directory / name).is_file():
                return manager
    return "npm"


def set_manager(found: dict, language: str, manager: str) -> None:
    current = found["package_managers"].get(language)
    if not current:
        found["package_managers"][language] = manager
    elif current != manager and manager not in current.split(", "):
        found["package_managers"][language] = current + ", " + manager


def node_standards(root: Path, base: Path, found: dict) -> None:
    package = base / "package.json"
    if not package.is_file():
        return
    manager = manager_for(root, base, NODE_LOCKS)
    set_manager(found, "javascript", manager)
    if (base / "tsconfig.json").is_file():
        found["languages"].append("typescript")
    else:
        found["languages"].append("javascript")
    scripts = load_json(package).get("scripts") or {}
    if not isinstance(scripts, dict):
        scripts = {}
    factory = {
        "test": ("test",),
        "typecheck": ("typecheck", "type-check", "tsc"),
        "lint": ("lint",),
        "format": ("format", "fmt"),
    }
    for key, names in factory.items():
        for name in names:
            if name in scripts:
                add_command(
                    found["commands"], key, scoped(root, base, f"{manager} run {name}")
                )
                break
    add_config(found, root, base, NODE_CONFIGS)


def python_standards(root: Path, base: Path, found: dict) -> None:
    pyproject = base / "pyproject.toml"
    requirements = read_text(base / "requirements.txt").lower()
    setup_cfg = read_text(base / "setup.cfg").lower()
    has_python = (
        pyproject.is_file()
        or (base / "requirements.txt").is_file()
        or (base / "setup.py").is_file()
        or (base / "setup.cfg").is_file()
        or any(base.glob("*.py"))
    )
    if not has_python:
        return
    manager = ""
    for directory in (base, root):
        if (directory / "uv.lock").is_file():
            manager = "uv"
            break
        if (directory / "poetry.lock").is_file():
            manager = "poetry"
            break
    if manager:
        set_manager(found, "python", manager)
    found["languages"].append("python")

    pyproject_text = read_text(pyproject).lower() if pyproject.is_file() else ""
    extra = " ".join(
        read_text(base / name).lower()
        for name in (
            "requirements-dev.txt",
            "requirements_test.txt",
            "requirements-tests.txt",
            "tox.ini",
            "pytest.ini",
        )
    )
    has_pytest = (
        "pytest" in pyproject_text
        or "pytest" in requirements
        or "pytest" in setup_cfg
        or "pytest" in extra
    )
    has_ruff = "ruff" in pyproject_text or "ruff" in requirements
    has_black = "black" in pyproject_text or "black" in requirements
    has_mypy = "mypy" in pyproject_text or "mypy" in requirements

    def command(value: str) -> str:
        if manager:
            value = f"{manager} run {value}"
        return scoped(root, base, value)

    if has_pytest:
        add_command(found["commands"], "test", command("pytest"))
    if has_ruff:
        add_command(found["commands"], "lint", command("ruff check ."))
        add_command(found["commands"], "format", command("ruff format ."))
    elif has_black:
        add_command(found["commands"], "format", command("black ."))
    if has_mypy:
        add_command(found["commands"], "typecheck", command("mypy ."))
    add_config(found, root, base, PYTHON_CONFIGS)


def go_standards(root: Path, base: Path, found: dict) -> None:
    if not (base / "go.mod").is_file():
        return
    set_manager(found, "go", "go modules")
    found["languages"].append("go")
    add_command(found["commands"], "test", scoped(root, base, "go test ./..."))
    add_command(found["commands"], "typecheck", scoped(root, base, "go vet ./..."))
    add_command(found["commands"], "format", scoped(root, base, "gofmt -w ."))
    if (base / ".golangci.yml").is_file() or (base / ".golangci.yaml").is_file():
        add_command(
            found["commands"], "lint", scoped(root, base, "golangci-lint run")
        )
    add_config(found, root, base, GO_CONFIGS)


def swift_standards(root: Path, base: Path, found: dict) -> None:
    has_package = (base / "Package.swift").is_file()
    has_xcode = any(base.glob("*.xcodeproj")) or any(base.glob("*.xcworkspace"))
    if not (has_package or has_xcode):
        return
    found["languages"].append("swift")
    if has_package:
        set_manager(found, "swift", "swiftpm")
        add_command(found["commands"], "test", scoped(root, base, "swift test"))
    if (base / ".swiftlint.yml").is_file():
        add_command(found["commands"], "lint", scoped(root, base, "swiftlint"))
    if (base / ".swiftformat").is_file():
        add_command(found["commands"], "format", scoped(root, base, "swiftformat ."))
    add_config(found, root, base, SWIFT_CONFIGS)


def rust_standards(root: Path, base: Path, found: dict) -> None:
    if not (base / "Cargo.toml").is_file():
        return
    set_manager(found, "rust", "cargo")
    found["languages"].append("rust")
    add_command(found["commands"], "test", scoped(root, base, "cargo test"))
    add_command(
        found["commands"], "lint", scoped(root, base, "cargo clippy --all-targets")
    )
    add_command(found["commands"], "typecheck", scoped(root, base, "cargo check"))
    add_command(found["commands"], "format", scoped(root, base, "cargo fmt --check"))
    add_config(found, root, base, RUST_CONFIGS)


def manifest_roots(root: Path) -> list[Path]:
    """Root plus immediate subdirectories that hold a known manifest."""
    names = {
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "go.mod",
        "Package.swift",
        "Cargo.toml",
    }
    roots = [root]
    for child in sorted(root.iterdir()):
        if child.is_dir() and child.name not in IGNORE:
            if any((child / name).exists() for name in names) or any(
                child.glob("*.xcodeproj")
            ):
                roots.append(child)
    return roots


def managed_block(text: str) -> str | None:
    match = re.search(re.escape(START) + r"(.*?)" + re.escape(END), text, re.S)
    return match.group(0) if match else None


def discover(project: Path) -> dict:
    root = project.resolve()
    found: dict = {
        "project": str(root),
        "languages": [],
        "package_managers": {},
        "commands": {key: [] for key in KEYS},
        "configs": [],
        "agents": {
            "exists": (root / "AGENTS.md").is_file(),
            "managed": False,
            "state": "missing_file",
        },
    }
    for base in manifest_roots(root):
        for detect in (
            node_standards,
            python_standards,
            go_standards,
            swift_standards,
            rust_standards,
        ):
            detect(root, base, found)
    found["languages"] = sorted(set(found["languages"]))
    found["package_managers"] = dict(sorted(found["package_managers"].items()))
    found["configs"] = sorted(set(found["configs"]))

    agents = root / "AGENTS.md"
    if agents.is_file():
        existing = read_text(agents)
        block = managed_block(existing)
        found["agents"]["managed"] = block is not None
        if block is None:
            found["agents"]["state"] = "missing_block"
        elif block != render_block(found):
            found["agents"]["state"] = "stale"
        else:
            found["agents"]["state"] = "ok"
    return found


def render_block(data: dict) -> str:
    lines = [START, "## Proje standartları", ""]
    managers = data.get("package_managers") or {}
    if managers:
        lines.append(
            "- Paket yöneticisi: "
            + ", ".join(f"{name} ({language})" for language, name in managers.items())
        )
    labels = (
        ("test", "Test"),
        ("typecheck", "Tip"),
        ("lint", "Lint"),
        ("format", "Biçim"),
    )
    for key, label in labels:
        values = (data.get("commands") or {}).get(key) or []
        for value in values:
            lines.append(f"- {label}: `{value}`")
    configs = data.get("configs") or []
    if configs:
        lines.append("- Yapılandırma: " + ", ".join(f"`{name}`" for name in configs))
    if not managers and not any((data.get("commands") or {}).values()):
        lines.append(
            "- Tespit edilen komut yok; gate komutlarını `ecosystem.yaml` içinde tanımlayın."
        )
    lines.extend(
        [
            "",
            "Bu blok otomatik üretilir. Config değişince `standards.py --apply`",
            "çalıştırın; bloğu elle düzenlemeyin.",
            END,
        ]
    )
    return "\n".join(lines)


def proposed_text(existing: str, block: str) -> str:
    current = managed_block(existing)
    if current is not None:
        return existing.replace(current, block, 1)
    body = existing.rstrip("\n")
    if not body:
        return "# Agents\n\n" + block + "\n"
    return body + "\n\n" + block + "\n"


def inject(project: Path, apply: bool = False) -> dict:
    root = project.resolve()
    data = discover(root)
    block = render_block(data)
    agents = root / "AGENTS.md"
    existing = read_text(agents) if agents.is_file() else ""
    text = proposed_text(existing, block)
    changed = text != existing
    if apply and changed:
        agents.write_text(text, encoding="utf-8")
    return {
        "project": str(root),
        "changed": changed,
        "applied": bool(apply and changed),
        "block": block,
        "text": text,
    }


def check(project: Path) -> list[str]:
    data = discover(project)
    state = data["agents"]["state"]
    if state == "missing_file":
        return ["AGENTS.md yok"]
    if state == "missing_block":
        return ["AGENTS.md içinde standart bloğu yok"]
    if state == "stale":
        return ["standart bloğu bayat; --apply ile yenile"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="discover project standards")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.check:
        errors = check(args.project)
        for message in errors:
            print(f"[fail] {message}")
        print(f"{len(errors)} hata")
        return 1 if errors else 0

    data = discover(args.project)
    result = inject(args.project, apply=args.apply)
    if args.json:
        print(
            json.dumps(
                {**data, "changed": result["changed"], "applied": result["applied"]},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    lines = [
        f"project: {data['project']}",
        "languages: " + (", ".join(data["languages"]) or "-"),
        "package managers: " + (
            ", ".join(f"{k}={v}" for k, v in data["package_managers"].items()) or "-"
        ),
    ]
    for key in KEYS:
        values = data["commands"][key]
        lines.append(f"{key}: " + (", ".join(values) or "-"))
    lines.append("configs: " + (", ".join(data["configs"]) or "-"))
    lines.append("agents block: " + data["agents"]["state"])
    if args.apply:
        lines.append("applied: evet" if result["applied"] else "applied: değişiklik yok")
    else:
        lines.append("dry-run: --apply ile yazılır")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
