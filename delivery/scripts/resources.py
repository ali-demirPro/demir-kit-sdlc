#!/usr/bin/env python3
"""Machine budget guard: measure the box, report it, refuse when it is saturated.

A 16 GB laptop with two simulators, three heavy workers and an Electron shell
freezes; the agents then look "slow". This guard turns that into a signal:

  exit 0 healthy · 2 degraded (warn) · 3 blocked (do not start heavy work)

Thresholds live in ``.kit/resources.yaml`` (optional); the defaults below are
the documented baseline.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DIR = ".kit"
NAME = "resources.jsonl"
CONFIG = "resources.yaml"

DEFAULTS = {
    "free_ram_warn_mb": 1500,
    "free_ram_block_mb": 800,
    "compressor_warn_mb": 1500,
    "compressor_block_mb": 3000,
    "load_warn_factor": 1.5,
    "load_block_factor": 2.5,
    "max_simulators": 1,
    "max_heavy_workers": 2,
}

HEAVY = ("xcodebuild", "swift-frontend", "swift-build", "ibtool", "actool")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def project_root(fallback: Path | None = None) -> Path:
    override = os.environ.get("DEMIR_KIT_RESOURCES_ROOT")
    if override:
        return Path(override)
    current = Path.cwd()
    return current if (current / "kit.config.yaml").is_file() else (fallback or current)


def load_limits(project: Path) -> dict:
    limits = dict(DEFAULTS)
    path = Path(project) / DIR / CONFIG
    if not path.is_file():
        return limits
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return limits
    values = data.get("limits") if isinstance(data, dict) else None
    if isinstance(values, dict):
        for key, value in values.items():
            if key in limits and isinstance(value, (int, float)):
                limits[key] = value
    return limits


def _vm_stat() -> tuple[float, float]:
    """(free+speculative MB, compressor MB) from vm_stat."""
    try:
        output = subprocess.check_output(["vm_stat"], text=True)
    except (OSError, subprocess.CalledProcessError):
        return (0.0, 0.0)
    page = 4096
    for line in output.splitlines()[:2]:
        if "page size of" in line:
            digits = "".join(ch for ch in line if ch.isdigit())
            if digits:
                page = int(digits)
    values = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits:
            values[key.strip()] = int(digits)
    free = values.get("Pages free", 0) + values.get("Pages speculative", 0)
    compressor = values.get("Pages occupied by compressor", 0)
    return (free * page / 1024 / 1024, compressor * page / 1024 / 1024)


def _booted_simulators() -> int:
    try:
        output = subprocess.check_output(
            ["xcrun", "simctl", "list", "devices", "booted"], text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return 0
    return sum(1 for line in output.splitlines() if "(Booted)" in line)


def _heavy_workers() -> int:
    try:
        output = subprocess.check_output(["ps", "-Ao", "comm"], text=True)
    except (OSError, subprocess.CalledProcessError):
        return 0
    count = 0
    for line in output.splitlines():
        if any(name in line for name in HEAVY):
            count += 1
    return count


def measure() -> dict:
    free_mb, compressor_mb = _vm_stat()
    try:
        load1 = float(os.getloadavg()[0])
    except (OSError, AttributeError):
        load1 = 0.0
    return {
        "free_ram_mb": round(free_mb),
        "compressor_mb": round(compressor_mb),
        "load1": round(load1, 2),
        "cpus": os.cpu_count() or 1,
        "booted_simulators": _booted_simulators(),
        "heavy_workers": _heavy_workers(),
    }


def evaluate(metrics: dict, limits: dict | None = None) -> dict:
    limits = dict(limits or DEFAULTS)
    reasons: list[str] = []
    state = 0

    def block(reason: str) -> None:
        nonlocal state
        state = 3
        reasons.append(reason)

    def warn(reason: str) -> None:
        nonlocal state
        state = max(state, 2)
        reasons.append(reason)

    free = metrics.get("free_ram_mb") or 0
    if free < limits["free_ram_block_mb"]:
        block(f"RAM neredeyse dolu ({int(free)} MB boş) — worker başlatma")
    elif free < limits["free_ram_warn_mb"]:
        warn(f"RAM daralıyor ({int(free)} MB boş)")

    compressor = metrics.get("compressor_mb") or 0
    if compressor > limits["compressor_block_mb"]:
        block(f"bellek sıkıştırma {int(compressor)} MB — önce boşalt")
    elif compressor > limits["compressor_warn_mb"]:
        warn(f"bellek sıkıştırma {int(compressor)} MB")

    cpus = max(1, int(metrics.get("cpus") or 1))
    factor = float(metrics.get("load1") or 0) / cpus
    if factor > limits["load_block_factor"]:
        block(f"yük {factor:.1f}x çekirdek — makine dolu")
    elif factor > limits["load_warn_factor"]:
        warn(f"yük {factor:.1f}x çekirdek")

    sims = int(metrics.get("booted_simulators") or 0)
    if sims > int(limits["max_simulators"]):
        block(f"{sims} simülatör açık (bütçe {int(limits['max_simulators'])})")

    heavy = int(metrics.get("heavy_workers") or 0)
    if heavy > int(limits["max_heavy_workers"]):
        block(f"{heavy} ağır iş koşuyor (bütçe {int(limits['max_heavy_workers'])})")

    return {"state": state, "reasons": reasons, "metrics": metrics, "limits": limits}


def log_path(project: Path) -> Path:
    return Path(project) / DIR / NAME


def record(project: Path, result: dict) -> dict:
    path = log_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": now(), "state": result["state"], "reasons": result["reasons"],
           "metrics": result["metrics"], "limits": result["limits"]}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def check(project: Path | None = None, log: bool = True) -> dict:
    project = project or project_root()
    result = evaluate(measure(), load_limits(project))
    if log:
        record(project, result)
    return result


def blocked(project: Path | None = None) -> str | None:
    """Reason string when the machine is blocked, else None."""
    if os.environ.get("DEMIR_KIT_RESOURCES") == "off":
        return None
    result = check(project)
    return "; ".join(result["reasons"]) if result["state"] == 3 else None


def report(project: Path | None = None) -> str:
    result = check(project)
    metrics = result["metrics"]
    head = {
        0: "Makine hazır",
        2: "Makine zorlanıyor",
        3: "Makine bloke — ağır iş başlatma",
    }[result["state"]]
    lines = [
        head,
        f"RAM boş {int(metrics['free_ram_mb'])} MB · compressor "
        f"{int(metrics['compressor_mb'])} MB · load {metrics['load1']} "
        f"({metrics['cpus']} çekirdek) · simülatör "
        f"{metrics['booted_simulators']} · ağır iş {metrics['heavy_workers']}",
    ]
    lines += [f"- {reason}" for reason in result["reasons"]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="machine budget guard")
    parser.add_argument("--check", action="store_true", help="exit 0/2/3")
    parser.add_argument("--report", action="store_true", help="human summary")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    parser.add_argument("--metrics", help="JSON metrics override (tests)")
    parser.add_argument("--project", default=None)
    args = parser.parse_args()

    project = Path(args.project) if args.project else project_root()
    if args.metrics:
        result = evaluate(json.loads(args.metrics), load_limits(project))
    else:
        result = check(project, log=not args.no_log)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.report:
        print(report(project))
    elif result["reasons"]:
        print("; ".join(result["reasons"]))
    return result["state"]


if __name__ == "__main__":
    sys.exit(main())
