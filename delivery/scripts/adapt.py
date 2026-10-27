#!/usr/bin/env python3
"""Adapt a project's capability declaration and show the impact."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import resolver  # noqa: E402


def build_declared(current: dict, add: list[str], remove: list[str]) -> dict:
    include = set(current.get("include") or [])
    exclude = set(current.get("exclude") or [])
    for cap_id in add:
        include.add(cap_id)
        exclude.discard(cap_id)
    for cap_id in remove:
        exclude.add(cap_id)
        include.discard(cap_id)
    return {
        "version": 1,
        "include": sorted(include),
        "exclude": sorted(exclude),
    }


def unknown_capabilities(declared: dict, registry: dict) -> list[str]:
    available = set((registry.get("capabilities") or {}).keys())
    return sorted(
        {
            cap_id
            for cap_id in (declared.get("include") or [])
            + (declared.get("exclude") or [])
            if cap_id not in available
        }
    )


def variant_keys(items: list[dict]) -> set[tuple[str, str]]:
    return {(item["role"], item["capability"]) for item in items}


def gap_keys(items: list[dict]) -> set[tuple[str, str]]:
    return {(item["role"], item["capability"]) for item in items}


def diff(before: dict, after: dict) -> dict:
    return {
        "capabilities_added": sorted(set(after["capabilities"]) - set(before["capabilities"])),
        "capabilities_removed": sorted(set(before["capabilities"]) - set(after["capabilities"])),
        "roles_added": sorted(set(after["active_roles"]) - set(before["active_roles"])),
        "roles_removed": sorted(set(before["active_roles"]) - set(after["active_roles"])),
        "variants_added": sorted(
            variant_keys(after["active_variants"]) - variant_keys(before["active_variants"])
        ),
        "variants_removed": sorted(
            variant_keys(before["active_variants"]) - variant_keys(after["active_variants"])
        ),
        "gaps_added": sorted(
            gap_keys(after["variant_gaps"]) - gap_keys(before["variant_gaps"])
        ),
        "gaps_removed": sorted(
            gap_keys(before["variant_gaps"]) - gap_keys(after["variant_gaps"])
        ),
        "risk_floor_before": before["risk_floor"],
        "risk_floor_after": after["risk_floor"],
        "docs_before": len(before["docs"]),
        "docs_after": len(after["docs"]),
    }


def write_declared(project: Path, declared: dict) -> Path:
    path = resolver.declared_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "include": declared.get("include") or [],
        "exclude": declared.get("exclude") or [],
        "source": "adapt.py",
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    text = "# Project capability declaration — managed by delivery/scripts/adapt.py.\n"
    text += yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    path.write_text(text, encoding="utf-8")
    return path


def load_project(project: Path) -> tuple[dict, list[dict]]:
    ecosystem = resolver.load_yaml(project / "ecosystem.yaml")
    return ecosystem, resolver.project_signals(ecosystem)


def render(data: dict) -> str:
    delta = data["diff"]
    lines = [
        f"project: {data['project']}",
        f"path: {data['path']}",
        f"capabilities: {', '.join(data['before']['capabilities']) or '-'} -> "
        f"{', '.join(data['after']['capabilities']) or '-'}",
    ]
    for key in (
        "capabilities_added",
        "capabilities_removed",
        "roles_added",
        "roles_removed",
        "gaps_added",
        "gaps_removed",
    ):
        values = delta[key]
        if values:
            lines.append(f"{key}: " + ", ".join(
                " / ".join(item) if isinstance(item, tuple) else str(item)
                for item in values
            ))
    if delta["variants_added"]:
        lines.append("variants_added: " + ", ".join(f"{r}/{c}" for r, c in delta["variants_added"]))
    if delta["variants_removed"]:
        lines.append("variants_removed: " + ", ".join(f"{r}/{c}" for r, c in delta["variants_removed"]))
    lines.append(f"risk: {delta['risk_floor_before']} -> {delta['risk_floor_after']}")
    lines.append(f"docs: {delta['docs_before']} -> {delta['docs_after']}")
    if data.get("applied"):
        lines.append(f"applied: {data['applied']}")
    else:
        lines.append("dry-run: --apply ile yazılır")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="adapt project capabilities")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--path", default="full_product")
    parser.add_argument("--add", action="append", default=[])
    parser.add_argument("--remove", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
    capability_registry = resolver.load_capabilities()
    matrix = resolver.load_matrix()
    variants = resolver.load_agent_variants()
    ecosystem, signals = load_project(project)
    current_raw = resolver.load_declared(project, include_profiles=False)
    current = resolver.load_declared(project)
    target_raw = build_declared(current_raw, args.add, args.remove)
    profile_caps = set(current["include"]) - set(current_raw["include"])
    target = {
        "version": 1,
        "include": sorted(set(target_raw["include"]) | profile_caps),
        "exclude": target_raw["exclude"],
    }

    unknown = unknown_capabilities(target, capability_registry)
    if unknown:
        sys.exit(f"adapt: bilinmeyen capability — {', '.join(unknown)}")

    before = resolver.resolve(
        capability_registry, matrix, variants, args.path, signals,
        declared=current,
    )
    after = resolver.resolve(
        capability_registry, matrix, variants, args.path, signals,
        declared=target,
    )
    data = {
        "project": str(project),
        "path": args.path,
        "declared": target,
        "before": before,
        "after": after,
        "diff": diff(before, after),
    }
    if args.apply:
        # Profil kaynaklı capability'ler dosyaya yazılmaz; kompozisyon
        # resolver'da kalır. Açık include/exclude proje kararıdır.
        path = write_declared(project, target_raw)
        data["applied"] = str(path)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
