#!/usr/bin/env python3
"""Filter changed paths before risk-glob escalation."""

from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

import yaml


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


def main() -> int:
    parser = argparse.ArgumentParser(description="risk path filter")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    exclude = list(args.exclude)
    try:
        data = yaml.safe_load(args.registry.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        data = {}
    configured = ((data.get("risk") or {}).get("exclude") or [])
    if isinstance(configured, list):
        exclude.extend(str(item) for item in configured)

    for path in filter_paths(sys.stdin.read().splitlines(), exclude):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
