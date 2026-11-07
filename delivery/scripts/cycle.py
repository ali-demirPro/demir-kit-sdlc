#!/usr/bin/env python3
"""Cycle log: real wall-clock record of every state transition.

One JSON line per transition in ``<project>/.kit/cycle.jsonl``. The log is the
source of truth for durations: GitHub labels are applied in batches at close
time, so they cannot report when work actually started.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DIR = ".kit"
NAME = "cycle.jsonl"
STAGES = (
    "scope-confirmed",
    "agent-approved",
    "executing",
    "blocked",
    "deferred",
    "leaf-done",
    "epic-reconcile",
    "epic-done",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def cycle_path(project: Path) -> Path:
    return Path(project) / DIR / NAME


def make_row(
    issue: int,
    stage: str,
    actor: str = "",
    reason: str = "",
    epic: int | None = None,
    ts: str | None = None,
) -> dict:
    """Build one cycle row without touching the filesystem."""
    row = {
        "ts": ts or now(),
        "issue": int(issue),
        "stage": str(stage),
        "actor": str(actor or ""),
    }
    if reason:
        row["reason"] = str(reason)
    if epic:
        row["epic"] = int(epic)
    return row


def record(project: Path, row: dict) -> dict:
    """Append one row; create ``.kit/`` when missing."""
    path = cycle_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read(project: Path, issue: int | None = None) -> list[dict]:
    """Read rows oldest-first; ignore blank or broken lines."""
    path = cycle_path(project)
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or not row.get("ts") or "issue" not in row:
            continue
        if issue is not None and int(row.get("issue") or 0) != int(issue):
            continue
        rows.append(row)
    rows.sort(key=lambda item: str(item.get("ts")))
    return rows


def phases(rows: list[dict]) -> list[dict]:
    """Minutes spent between consecutive stages."""
    ordered = sorted(rows, key=lambda item: str(item.get("ts")))
    result: list[dict] = []
    for previous, current in zip(ordered, ordered[1:]):
        start = parse_ts(previous.get("ts"))
        end = parse_ts(current.get("ts"))
        if not start or not end:
            continue
        minutes = max(0, int((end - start).total_seconds() // 60))
        result.append(
            {
                "from": str(previous.get("stage") or "?"),
                "to": str(current.get("stage") or "?"),
                "minutes": minutes,
            }
        )
    return result


def summary(rows: list[dict]) -> dict:
    """Phase breakdown with percentages of the measured span."""
    items = phases(rows)
    total = sum(item["minutes"] for item in items)
    for item in items:
        item["percent"] = round(100 * item["minutes"] / total) if total else 0
    return {"total_minutes": total, "phases": items}


def section(rows: list[dict], label: str = "Döngü") -> str:
    """One Markdown line for the human report."""
    if not rows:
        return f"**{label}:** kayıt yok"
    data = summary(rows)
    if not data["phases"]:
        return f"**{label}:** {len(rows)} kayıt, tek aşama"
    parts = [
        f"{item['from']}→{item['to']} {item['minutes']} dk (%{item['percent']})"
        for item in data["phases"]
    ]
    return f"**{label}:** toplam {data['total_minutes']} dk · " + " · ".join(parts)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="cycle log reader")
    parser.add_argument("--project", default=".")
    parser.add_argument("--issue", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = read(Path(args.project), args.issue)
    if args.json:
        print(json.dumps({"rows": rows, "summary": summary(rows)}, ensure_ascii=False, indent=2))
    else:
        print(section(rows, f"#{args.issue}" if args.issue else "Döngü"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
