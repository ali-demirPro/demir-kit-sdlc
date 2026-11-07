#!/usr/bin/env python3
"""Release worker terminals that stopped producing work.

`worker_cleanup.py` releases terminals that *finished*; this reaper also closes
terminals that are still "running" but have not sent a heartbeat for a while —
the 8-hour idle panes that keep GPU and memory busy on a laptop.

    worker_reaper.py --run run_abc              # dry-run plan
    worker_reaper.py --run run_abc --apply      # release idle workers
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import usage  # noqa: E402
import worker_cleanup  # noqa: E402

DEFAULT_IDLE = 15
SETTLED_STATES = {"succeeded", "failed", "stopped"}


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def runs(project: Path | None = None) -> list[str]:
    root = Path(project or Path.cwd())
    found: list[str] = []
    for path in sorted((root / ".orchestration").glob("epic-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        run_id = str(data.get("run_id") or "")
        if run_id and run_id not in found:
            found.append(run_id)
    return found


def _dispatch(dispatch_id: str) -> dict:
    try:
        record = usage.dispatch_record(dispatch_id) or {}
    except Exception:
        return {}
    dispatch = record.get("dispatch")
    return dispatch if isinstance(dispatch, dict) else {}


def plan_for(
    run_id: str,
    idle_minutes: int = DEFAULT_IDLE,
    now: datetime | None = None,
) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    rows: list[dict] = []
    for worker in usage.run_workers(run_id):
        dispatch_id = str(worker.get("dispatchId") or "")
        if not dispatch_id:
            continue
        dispatch = _dispatch(dispatch_id)
        heartbeat = parse_ts(dispatch.get("lastHeartbeatAt")) or parse_ts(
            dispatch.get("dispatchedAt")
        )
        idle = int((now - heartbeat).total_seconds() // 60) if heartbeat else -1

        state = str(worker.get("workerState") or "")
        terminal = str(worker.get("terminalState") or "")
        retained = str((worker.get("resource") or {}).get("retainedReason") or "")

        reason = None
        if terminal == "released" or state in SETTLED_STATES:
            reason = "zaten bitti"
        elif retained == "user_takeover":
            reason = "insan devraldı"
        elif idle < 0:
            reason = "zaman bilgisi yok"
        elif idle < idle_minutes:
            reason = f"aktif ({idle} dk)"

        rows.append(
            {
                "run_id": run_id,
                "dispatch_id": dispatch_id,
                "state": state,
                "terminal": terminal,
                "idle_minutes": idle,
                "action": "release" if reason is None else "keep",
                "reason": reason,
            }
        )
    return rows


def apply(rows: list[dict]) -> list[dict]:
    for row in rows:
        if row.get("action") != "release":
            continue
        ok = worker_cleanup.release(str(row["dispatch_id"]))
        row["released"] = bool(ok)
        if not ok:
            row["action"] = "failed"
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="release idle worker terminals")
    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--idle-minutes", type=int, default=DEFAULT_IDLE)
    parser.add_argument("--project", default=".")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    targets = args.run or runs(Path(args.project))
    if not targets:
        print("worker_reaper: Orca run bulunamadı", file=sys.stderr)
        return 0

    rows: list[dict] = []
    for run_id in targets:
        rows.extend(plan_for(run_id, args.idle_minutes))
    if args.apply:
        rows = apply(rows)

    released = sum(1 for row in rows if row.get("released"))
    payload = {
        "runs": targets,
        "idle_minutes": args.idle_minutes,
        "released": released,
        "rows": rows,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"{'kapatıldı' if args.apply else 'plan'}: {released if args.apply else sum(1 for r in rows if r['action'] == 'release')}"
            f" / {len(rows)} worker · eşik {args.idle_minutes} dk"
        )
        for row in rows:
            if row["action"] != "keep":
                print(f"  - {row['dispatch_id']} · {row['action']} · {row.get('reason') or (str(row['idle_minutes']) + ' dk')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
