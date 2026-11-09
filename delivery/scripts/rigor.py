#!/usr/bin/env python3
"""Resolve the effective rigor level and its six knobs.

`process.rigor` is the single gate: it selects `minimal`, `standard` or `full`
from ``delivery/rigor.yaml`` and spreads six knobs. Live knobs may be overridden
explicitly in ``kit.config.yaml`` under ``process``; ``modes.review_mode`` is
stored for CCGS mapping only and never acts as a lever.

Usage:
  python3 delivery/scripts/rigor.py --check
  python3 delivery/scripts/rigor.py --check path/to/rigor.yaml
  python3 delivery/scripts/rigor.py --effective --project .
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from schema_lite import validate_schema  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RIGOR = ROOT / "delivery" / "rigor.yaml"
SCHEMA = ROOT / "delivery" / "schemas" / "rigor.schema.json"
CONFIG = "kit.config.yaml"

LEVELS = ("minimal", "standard", "full")
DEFAULT_LEVEL = "standard"

# Altı düğme, P3.yaml sırasıyla. review_mode dışındakiler canlı kaldıraçtır.
KNOBS = (
    "modes.workflow",
    "docs.density",
    "qa.level",
    "modes.story_granularity",
    "modes.review_mode",
    "team.size",
)
LIVE_KNOBS = (
    "modes.workflow",
    "docs.density",
    "qa.level",
    "modes.story_granularity",
    "team.size",
)
STORED_KNOBS = ("modes.review_mode",)

KNOB_VALUES = {
    "modes.workflow": ("minimal", "standard", "full"),
    "docs.density": ("terse", "balanced", "thorough"),
    "qa.level": ("minimal", "standard", "full"),
    "modes.story_granularity": ("coarse", "balanced", "fine"),
    "modes.review_mode": ("solo", "lean", "full"),
    "team.size": ("individual", "studio"),
}


class RigorError(ValueError):
    """Rigor configuration is missing, unknown or malformed."""


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RigorError(f"{path}: okunamadı — {exc}") from exc
    except yaml.YAMLError as exc:
        raise RigorError(f"{path}: YAML hatası — {exc}") from exc
    return data if isinstance(data, dict) else {}


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RigorError(f"{path}: JSON okunamadı — {exc}") from exc
    return data if isinstance(data, dict) else {}


def load_rigor(path: Path | None = None) -> dict:
    return load_yaml(Path(path) if path else RIGOR)


def validate(data, schema: dict | None = None) -> list[str]:
    """Schema errors for a rigor document; empty list means valid."""
    return validate_schema(data, schema or load_json(SCHEMA), "rigor")


def validate_file(path: Path | None = None) -> list[str]:
    return validate(load_rigor(path))


def _explicit(process: dict, name: str):
    """Explicit project value for a dotted knob, if any (nested or dotted)."""
    if name in process and not isinstance(process[name], dict):
        return process[name]
    node = process
    for part in name.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return None if isinstance(node, dict) else node


def _knob_value(name: str, value) -> str:
    allowed = KNOB_VALUES[name]
    text = str(value)
    if text not in allowed:
        raise RigorError(
            f"process.{name}: '{text}' geçersiz — beklenen: {', '.join(allowed)}"
        )
    return text


def load_effective(project: Path | str | None = None, rigor_path: Path | None = None) -> dict:
    """Effective level, its source and the six knobs with their sources."""
    root = Path(project) if project else ROOT
    data = load_rigor(rigor_path)
    errors = validate(data)
    if errors:
        raise RigorError("; ".join(errors))
    levels = data["levels"]

    config = load_yaml(root / CONFIG) if (root / CONFIG).is_file() else {}
    process = config.get("process") or {}
    if not isinstance(process, dict):
        raise RigorError(f"{CONFIG}: process mapping değil")

    raw = process.get("rigor")
    if raw is None:
        level = DEFAULT_LEVEL
        source = "default"
    else:
        level = str(raw)
        if level not in levels:
            raise RigorError(
                f"{CONFIG}: process.rigor '{level}' geçersiz — "
                f"beklenen: {', '.join(levels)}"
            )
        source = CONFIG

    knobs: dict[str, dict] = {}
    for name in KNOBS:
        derived = _knob_value(name, levels[level][name])
        explicit = _explicit(process, name)
        if name in STORED_KNOBS:
            knobs[name] = {
                "value": _knob_value(name, explicit) if explicit is not None else derived,
                "source": CONFIG if explicit is not None else f"rigor:{level}",
                "effect": "stored",
            }
        elif explicit is not None:
            knobs[name] = {
                "value": _knob_value(name, explicit),
                "source": CONFIG,
            }
        else:
            knobs[name] = {"value": derived, "source": f"rigor:{level}"}
    return {"level": level, "source": source, "knobs": knobs}


def reviewer_count(risk: str, data: dict | None = None) -> int:
    """Gating reviewer count is risk-only; rigor never changes it."""
    data = data if data is not None else load_rigor()
    gating = data.get("gating")
    if not isinstance(gating, dict) or not gating:
        raise RigorError("gating eksik")
    source = gating.get("reviewer_count_source")
    if source != "risk":
        raise RigorError(
            f"gating.reviewer_count_source '{source}' geçersiz — beklenen: risk"
        )
    counts = gating.get("reviewer_count") or {}
    if not isinstance(counts, dict) or risk not in counts:
        raise RigorError(f"bilinmeyen risk: {risk}")
    return int(counts[risk])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="demir-kit rigor resolver")
    parser.add_argument(
        "--check",
        nargs="?",
        const=str(RIGOR),
        metavar="PATH",
        help="rigor YAML'ını şemaya göre doğrula (varsayılan delivery/rigor.yaml)",
    )
    parser.add_argument("--effective", action="store_true", help="etkin matrisi yaz")
    parser.add_argument("--project", type=Path, default=ROOT, help="kit.config kökü")
    args = parser.parse_args(argv)

    if args.check is None and not args.effective:
        parser.error("--check veya --effective gerekli")

    if args.check is not None:
        try:
            errors = validate_file(Path(args.check))
        except RigorError as exc:
            print(f"[fail] {exc}", file=sys.stderr)
            return 1
        for message in errors:
            print(f"[fail] {message}", file=sys.stderr)
        if errors:
            return 1
        print(f"[ok] {args.check}")
        return 0

    try:
        effective = load_effective(args.project)
    except RigorError as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 1
    print(json.dumps(effective, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
