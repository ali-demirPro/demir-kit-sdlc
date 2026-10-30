#!/usr/bin/env python3
"""Sync a product repo's vendored demir-kit to the source kit version."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ALLOW_DIRS = ("delivery", "skills")
ALLOW_FILES = ("install.sh", "VERSION", "CHANGELOG.md", "README.md", ".gitignore")
LEGACY = (
    "references",
    "orchestration",
    "profiles",
    "tools",
    "examples",
    "templates",
    "discovery",
    "ARCHITECTURE.md",
    "skills-lock.json",
)


def load_config(project: Path) -> dict:
    path = project / "kit.config.yaml"
    if not path.is_file():
        raise ValueError("kit.config.yaml yok")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("kit.config.yaml kök mapping değil")
    return data


def target_kit(project: Path) -> Path:
    config = load_config(project)
    root = (config.get("kit") or {}).get("root")
    if not root:
        raise ValueError("kit.config.yaml kit.root yok")
    return project / str(root)


def source_version(source: Path) -> str:
    path = source / "VERSION"
    if not path.is_file():
        raise ValueError("kaynak VERSION yok")
    return path.read_text(encoding="utf-8").strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_map(root: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in ALLOW_DIRS:
        base = root / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if name == "delivery" and "tests" in path.relative_to(base).parts[:1]:
                continue
            mapping[str(path.relative_to(root))] = digest(path)
    for name in ALLOW_FILES:
        path = root / name
        if path.is_file():
            mapping[name] = digest(path)
    return mapping


def build_plan(source: Path, project: Path) -> dict:
    kit = target_kit(project)
    target_ver = (kit / "VERSION").read_text(encoding="utf-8").strip() if (kit / "VERSION").is_file() else None
    src_files = file_map(source)
    dst_files = file_map(kit) if kit.is_dir() else {}
    changed = sorted(
        path for path, value in src_files.items() if dst_files.get(path) != value
    )
    extra = sorted(path for path in dst_files if path not in src_files)
    legacy = sorted(path for path in LEGACY if (kit / path).exists())
    config = load_config(project)
    kit_config = config.get("kit") or {}
    config_drift = {
        "version": str(kit_config.get("version")) != source_version(source),
        "protocol": str(kit_config.get("protocol")) != "2",
    }
    return {
        "source": str(source),
        "project": str(project),
        "kit_root": str(kit),
        "source_version": source_version(source),
        "target_version": target_ver,
        "changed": changed,
        "extra": extra,
        "legacy": legacy,
        "config": config_drift,
        "clean": not (changed or extra or legacy or any(config_drift.values())),
    }


def copy_allowlist(source: Path, kit: Path) -> list[str]:
    actions: list[str] = []
    for name in ALLOW_DIRS:
        src = source / name
        dst = kit / name
        if not src.is_dir():
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(
            src,
            dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests"),
        )
        actions.append(f"copy {name}/")
    for name in ALLOW_FILES:
        src = source / name
        if src.is_file():
            shutil.copy2(src, kit / name)
            actions.append(f"copy {name}")
    return actions


def update_config(project: Path, version: str) -> None:
    path = project / "kit.config.yaml"
    lines = path.read_text(encoding="utf-8").splitlines()
    in_kit = False
    updated = {"version": False, "protocol": False}
    result = []
    for line in lines:
        if re.match(r"^kit:\s*$", line):
            in_kit = True
            result.append(line)
            continue
        if in_kit and re.match(r"^\S", line):
            in_kit = False
        if in_kit:
            match = re.match(r"^(\s*)version:\s*.*$", line)
            if match and not updated["version"]:
                line = f'{match.group(1)}version: "{version}"'
                updated["version"] = True
            match = re.match(r"^(\s*)protocol:\s*.*$", line)
            if match and not updated["protocol"]:
                line = f'{match.group(1)}protocol: "2"'
                updated["protocol"] = True
        result.append(line)
    path.write_text("\n".join(result) + "\n", encoding="utf-8")


def assert_safe_target(source: Path, kit: Path) -> None:
    source = source.resolve()
    kit = kit.resolve()
    if source == kit or source in kit.parents or kit in source.parents:
        raise ValueError("source and target kit overlap; refusing to sync")
    if (kit / ".git").exists():
        raise ValueError(
            "hedef kit dizini bir git deposu (submodule/clone); vendor_sync "
            "yerine 'git submodule update --remote demir-kit' kullanın"
        )


def apply_plan(source: Path, project: Path) -> dict:
    plan = build_plan(source, project)
    kit = Path(plan["kit_root"])
    assert_safe_target(source, kit)
    kit.mkdir(parents=True, exist_ok=True)
    actions = copy_allowlist(source, kit)
    for name in plan["legacy"]:
        path = kit / name
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        actions.append(f"remove legacy {name}")
    update_config(project, plan["source_version"])
    actions.append("update kit.config version/protocol")
    after = build_plan(source, project)
    return {**after, "actions": actions}


def main() -> int:
    parser = argparse.ArgumentParser(description="sync vendored demir-kit")
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--target", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    project = args.target.resolve()
    try:
        if args.apply:
            plan = apply_plan(source, project)
        else:
            plan = build_plan(source, project)
    except (ValueError, OSError) as exc:
        sys.exit(f"vendor_sync: {exc}")

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(f"source: {plan['source_version']} · target: {plan['target_version'] or 'yok'}")
        for key in ("changed", "extra", "legacy"):
            values = plan.get(key) or []
            if values:
                print(f"{key}:")
                for value in values:
                    print(f"  - {value}")
        drift = [key for key, value in (plan.get("config") or {}).items() if value]
        if drift:
            print("config drift: " + ", ".join(drift))
        if plan.get("actions"):
            print("actions:")
            for action in plan["actions"]:
                print(f"  - {action}")
        if plan["clean"]:
            print("clean")

    if args.apply and not plan["clean"]:
        print("vendor_sync: apply did not converge", file=sys.stderr)
        return 1
    if args.check and not plan["clean"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
