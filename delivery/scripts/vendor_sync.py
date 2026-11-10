#!/usr/bin/env python3
"""Sync a product repo's vendored demir-kit to the source kit version.

The transfer path is ``--apply`` (copy + seal). ``--check`` verifies the
vendored copy against its own ``KIT-MANIFEST.json`` without a source checkout;
``--check-live`` keeps the older source-tree comparison for callers that do
have the kit checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

import schema_lite

ROOT = Path(__file__).resolve().parents[2]
ALLOW_DIRS = ("delivery", "skills")
ALLOW_FILES = ("install.sh", "VERSION", "CHANGELOG.md", "README.md", ".gitignore")
MANIFEST_NAME = "KIT-MANIFEST.json"
MANIFEST_SCHEMA = ROOT / "delivery" / "schemas" / "kit_manifest.schema.json"
GENERATOR_VERSION = 1
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


def _allowed_relative(path: str) -> bool:
    """True when ``path`` belongs to the vendor_sync allowlist."""
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return False
    parts = candidate.parts
    if not parts:
        return False
    if path in ALLOW_FILES:
        return True
    top = parts[0]
    if top not in ALLOW_DIRS:
        return False
    if any(part == "__pycache__" for part in parts) or path.endswith(".pyc"):
        return False
    if top == "delivery" and len(parts) > 1 and parts[1] == "tests":
        return False
    return True


def snapshot(root: Path) -> dict[str, dict]:
    """Every allowlisted file with its digest and byte length."""
    snapshot: dict[str, dict] = {}
    for path in file_map(root):
        full = root / path
        data = full.read_bytes()
        snapshot[path] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    return snapshot


def source_commit(root: Path) -> str:
    """Kit source commit when ``root`` is its own git checkout, else 'unknown'."""
    override = os.environ.get("DEMIR_KIT_SOURCE_COMMIT")
    if override:
        return override.strip()
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    try:
        toplevel = git("rev-parse", "--show-toplevel")
        commit = git("rev-parse", "HEAD")
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if not toplevel or not commit:
        return "unknown"
    try:
        inside = Path(toplevel).resolve() == Path(root).resolve()
    except OSError:
        return "unknown"
    return commit if inside else "unknown"


def manifest_payload(root: Path, commit: str | None = None) -> dict:
    """Deterministic manifest payload for one kit tree."""
    version_path = root / "VERSION"
    if not version_path.is_file():
        raise ValueError("kaynak VERSION yok")
    files = [
        {"path": path, "sha256": item["sha256"], "bytes": item["bytes"]}
        for path, item in sorted(snapshot(root).items())
    ]
    if not files:
        raise ValueError("manifest için allowlist dosyası yok")
    return {
        "demir_kit_version": "2",
        "schema_version": 1,
        "version": version_path.read_text(encoding="utf-8").strip(),
        "source_commit": commit or source_commit(root),
        "generator_version": GENERATOR_VERSION,
        "files": files,
    }


def seal(root: Path, commit: str | None = None) -> dict:
    """Write KIT-MANIFEST.json; the same tree produces the same bytes."""
    payload = manifest_payload(root, commit=commit)
    path = root / MANIFEST_NAME
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def validate_manifest(data: dict) -> list[str]:
    """Schema and scope checks for a manifest payload."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["manifest kök mapping değil"]
    try:
        schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"kit manifest şeması okunamadı: {exc}"]
    errors += schema_lite.validate_schema(data, schema)
    files = data.get("files") or []
    if isinstance(files, list):
        paths = [item.get("path") for item in files if isinstance(item, dict)]
        duplicates = sorted(
            {str(path) for path in paths if paths.count(path) > 1}
        )
        for path in duplicates:
            errors.append(f"tekrarlı yol: {path}")
        if paths != sorted(str(path) for path in paths):
            errors.append("dosya yolları sıralı değil")
        for path in paths:
            if not isinstance(path, str) or not _allowed_relative(path):
                errors.append(f"allowlist dışı yol: {path}")
    return errors


def load_manifest(root: Path) -> tuple[dict | None, list[str]]:
    path = root / MANIFEST_NAME
    if not path.is_file():
        return None, [f"{MANIFEST_NAME} yok"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"{MANIFEST_NAME} okunamadı: {exc}"]
    return data, validate_manifest(data)


def check_manifest(root: Path) -> dict:
    """Offline integrity check: manifest plus local files, no source checkout."""
    data, errors = load_manifest(root)
    result = {
        "manifest": str(root / MANIFEST_NAME),
        "files": len((data or {}).get("files") or []) if isinstance(data, dict) else 0,
        "missing": [],
        "extra": [],
        "changed": [],
        "errors": errors,
    }
    if data is None:
        return {
            **result,
            "status": "not_run",
            "reason": (
                f"{MANIFEST_NAME} yok — 'vendor_sync.py --seal' ile üret"
            ),
        }
    if errors:
        return {**result, "status": "invalid", "reason": "manifest geçersiz"}
    expected = {
        str(item.get("path")): item
        for item in data.get("files") or []
        if isinstance(item, dict)
    }
    actual = snapshot(root)
    result["missing"] = sorted(set(expected) - set(actual))
    result["extra"] = sorted(set(actual) - set(expected))
    changed = []
    for path in sorted(set(expected) & set(actual)):
        expected_bytes = int(expected[path].get("bytes", -1))
        if (
            str(expected[path].get("sha256")) != actual[path]["sha256"]
            or expected_bytes != actual[path]["bytes"]
        ):
            changed.append(
                {
                    "path": path,
                    "expected": str(expected[path].get("sha256")),
                    "actual": actual[path]["sha256"],
                    "expected_bytes": expected_bytes,
                    "actual_bytes": actual[path]["bytes"],
                }
            )
    result["changed"] = changed
    clean = not (result["missing"] or result["extra"] or changed)
    result["status"] = "pass" if clean else "fail"
    result["reason"] = "manifest ve yerel dosyalar aynı" if clean else "fark var"
    return result


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
            if ".drafts" in path.parts:  # skill öneri taslağı ürüne gitmez
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
    seal(kit, commit=source_commit(source))
    actions.append(f"seal {MANIFEST_NAME}")
    after = build_plan(source, project)
    return {**after, "actions": actions}


def resolve_kit(args, source: Path, project: Path) -> Path:
    """Kit root for seal/check: explicit flag, product config, else the tree."""
    if args.kit:
        return args.kit.resolve()
    config = project / "kit.config.yaml"
    if config.is_file():
        return target_kit(project)
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description="sync vendored demir-kit")
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--target", type=Path, default=Path.cwd())
    parser.add_argument("--kit", type=Path, help="seal/check için kit kökü")
    parser.add_argument("--check", action="store_true", help="offline manifest denetimi")
    parser.add_argument(
        "--check-live",
        action="store_true",
        help="kaynak kit ile hedef kopyayı canlı karşılaştır",
    )
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    project = args.target.resolve()
    kit = resolve_kit(args, source, project)

    if args.check_live:
        try:
            plan = build_plan(source, project)
        except (ValueError, OSError) as exc:
            sys.exit(f"vendor_sync: {exc}")
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(
                f"source: {plan['source_version']} · target: "
                f"{plan['target_version'] or 'yok'}"
            )
            for key in ("changed", "extra", "legacy"):
                for value in plan.get(key) or []:
                    print(f"{key}: {value}")
        return 0 if plan["clean"] else 1

    if args.seal:
        try:
            payload = seal(kit)
        except (ValueError, OSError) as exc:
            sys.exit(f"vendor_sync: {exc}")
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"sealed: {len(payload['files'])} dosya · version "
                f"{payload['version']} · commit {payload['source_commit'][:7]}"
            )
        return 0

    if args.check:
        result = check_manifest(kit)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"manifest: {result['manifest']}")
            print(f"status: {result['status']} — {result.get('reason', '')}")
            for key in ("missing", "extra"):
                for value in result.get(key) or []:
                    print(f"{key}: {value}")
            for item in result.get("changed") or []:
                print(
                    f"changed: {item['path']} — beklenen "
                    f"{item['expected']} gerçek {item['actual']}"
                )
            for value in result.get("errors") or []:
                print(f"error: {value}")
        return 0 if result["status"] == "pass" else (1 if result["status"] == "fail" else 2)

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
