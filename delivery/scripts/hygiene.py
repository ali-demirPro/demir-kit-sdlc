#!/usr/bin/env python3
"""Safe cleanup: old Xcode DerivedData plus index markers.

Guardrails are the point: every path must live under an allowlisted root, the
disk must have room, no build may be running, and one run may delete at most
20 GB. When a guard fails the tool deletes nothing and explains why.

    hygiene.py --dry-run        # default: report only
    hygiene.py --apply          # delete when every guard passes
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

KEEP_DAYS = 7
MAX_BYTES = 20 * 1024**3
MIN_FREE = 20 * 1024**3

DERIVED = Path.home() / "Library/Developer/Xcode/DerivedData"
INDEX_DIRS = (
    Path.home() / "Library/Developer/Xcode/DerivedData",
    Path.home() / "Library/Developer/CoreSimulator/Devices",
    Path.home() / ".local/share/opencode",
)


def _git_free() -> int:
    usage = shutil.disk_usage(Path.home())
    return usage.free


def _age_days(path: Path, now: float) -> float:
    try:
        return (now - path.stat().st_mtime) / 86400
    except OSError:
        return 0.0


def _size(path: Path) -> int:
    try:
        output = subprocess.check_output(["du", "-sk", str(path)], text=True, timeout=20)
        return int(output.split()[0]) * 1024
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0


def _busy() -> bool:
    try:
        output = subprocess.check_output(["ps", "-Ao", "comm"], text=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return any(name in output for name in ("xcodebuild", "swift-frontend"))


def group_of(name: str) -> str:
    return name.rsplit("-", 1)[0] if "-" in name else name


def plan(
    derived: Path = DERIVED,
    now: float | None = None,
    keep_days: int = KEEP_DAYS,
) -> dict:
    now = now or time.time()
    items: list[dict] = []

    groups: dict[str, list[Path]] = {}
    if Path(derived).is_dir():
        for item in Path(derived).iterdir():
            if item.is_dir():
                groups.setdefault(group_of(item.name), []).append(item)
    for paths in groups.values():
        newest = min(paths, key=lambda path: _age_days(path, now))
        for item in paths:
            if item == newest or _age_days(item, now) < keep_days:
                continue
            items.append(
                {"kind": "derived", "path": str(item), "bytes": _size(item),
                 "age_days": int(_age_days(item, now))}
            )

    total = sum(item["bytes"] for item in items)
    return {"items": items, "bytes": total}


def guards(
    result: dict, free: int | None = None, roots: tuple[Path, ...] | None = None
) -> list[str]:
    problems: list[str] = []
    roots = tuple(root.resolve() for root in (roots or (DERIVED,)))
    for item in result["items"]:
        path = Path(item["path"]).resolve()
        if not any(path.is_relative_to(root) for root in roots):
            problems.append(f"allowlist dışı: {path}")
    free = _git_free() if free is None else free
    if free < MIN_FREE:
        problems.append(f"boş disk {free // 1024**3} GB < {MIN_FREE // 1024**3} GB")
    if _busy():
        problems.append("çalışan derleme var")
    if result["bytes"] > MAX_BYTES:
        problems.append(f"tek çalıştırmada {result['bytes'] // 1024**3} GB > 20 GB")
    return problems


def apply(result: dict) -> dict:
    deleted = 0
    failed = 0
    for item in result["items"]:
        try:
            shutil.rmtree(Path(item["path"]))
            deleted += 1
        except OSError:
            failed += 1
            continue
    return {"deleted": deleted, "failed": failed}


def mark_indexes() -> int:
    count = 0
    for directory in INDEX_DIRS:
        if not directory.is_dir():
            continue
        marker = directory / ".metadata_never_index"
        if not marker.exists():
            try:
                marker.write_text("", encoding="utf-8")
                count += 1
            except OSError:
                continue
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="safe cleanup")
    parser.add_argument("--apply", action="store_true", help="delete (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="plan only (default)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--derived", default=str(DERIVED))
    args = parser.parse_args()

    result = plan(Path(args.derived))
    problems = guards(result)
    payload = {
        **result,
        "problems": problems,
        "applied": bool(args.apply and not problems),
    }
    if args.apply and not problems:
        payload.update(apply(result))
        payload["index_markers"] = mark_indexes()

    if args.json:
        print(__import__("json").dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not problems else 2
    print(f"{len(result['items'])} öğe · {result['bytes'] / 1e9:.1f} GB")
    for item in result["items"]:
        print(f"  - {item['kind']}: {item['path']} ({item['bytes'] / 1e9:.1f} GB, {item['age_days']} gün)")
    for problem in problems:
        print(f"  ! {problem}")
    print("silindi" if payload["applied"] else "silinmedi (dry-run veya guard)")
    return 0 if not problems else 2


if __name__ == "__main__":
    sys.exit(main())
