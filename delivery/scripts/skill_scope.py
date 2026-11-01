#!/usr/bin/env python3
"""Resolve which skills a project should install.

Runtime skills are always installed. Scoped skills (registry `skills.scoped`)
are installed only when the project declares the matching capability in
`.kit/capabilities.yaml`.

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


def load_registry(root: Path) -> dict:
    path = root / "delivery" / "registry.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def declared_capabilities(project: Path) -> set[str]:
    path = project / ".kit" / "capabilities.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return set()
    if not isinstance(data, dict):
        return set()
    return {str(item) for item in data.get("include") or []}


def select(project: Path, root: Path = ROOT) -> dict:
    skills = (load_registry(root).get("skills") or {}) if isinstance(load_registry(root), dict) else {}
    runtime = [str(name) for name in skills.get("runtime") or []]
    scoped_map = skills.get("scoped") or {}
    declared = declared_capabilities(project)
    scoped: list[str] = []
    for capability, names in (scoped_map.items() if isinstance(scoped_map, dict) else []):
        if str(capability) not in declared:
            continue
        for name in names or []:
            name = str(name)
            if name not in scoped:
                scoped.append(name)
    return {
        "runtime": runtime,
        "scoped": scoped,
        "install": runtime + scoped,
        "declared": sorted(declared),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="resolve skills to install")
    parser.add_argument("--project", default=".")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = select(Path(args.project), Path(args.root))
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for name in data["install"]:
            print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
