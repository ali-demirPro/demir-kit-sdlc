#!/usr/bin/env python3
"""Read-only verification of the project adaptation chain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import detect as detect_mod  # noqa: E402
import init as init_mod  # noqa: E402
import profiles as profiles_mod  # noqa: E402
import resolver  # noqa: E402
import standards as standards_mod  # noqa: E402


def known_capabilities() -> set[str]:
    path = ROOT / "delivery" / "capabilities" / "registry.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return set((data.get("capabilities") or {}).keys())


def known_packs() -> set[str]:
    path = ROOT / "delivery" / "packs"
    return {item.name for item in path.iterdir() if item.is_dir()}


def declared_surfaces(root: Path) -> list[dict]:
    """ecosystem.yaml'da bildirilen yüzeyler (fingerprint boşsa yedek)."""
    path = root / "ecosystem.yaml"
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []
    surfaces: list[dict] = []
    for product in (data.get("products") or {}).values():
        for name, spec in ((product or {}).get("surfaces") or {}).items():
            spec = spec or {}
            surfaces.append(
                {
                    "name": name,
                    "path": spec.get("path") or ".",
                    "platforms": spec.get("platforms") or [],
                    "stacks": spec.get("stacks") or [],
                }
            )
    return surfaces


def check_declarations(root: Path, known: set[str]) -> tuple[list[str], dict]:
    issues: list[str] = []
    for message in profiles_mod.validate_project(root, known, known_packs()):
        issues.append(f"profiles: {message}")
    declared_path = root / ".kit" / "capabilities.yaml"
    if declared_path.is_file():
        declared = resolver.load_declared(root, include_profiles=False)
        if declared.get("version") != 1:
            issues.append(".kit/capabilities.yaml: version 1 olmalı")
        for cap_id in (declared.get("include") or []) + (declared.get("exclude") or []):
            if cap_id not in known:
                issues.append(f"bilinmeyen capability: {cap_id}")
    return issues, {
        "profiles": profiles_mod.profile_names(root),
        "capabilities_file": declared_path.is_file(),
    }


def check_plan(plan: dict, known: set[str], declared: list[dict] | None = None) -> list[str]:
    issues: list[str] = []
    surfaces = plan["fingerprint"].get("surfaces") or []
    if not surfaces:
        surfaces = declared or []
    if not surfaces:
        issues.append("yüzey tespit edilmedi")
    for surface in surfaces:
        if "unknown" in (surface.get("platforms") or []):
            issues.append(f"bilinmeyen platform: {surface['name']}")
    names = plan.get("profiles") or []
    if not names:
        issues.append("profil önerilmedi")
    if plan.get("profile") not in names:
        issues.append("default profil listede değil")
    if not [name for name in names if name not in profiles_mod.OVERLAYS]:
        issues.append("base profil yok")
    for name in names:
        if not profiles_mod.load_profile(name):
            issues.append(f"profil yok: {name}")
    for cap_id in plan.get("capabilities") or []:
        if cap_id not in known:
            issues.append(f"bilinmeyen capability: {cap_id}")
    return issues


def verify_project(project: Path) -> dict:
    root = project.resolve()
    plan = init_mod.build(root)
    known = known_capabilities()
    detected = plan["fingerprint"].get("surfaces") or []
    declared = [] if detected else declared_surfaces(root)
    issues = check_plan(plan, known, declared)
    declaration_issues, configured = check_declarations(root, known)
    issues.extend(declaration_issues)
    standards = standards_mod.discover(root)
    if standards["agents"]["state"] == "stale":
        issues.append("standards: AGENTS.md bloğu bayat")
    return {
        "project": str(root),
        "ok": not issues,
        "issues": issues,
        "surfaces": [
            {
                "name": surface["name"],
                "path": surface["path"],
                "platforms": surface.get("platforms") or [],
                "stacks": surface.get("stacks") or [],
            }
            for surface in (detected or declared)
        ],
        "profiles": plan.get("profiles") or [],
        "default": plan.get("profile"),
        "configured": configured,
        "capabilities": plan.get("capabilities") or [],
        "tests": plan["fingerprint"].get("test_commands") or {},
        "standards": {
            "languages": standards["languages"],
            "package_managers": standards["package_managers"],
            "commands": standards["commands"],
            "agents": standards["agents"]["state"],
        },
    }


def render(report: dict) -> str:
    lines = [
        f"project: {report['project']}",
        "ok: " + ("evet" if report["ok"] else "HAYIR"),
        "surfaces: " + (
            ", ".join(
                f"{item['name']}[{','.join(item['platforms'])}] @ {item['path']}"
                for item in report["surfaces"]
            )
            or "-"
        ),
        "profiles: " + (", ".join(report["profiles"]) or "-"),
        "default: " + str(report["default"]),
        "configured: "
        + (
            ", ".join(report["configured"]["profiles"])
            if report["configured"]["profiles"]
            else "-"
        )
        + (", .kit" if report["configured"]["capabilities_file"] else ""),
        "capabilities: " + (", ".join(report["capabilities"]) or "-"),
        "commands: " + (
            ", ".join(f"{key}={value}" for key, value in report["tests"].items()) or "-"
        ),
        "standards: " + (
            ", ".join(report["standards"]["languages"]) or "-"
        ) + f" (AGENTS: {report['standards']['agents']})",
    ]
    for issue in report["issues"]:
        lines.append(f"  [fail] {issue}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="verify adaptation read-only")
    parser.add_argument(
        "--project",
        type=Path,
        action="append",
        default=[],
        help="project path; repeatable",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    projects = args.project or [Path.cwd()]
    reports = [verify_project(path) for path in projects]
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        for index, report in enumerate(reports):
            if index:
                print()
            print(render(report))
    return 0 if all(report["ok"] for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
