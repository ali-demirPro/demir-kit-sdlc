#!/usr/bin/env python3
"""Adopt demir-kit into a project with one command (dry-run default)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import init as init_mod  # noqa: E402
import standards as standards_mod  # noqa: E402
import vendor_sync  # noqa: E402
import verify as verify_mod  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def kit_root(project: Path, init_plan: dict | None = None) -> Path:
    config = project / "kit.config.yaml"
    if config.is_file():
        data = vendor_sync.load_config(project)
        root = (data.get("kit") or {}).get("root") or "demir-kit"
        return project / str(root)
    return project / "demir-kit"


def source_relation(project: Path) -> tuple[bool, bool, bool, bool]:
    source = ROOT.resolve()
    target = project.resolve()
    kit = kit_root(project).resolve()
    return (
        target == source,
        kit == source,
        source in kit.parents,
        source in target.parents,
    )


def empty_plan(root: Path, issues: list[str]) -> dict:
    return {
        "project": str(root),
        "kit_root": str(root / "demir-kit"),
        "profiles": [],
        "default": None,
        "capabilities": [],
        "surfaces": [],
        "files": [],
        "existing": [],
        "vendor": False,
        "standards": "missing_file",
        "verify": {"ok": False, "issues": issues},
        "issues": issues,
        "init_plan": {},
    }


def plan(project: Path, force: bool = False, vendor: bool = False) -> dict:
    root = project.resolve()
    if not root.is_dir():
        return empty_plan(root, ["proje dizini yok"])
    try:
        kit = kit_root(root)
        init_plan = init_mod.build(root)
    except (ValueError, yaml.YAMLError, OSError) as exc:
        return empty_plan(root, [f"kit.config.yaml okunamadı: {exc}"])
    target_is_source, vendored, inside_source, target_inside_source = source_relation(root)
    needs_vendor = vendor or not (kit / "delivery").is_dir()
    standards = standards_mod.discover(root)
    issues: list[str] = []
    if not init_plan["fingerprint"].get("surfaces"):
        issues.append("yüzey tespit edilmedi; adopt yazmadan durdu")
    if target_is_source:
        issues.append("kaynak ve hedef aynı; adopt kendi reposunda çalışmaz")
    elif inside_source or target_inside_source:
        issues.append("hedef kaynak kit'in içinde; adopt reddedildi")
    if needs_vendor and vendored:
        # Kit zaten ürünün içinde; vendor adımı atlanır, init/standards çalışır.
        needs_vendor = False
    preview = verify_mod.verify_project(root)
    return {
        "project": str(root),
        "kit_root": str(kit),
        "profiles": init_plan.get("profiles") or [],
        "default": init_plan.get("profile"),
        "capabilities": init_plan.get("capabilities") or [],
        "surfaces": [
            {
                "name": item["name"],
                "path": item["path"],
                "platforms": item.get("platforms") or [],
            }
            for item in init_plan["fingerprint"].get("surfaces") or []
        ],
        "files": list(init_plan["files"]),
        "existing": init_plan.get("existing") or [],
        "vendor": needs_vendor,
        "standards": standards["agents"]["state"],
        "verify": preview,
        "issues": issues,
        "init_plan": init_plan,
    }


def apply(project: Path, force: bool = False, vendor: bool = False) -> dict:
    data = plan(project, force=force, vendor=vendor)
    if data["issues"]:
        return {**data, "applied": False, "verify": None}

    root = Path(data["project"])
    applied = init_mod.apply_plan(data["init_plan"], force=force)
    steps = [
        {
            "step": "init",
            "written": applied["written"],
            "skipped": applied["skipped"],
        }
    ]

    if data["vendor"]:
        try:
            synced = vendor_sync.apply_plan(ROOT, root)
        except (ValueError, yaml.YAMLError, OSError) as exc:
            data["issues"].append(f"vendor sync başarısız: {exc}")
            steps.append({"step": "vendor", "actions": [], "clean": False})
        else:
            steps.append(
                {
                    "step": "vendor",
                    "actions": synced.get("actions") or [],
                    "clean": synced.get("clean", True),
                }
            )
            if not synced.get("clean", True):
                data["issues"].append("vendor sync yakınsamadı")
    else:
        steps.append({"step": "vendor", "actions": ["mevcut kit korundu"]})

    injected = standards_mod.inject(root, apply=True)
    steps.append(
        {
            "step": "standards",
            "changed": injected["changed"],
            "applied": injected["applied"],
        }
    )

    report = verify_mod.verify_project(root)
    steps.append({"step": "verify", "ok": report["ok"], "issues": report["issues"]})
    return {
        **data,
        "applied": True,
        "steps": steps,
        "verify": report,
    }


def render(data: dict) -> str:
    lines = [
        f"project: {data['project']}",
        f"kit: {data['kit_root']}",
        "profiles: " + (", ".join(data["profiles"]) or "-"),
        "default: " + str(data["default"]),
        "capabilities: " + (", ".join(data["capabilities"]) or "-"),
        "files: " + ", ".join(data["files"]),
        "vendor: " + ("gerekli" if data["vendor"] else "mevcut"),
        "standards: " + data["standards"],
        "surfaces: " + (
            ", ".join(
                f"{item['name']}[{','.join(item['platforms'])}] @ {item['path']}"
                for item in data.get("surfaces") or []
            )
            or "-"
        ),
    ]
    for issue in data["issues"]:
        lines.append(f"  [fail] {issue}")
    if data.get("applied"):
        for step in data.get("steps") or []:
            name = step["step"]
            if name == "init":
                lines.append(
                    "init: yazılan "
                    + (", ".join(step["written"]) or "-")
                    + " · atlanan "
                    + (", ".join(step["skipped"]) or "-")
                )
            elif name == "vendor":
                lines.append(
                    "vendor: "
                    + (", ".join(step["actions"]) or "-")
                    + ("" if step.get("clean", True) else " · yakınsamadı")
                )
            elif name == "standards":
                lines.append(
                    "standards: " + ("güncellendi" if step["changed"] else "değişmedi")
                )
            elif name == "verify":
                lines.append("verify: " + ("ok" if step["ok"] else "HATA"))
                for issue in step["issues"]:
                    lines.append(f"  [fail] {issue}")
    else:
        preview = data.get("verify") or {}
        lines.append("verify (önizleme): " + ("ok" if preview.get("ok") else "HATA"))
        for issue in preview.get("issues") or []:
            lines.append(f"  [fail] {issue}")
        lines.append("dry-run: --apply ile yazılır" if not data["issues"] else "yazılmadı")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="adopt demir-kit into a project")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--vendor", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        if args.apply:
            data = apply(args.project, force=args.force, vendor=args.vendor)
        else:
            data = plan(args.project, force=args.force, vendor=args.vendor)
    except (ValueError, yaml.YAMLError, OSError) as exc:
        sys.exit(f"adopt: {exc}")
    data.pop("init_plan", None)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render(data))

    if data["issues"]:
        return 1
    if data.get("applied") and data.get("verify") and not data["verify"]["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
