#!/usr/bin/env python3
"""Filter changed paths before risk-glob escalation."""

from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

import yaml


def _matches(path: str, pattern: str) -> bool:
    if fnmatch.fnmatch(path, pattern):
        return True
    # fnmatch's `**/x` needs a slash; registry patterns must also match root x.
    if pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:]):
        return True
    return False


def risk_for_paths(paths: list[str], registry: dict) -> str:
    risk = registry.get("risk") if isinstance(registry, dict) else {}
    escalate = (risk or {}).get("auto_escalate") or {}
    critical = escalate.get("critical") or []
    high = escalate.get("high") or []
    level = "none"
    for path in paths:
        if any(_matches(path, pattern) for pattern in critical):
            return "critical"
        if any(_matches(path, pattern) for pattern in high):
            level = "high"
    return level


def filter_paths(paths: list[str], exclude: list[str]) -> list[str]:
    kept: list[str] = []
    for raw in paths:
        path = raw.strip()
        if not path:
            continue
        if any(fnmatch.fnmatch(path, pattern) for pattern in exclude):
            continue
        kept.append(path)
    return kept


def load_overlay(root: Path) -> dict:
    """Proje risk overlay (.kit/risk.yaml); vendor_sync'den etkilenmez."""
    path = root / ".kit" / "risk.yaml"
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def merge_risk(registry: dict, overlay: dict) -> dict:
    """Kit risk glob'larına proje overlay'ini ekle (yalnız ekleme sınıfı)."""
    if not overlay:
        return registry
    merged = dict(registry) if isinstance(registry, dict) else {}
    risk = dict(merged.get("risk") or {})
    escalate = dict(risk.get("auto_escalate") or {})
    over_escalate = overlay.get("auto_escalate") or {}
    for level in ("high", "critical"):
        base = [str(item) for item in (escalate.get(level) or [])]
        extra = [str(item) for item in (over_escalate.get(level) or [])]
        combined = base + [item for item in extra if item not in base]
        if combined:
            escalate[level] = combined
    risk["auto_escalate"] = escalate
    merged["risk"] = risk
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="risk path filter")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--project", type=Path, help="ürün kökü (.kit/risk.yaml overlay)")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--risk", action="store_true")
    args = parser.parse_args()

    exclude = list(args.exclude)
    try:
        data = yaml.safe_load(args.registry.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        data = {}
    if args.project:
        data = merge_risk(data, load_overlay(args.project))
    configured = ((data.get("risk") or {}).get("exclude") or [])
    if isinstance(configured, list):
        exclude.extend(str(item) for item in configured)

    paths = filter_paths(sys.stdin.read().splitlines(), exclude)
    if args.risk:
        print(risk_for_paths(paths, data))
        return 0
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
