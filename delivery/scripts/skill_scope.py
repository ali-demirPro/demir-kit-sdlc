#!/usr/bin/env python3
"""Resolve which skills a project should install.

Runtime skills are always installed. Scoped skills (registry `skills.scoped`)
are installed only when the project declares the matching capability in
`.kit/capabilities.yaml`.

`--root` yalnız `registry.yaml` konumunu belirler; capability çözümlemesi
(profil ve .kit bildirimi) her zaman kit köküne göre yapılır.

Usage:
  python3 delivery/scripts/skill_scope.py --project .
  python3 delivery/scripts/skill_scope.py --project . --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("skill_scope: PyYAML required (python3 -m pip install pyyaml)")

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(Path(__file__).resolve().parent))

import resolver  # noqa: E402
import routing  # noqa: E402


def load_registry(root: Path) -> dict:
    path = root / "delivery" / "registry.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_project(cwd: Path, kit_root: Path) -> Path:
    """Product root when the caller stands in one; otherwise the kit root.

    Delegates to routing.project_root so the rule lives in one place.
    """
    return routing.project_root(Path(kit_root), Path(cwd))


def declared_capabilities(project: Path) -> set[str]:
    """Effective capabilities for the project, or ValueError when unclear.

    Uses the kit resolver so profile-composed capabilities count and `exclude`
    is honoured; a malformed file or an unknown capability is an error, never a
    silent runtime-only install.
    """
    path = project / ".kit" / "capabilities.yaml"
    if path.is_file():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f".kit/capabilities.yaml okunamadı: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(".kit/capabilities.yaml kök mapping değil")
        for key in ("include", "exclude"):
            if key in data and not isinstance(data[key], list):
                raise ValueError(f".kit/capabilities.yaml {key} liste değil")
    declared = resolver.load_declared(project)
    active = set(declared.get("include") or []) - set(declared.get("exclude") or [])
    available = set((resolver.load_capabilities().get("capabilities") or {}).keys())
    unknown = sorted(active - available)
    if unknown:
        raise ValueError("bilinmeyen capability: " + ", ".join(unknown))
    return active


def select(project: Path, root: Path = ROOT) -> dict:
    skills = (load_registry(root).get("skills") or {}) if isinstance(load_registry(root), dict) else {}
    runtime = [str(name) for name in skills.get("runtime") or []]
    scoped_map = skills.get("scoped") or {}
    declared = declared_capabilities(project) if project else set()
    scoped: list[str] = []
    for capability, names in (scoped_map.items() if isinstance(scoped_map, dict) else []):
        if str(capability) not in declared:
            continue
        for name in names or []:
            name = str(name)
            if name not in scoped:
                scoped.append(name)
    install: list[str] = []
    for name in runtime + scoped:
        if name not in install:
            install.append(name)
    return {
        "runtime": runtime,
        "scoped": scoped,
        "install": install,
        "declared": sorted(declared),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="resolve skills to install")
    parser.add_argument("--project")
    parser.add_argument("--cwd", help="current directory; product root is resolved from it")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    if args.project:
        project = Path(args.project)
    elif args.cwd:
        project = resolve_project(Path(args.cwd), root)
    else:
        project = Path(".")
    try:
        data = select(project, root)
    except ValueError as exc:
        print(f"skill_scope: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for name in data["install"]:
            print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
