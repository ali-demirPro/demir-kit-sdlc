#!/usr/bin/env python3
"""Heavy-work budget from `ecosystem.yaml`.

`resources.heavy_workers` caps how many build/test workers run at once. Missing
or non-positive values mean "no cap", so products without the key keep their
previous behaviour.
"""

from __future__ import annotations

from pathlib import Path

import yaml

KEYS = ("heavy_workers", "simulators")


def load(project: Path) -> dict:
    limits = {key: None for key in KEYS}
    path = Path(project) / "ecosystem.yaml"
    if not path.is_file():
        return limits
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return limits
    if not isinstance(data, dict):
        return limits
    values = data.get("resources")
    if not isinstance(values, dict):
        return limits
    for key in KEYS:
        value = values.get(key)
        if isinstance(value, int) and value > 0:
            limits[key] = value
    return limits
