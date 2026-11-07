#!/usr/bin/env python3
"""Fleet audit: read every project's session log and show where time and money go.

Read-only by contract: the session database is opened with ``mode=ro``, nothing
is deleted, and no prompt or message text is copied into the report.

    audit.py --projects ~/Projects --days 7
    audit.py --project votum --json
    audit.py --recommend
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / ".local/share/opencode/opencode.db"
DEFAULT_PROJECTS = Path.home() / "Projects"
DEFAULT_DERIVED = Path.home() / "Library/Developer/Xcode/DerivedData"
SIMULATORS = Path.home() / "Library/Developer/CoreSimulator/Devices"
ZOMBIE_MINUTES = 180


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def project_name(directory: str) -> str:
    """`/x/Projects/votum` and `/x/orca/workspaces/votum/epic-70` → `votum`."""
    parts = Path(directory).parts
    if "workspaces" in parts:
        index = parts.index("workspaces")
        if index + 1 < len(parts):
            return parts[index + 1]
    return Path(directory).name or directory


def _table(conn: sqlite3.Connection) -> str | None:
    names = {
        row[0]
        for row in conn.execute("select name from sqlite_master where type='table'")
    }
    for candidate in ("session_v2", "session"):
        if candidate in names:
            return candidate
    return None


def session_rows(db_path: Path, since_ms: int) -> list[dict]:
    if not db_path or not Path(db_path).is_file():
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        table = _table(conn)
        if not table:
            return []
        cursor = conn.execute(
            f"""
            select directory, parent_id, cost, tokens_cache_read,
                   time_created, time_updated
            from {table}
            where time_created >= ?
            """,
            (since_ms,),
        )
        return [
            {
                "directory": str(row[0] or ""),
                "parent": row[1],
                "cost": float(row[2] or 0),
                "cache_read": int(row[3] or 0),
                "duration": max(0, int((row[5] or 0) - (row[4] or 0))),
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def cycle_leaf_minutes(project: Path) -> float | None:
    path = Path(project) / ".kit" / "cycle.jsonl"
    if not path.is_file():
        return None
    rows: dict[int, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or not row.get("ts"):
            continue
        rows.setdefault(int(row.get("issue") or 0), []).append(str(row["ts"]))
    durations = []
    for stamps in rows.values():
        if not stamps:
            continue
        start = datetime.fromisoformat(min(stamps).replace("Z", "+00:00"))
        end = datetime.fromisoformat(max(stamps).replace("Z", "+00:00"))
        durations.append((end - start).total_seconds() / 60)
    durations = [value for value in durations if value > 0]
    if not durations:
        return None
    return round(statistics.median(durations))


def derived_count(project: str, derived_root: Path) -> int:
    root = Path(derived_root)
    if not root.is_dir():
        return 0
    prefix = project.lower() + "-"
    return sum(1 for item in root.iterdir() if item.is_dir() and item.name.lower().startswith(prefix))


def collect(
    projects_root: Path,
    days: int = 7,
    db_path: Path | None = None,
    derived_root: Path | None = None,
) -> dict:
    db = Path(db_path) if db_path else DEFAULT_DB
    derived = Path(derived_root) if derived_root else DEFAULT_DERIVED
    rows = session_rows(db, now_ms() - int(days * 86_400_000))

    projects: dict[str, dict] = {}
    for row in rows:
        if not row["directory"] or row["directory"] in {"/", "."}:
            continue
        name = project_name(row["directory"])
        project = projects.setdefault(
            name,
            {
                "sessions": 0,
                "subagents": 0,
                "cache_read": 0,
                "cost": 0.0,
                "minutes": 0,
                "zombies": 0,
                "derived_data": 0,
                "leaf_median_minutes": None,
            },
        )
        project["sessions"] += 1
        if row["parent"]:
            project["subagents"] += 1
        project["cache_read"] += row["cache_read"]
        project["cost"] += row["cost"]
        minutes = row["duration"] / 60_000
        project["minutes"] += int(minutes)
        if minutes >= ZOMBIE_MINUTES:
            project["zombies"] += 1

    for name, project in projects.items():
        project["cost"] = round(project["cost"], 2)
        project["derived_data"] = derived_count(name, derived)
        project["leaf_median_minutes"] = cycle_leaf_minutes(Path(projects_root) / name)

    simulators = 0
    if SIMULATORS.is_dir():
        simulators = sum(1 for item in SIMULATORS.iterdir() if item.is_dir())

    return {
        "window_days": days,
        "db": str(db),
        "projects": projects,
        "global": {
            "simulators": simulators,
            "derived_data": sum(p["derived_data"] for p in projects.values()),
            "sessions": sum(p["sessions"] for p in projects.values()),
            "subagents": sum(p["subagents"] for p in projects.values()),
            "cache_read": sum(p["cache_read"] for p in projects.values()),
            "cost": round(sum(p["cost"] for p in projects.values()), 2),
            "zombies": sum(p["zombies"] for p in projects.values()),
        },
    }


def _mb(value: int) -> str:
    return f"{value / 1_000_000:.0f}M"


def render(data: dict) -> str:
    lines = [
        f"Filo denetimi · son {data['window_days']} gün · {data['global']['sessions']} oturum",
        "",
        "proje       oturum  subagent  cache-read  maliyet  leaf med  zombi  ddata",
    ]
    for name, project in sorted(
        data["projects"].items(), key=lambda item: -item[1]["cache_read"]
    ):
        leaf = project["leaf_median_minutes"]
        lines.append(
            f"{name[:14]:14}  {project['sessions']:6}  {project['subagents']:8}  "
            f"{_mb(project['cache_read']):>10}  ${project['cost']:>6.2f}  "
            f"{(str(leaf) + ' dk') if leaf is not None else '—':>8}  "
            f"{project['zombies']:5}  {project['derived_data']:5}"
        )
    global_stats = data["global"]
    lines += [
        "",
        f"toplam: {_mb(global_stats['cache_read'])} cache · ${global_stats['cost']:.2f} · "
        f"{global_stats['zombies']} zombi oturum · {global_stats['simulators']} simülatör · "
        f"{global_stats['derived_data']} DerivedData",
    ]
    return "\n".join(lines)


def recommend(data: dict) -> list[str]:
    tips: list[str] = []
    if data["global"]["zombies"]:
        tips.append(
            f"{data['global']['zombies']} oturum boşta (3 saatten uzun) — reaper çalıştır."
        )
    if data["global"]["simulators"] > 1:
        tips.append(
            f"{data['global']['simulators']} simülatör cihazı var — tek cihaz yeter."
        )
    for name, project in sorted(data["projects"].items()):
        if project["derived_data"] > 1:
            tips.append(
                f"{name}: {project['derived_data']} DerivedData dizini — paylaşılan yol kullan."
            )
        if project["cache_read"] > 300_000_000:
            tips.append(
                f"{name}: {_mb(project['cache_read'])} cache-read — bağlam bütçesini düşür."
            )
        leaf = project["leaf_median_minutes"]
        if leaf is not None and leaf > 45:
            tips.append(f"{name}: leaf medyanı {leaf} dk — review turlarını azalt.")
    if not tips:
        tips.append("Eşik aşan kalem yok.")
    return tips


def main() -> int:
    parser = argparse.ArgumentParser(description="fleet audit (read-only)")
    parser.add_argument("--projects", default=str(DEFAULT_PROJECTS))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--project", help="one project name")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--derived-root", default=str(DEFAULT_DERIVED))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--recommend", action="store_true")
    args = parser.parse_args()

    data = collect(Path(args.projects), args.days, Path(args.db), Path(args.derived_root))
    if args.project:
        data["projects"] = {
            name: value for name, value in data["projects"].items() if name == args.project
        }
    tips = recommend(data)
    data["recommendations"] = tips

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print(render(data))
    if args.recommend:
        print("")
        for tip in tips:
            print(f"- {tip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
