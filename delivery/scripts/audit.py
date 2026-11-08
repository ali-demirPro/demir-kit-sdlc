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
import re
import sqlite3
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / ".local/share/opencode/opencode.db"
DEFAULT_PROJECTS = Path.home() / "Projects"
DEFAULT_DERIVED = Path.home() / "Library/Developer/Xcode/DerivedData"
SIMULATORS = Path.home() / "Library/Developer/CoreSimulator/Devices"
ZOMBIE_MINUTES = 180
PLACEHOLDER_RE = re.compile(r"^reviewer[_-][a-z]$", re.I)


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


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


def evidence_reviews(project: Path, since: datetime) -> int | None:
    """Verified review rounds from `.kit/evidence.jsonl`.

    ``None`` means the project has no index yet, so the caller keeps the legacy
    cycle-log count. A round counts only when the evidence names at least one
    reviewer id; a placeholder (``reviewer_a``) is not a review.
    """
    path = Path(project) / ".kit" / "evidence.jsonl"
    if not path.is_file():
        return None
    rounds = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        stamp = parse_ts(row.get("ts") or "")
        if not stamp or stamp < since:
            continue
        raw = row.get("reviewers")
        ids = (
            [item for item in raw if isinstance(item, str)]
            if isinstance(raw, list)
            else []
        )
        if [item.strip() for item in ids if item.strip() and not PLACEHOLDER_RE.match(item)]:
            rounds += 1
    return rounds


def cycle_stats(project: Path, since: datetime) -> dict:
    """Review rounds, gate runs and leaf median from `.kit/`.

    Review rounds come from `.kit/evidence.jsonl` (real reviewer ids) when that
    index exists; projects without it keep the legacy `.kit/cycle.jsonl` count.
    The leaf median selects issues whose ``leaf-done`` falls inside the window
    and measures ``executing -> leaf-done`` so approval waiting does not inflate
    the leaf time.
    """
    empty = {
        "review_rounds": 0,
        "reviews_measured": False,
        "gates": 0,
        "leaf_median_minutes": None,
    }
    path = Path(project) / ".kit" / "cycle.jsonl"
    indexed = evidence_reviews(Path(project), since)
    if not path.is_file():
        return {
            **empty,
            "review_rounds": indexed or 0,
            "reviews_measured": indexed is not None,
        }
    by_issue: dict[int, list[dict]] = {}
    legacy = 0
    gates = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        try:
            number = int(row.get("issue") or 0)
        except (TypeError, ValueError):
            continue
        stamp = parse_ts(row.get("ts") or "")
        if not stamp:
            continue
        by_issue.setdefault(number, []).append(row)
        if stamp < since:
            continue
        if row.get("stage") == "review":
            legacy += 1
        elif row.get("stage") == "gate":
            gates += 1

    durations = []
    for rows in by_issue.values():
        stages = {row.get("stage") for row in rows}
        if "epic-done" in stages or "leaf-done" not in stages:
            continue
        done = [
            parse_ts(row.get("ts") or "")
            for row in rows
            if row.get("stage") == "leaf-done"
        ]
        done = [stamp for stamp in done if stamp and stamp >= since]
        if not done:
            continue
        starts = [
            parse_ts(row.get("ts") or "")
            for row in rows
            if row.get("stage") == "executing"
        ]
        starts = [stamp for stamp in starts if stamp]
        begin = min(starts) if starts else min(
            (stamp for stamp in (parse_ts(row.get("ts") or "") for row in rows) if stamp),
            default=None,
        )
        if not begin:
            continue
        minutes = (min(done) - begin).total_seconds() / 60
        if minutes > 0:
            durations.append(minutes)
    return {
        "review_rounds": legacy if indexed is None else indexed,
        "reviews_measured": indexed is not None,
        "gates": gates,
        "leaf_median_minutes": round(statistics.median(durations)) if durations else None,
    }


def derived_usage(project: str, derived_root: Path) -> tuple[int, int]:
    """(directory count, bytes) for `<project>-*` DerivedData folders."""
    root = Path(derived_root)
    if not root.is_dir():
        return (0, 0)
    prefix = project.lower() + "-"
    dirs = [item for item in root.iterdir() if item.is_dir() and item.name.lower().startswith(prefix)]
    if not dirs:
        return (0, 0)
    try:
        output = subprocess.check_output(
            ["du", "-sk", *[str(item) for item in dirs]], text=True, timeout=20
        )
        total_kb = sum(int(line.split()[0]) for line in output.splitlines() if line.split())
        return (len(dirs), total_kb * 1024)
    except (OSError, subprocess.SubprocessError, ValueError):
        return (len(dirs), 0)


def project_dirs(projects_root: Path) -> list[Path]:
    root = Path(projects_root)
    if not root.is_dir():
        return []
    return [
        item
        for item in root.iterdir()
        if item.is_dir() and ((item / ".kit").is_dir() or (item / "kit.config.yaml").is_file())
    ]


def blank_project() -> dict:
    return {
        "sessions": 0,
        "subagents": 0,
        "cache_read": 0,
        "cost": 0.0,
        "minutes": 0,
        "zombies": 0,
        "review_rounds": 0,
        "reviews_measured": False,
        "gates": 0,
        "leaf_median_minutes": None,
        "derived_data": 0,
        "derived_bytes": 0,
    }


def totals(projects: dict, simulators: int) -> dict:
    return {
        "simulators": simulators,
        "derived_data": sum(p["derived_data"] for p in projects.values()),
        "derived_bytes": sum(p.get("derived_bytes", 0) for p in projects.values()),
        "sessions": sum(p["sessions"] for p in projects.values()),
        "subagents": sum(p["subagents"] for p in projects.values()),
        "cache_read": sum(p["cache_read"] for p in projects.values()),
        "cost": round(sum(p["cost"] for p in projects.values()), 2),
        "zombies": sum(p["zombies"] for p in projects.values()),
        "review_rounds": sum(p["review_rounds"] for p in projects.values()),
        "gates": sum(p["gates"] for p in projects.values()),
    }


def collect(
    projects_root: Path,
    days: int = 7,
    db_path: Path | None = None,
    derived_root: Path | None = None,
) -> dict:
    db = Path(db_path) if db_path else DEFAULT_DB
    derived = Path(derived_root) if derived_root else DEFAULT_DERIVED
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = session_rows(db, int(since.timestamp() * 1000))

    projects: dict[str, dict] = {
        item.name: blank_project() for item in project_dirs(Path(projects_root))
    }
    for row in rows:
        if not row["directory"] or row["directory"] in {"/", "."}:
            continue
        name = project_name(row["directory"])
        project = projects.setdefault(name, blank_project())
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
        count, size = derived_usage(name, derived)
        project["derived_data"] = count
        project["derived_bytes"] = size
        stats = cycle_stats(Path(projects_root) / name, since)
        project["review_rounds"] = stats["review_rounds"]
        project["reviews_measured"] = stats["reviews_measured"]
        project["gates"] = stats["gates"]
        project["leaf_median_minutes"] = stats["leaf_median_minutes"]

    simulators = 0
    if SIMULATORS.is_dir():
        simulators = sum(1 for item in SIMULATORS.iterdir() if item.is_dir())

    return {
        "window_days": days,
        "db": str(db),
        "projects": projects,
        "global": totals(projects, simulators),
    }


def _mb(value: int) -> str:
    return f"{value / 1_000_000:.0f}M"


def _size(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}G"
    return f"{value / 1_000_000:.0f}M"


def render(data: dict) -> str:
    lines = [
        f"Filo denetimi · son {data['window_days']} gün · {data['global']['sessions']} oturum",
        "",
        "proje           oturum  sub  cache  maliyet  leaf  review  gate  zombi  ddata  disk",
    ]
    for name, project in sorted(
        data["projects"].items(), key=lambda item: -item[1]["cache_read"]
    ):
        leaf = project["leaf_median_minutes"]
        reviews = (
            f"{project['review_rounds']:6}"
            if project.get("reviews_measured")
            else f"{'—':>6}"
        )
        lines.append(
            f"{name[:14]:14}  {project['sessions']:6}  {project['subagents']:3}  "
            f"{_mb(project['cache_read']):>5}  ${project['cost']:>6.2f}  "
            f"{(str(leaf) + ' dk') if leaf is not None else '—':>6}  "
            f"{reviews}  {project['gates']:4}  "
            f"{project['zombies']:5}  {project['derived_data']:5}  "
            f"{_size(project['derived_bytes']):>5}"
        )
    summary = data["global"]
    lines += [
        "",
        f"toplam: {_mb(summary['cache_read'])} cache · ${summary['cost']:.2f} · "
        f"{summary['review_rounds']} review turu · {summary['gates']} kapı · "
        f"{summary['zombies']} zombi · {summary['simulators']} simülatör · "
        f"{summary['derived_data']} DerivedData ({_size(summary['derived_bytes'])})",
    ]
    return "\n".join(lines)


def recommend(data: dict) -> list[str]:
    tips: list[str] = []
    summary = data["global"]
    if summary["zombies"]:
        tips.append(f"{summary['zombies']} oturum boşta (3 saatten uzun) — `orca orchestration worker-list --run <id> --terminal-state active` ile incele, gerekirse worker-abandon.")
    if summary["simulators"] > 1:
        tips.append(f"{summary['simulators']} simülatör cihazı var — tek cihaz yeter.")
    if summary["derived_bytes"] > 20_000_000_000:
        tips.append(f"{_size(summary['derived_bytes'])} DerivedData — eski dizinleri temizle.")
    for name, project in sorted(data["projects"].items()):
        if project["derived_data"] > 1:
            tips.append(f"{name}: {project['derived_data']} DerivedData dizini — paylaşılan yol kullan.")
        if project["cache_read"] > 300_000_000:
            tips.append(f"{name}: {_mb(project['cache_read'])} cache-read — bağlam bütçesini düşür.")
        leaf = project["leaf_median_minutes"]
        if leaf is not None and leaf > 45:
            tips.append(f"{name}: leaf medyanı {leaf} dk — review turlarını azalt.")
        if project["review_rounds"] > project["sessions"]:
            tips.append(f"{name}: {project['review_rounds']} review turu — tur bütçesini uygula.")
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
    simulators = data["global"]["simulators"]
    if args.project:
        data["projects"] = {
            name: value for name, value in data["projects"].items() if name == args.project
        }
        data["global"] = totals(data["projects"], simulators)
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
