#!/usr/bin/env python3
"""Release settled Orca worker terminals of a run.

Usage:
  python3 delivery/scripts/worker_cleanup.py --run run_abc        # plan
  python3 delivery/scripts/worker_cleanup.py --run run_abc --apply
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import usage as usage_mod  # noqa: E402

SETTLED = {"succeeded", "failed", "stopped"}


def orca(args: list[str]) -> dict:
    try:
        result = subprocess.run(
            ["orca", *args], capture_output=True, text=True, timeout=120
        )
    except FileNotFoundError:
        return {}
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict) or not payload.get("ok"):
        return {}
    data = payload.get("result")
    return data if isinstance(data, dict) else {}


def workers(run_id: str) -> list[dict]:
    return usage_mod.run_workers(run_id)


def skip_reason(worker: dict) -> str | None:
    state = str(worker.get("workerState") or "")
    terminal = str(worker.get("terminalState") or "")
    resource = worker.get("resource") or {}
    retained = str(resource.get("retainedReason") or "")
    if state not in SETTLED:
        return f"worker {state or 'bilinmiyor'} (bitmedi)"
    if terminal == "released":
        return "zaten serbest"
    if retained == "user_takeover":
        return "user_takeover (insan devraldı)"
    if terminal == "reclaimable":
        return None
    if terminal == "retained":
        return f"retained ({retained or 'sebep yok'}) — elle incele"
    return f"terminal {terminal or 'bilinmiyor'}"


def plan_for(run_id: str) -> list[dict]:
    rows = []
    for worker in workers(run_id):
        reason = skip_reason(worker)
        rows.append(
            {
                "dispatch_id": worker.get("dispatchId"),
                "state": worker.get("workerState"),
                "terminal": worker.get("terminalState"),
                "action": "skip" if reason else "release",
                "reason": reason,
            }
        )
    return rows


def release(dispatch_id: str) -> bool:
    result = orca(
        ["orchestration", "worker-release", "--dispatch", dispatch_id, "--json"]
    )
    return bool(result)


def apply(rows: list[dict]) -> list[dict]:
    for row in rows:
        if row["action"] != "release":
            continue
        ok = release(str(row["dispatch_id"]))
        row["released"] = ok
        if not ok:
            row["action"] = "failed"
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="release settled worker terminals")
    parser.add_argument("--run", required=True, help="Orca run id")
    parser.add_argument("--apply", action="store_true", help="release (default: plan)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = plan_for(args.run)
    if not rows:
        print(
            f"worker_cleanup: {args.run} için worker bulunamadı (run kimliği veya Orca)",
            file=sys.stderr,
        )
        return 1
    if args.apply:
        rows = apply(rows)

    if args.json:
        print(json.dumps({"run_id": args.run, "workers": rows}, ensure_ascii=False, indent=2))
    else:
        print_summary(args.run, rows, args.apply)
    return 1 if any(row["action"] == "failed" for row in rows) else 0

def print_summary(run_id: str, rows: list[dict], applied: bool) -> None:
    released = sum(1 for row in rows if row.get("released"))
    planned = sum(1 for row in rows if row["action"] == "release")
    failed = sum(1 for row in rows if row["action"] == "failed")
    print(
        f"Run {run_id} · {len(rows)} worker · "
        f"{'serbest bırakıldı' if applied else 'plan'}: "
        f"{released if applied else planned}"
        + (f" · hata: {failed}" if failed else "")
    )
    for row in rows:
        reason = f" — {row['reason']}" if row.get("reason") else ""
        print(f"- {row['dispatch_id']} {row['action']}{reason}")


if __name__ == "__main__":
    sys.exit(main())
