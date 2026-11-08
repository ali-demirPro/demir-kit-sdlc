#!/usr/bin/env python3
"""Collect OpenCode session duration, tokens and cost for a time window."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = "opencode2"


def project_root(cwd: Path | None = None) -> Path:
    current = Path(cwd) if cwd else Path.cwd()
    return current if (current / "kit.config.yaml").is_file() else ROOT


def parse_time(value: str | None, default: datetime) -> datetime:
    if not value:
        return default
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def token_totals(tokens: dict | None) -> dict:
    tokens = tokens or {}
    cache = tokens.get("cache") or {}
    return {
        "input": int(tokens.get("input") or 0),
        "output": int(tokens.get("output") or 0),
        "reasoning": int(tokens.get("reasoning") or 0),
        "cache_read": int(cache.get("read") or 0),
        "cache_write": int(cache.get("write") or 0),
    }


def summarize_export(
    data: dict, since_ms: int, until_ms: int
) -> dict:
    info = data.get("info") or {}
    messages = data.get("messages") or []
    windowed = [
        message
        for message in messages
        if since_ms <= (message.get("time") or {}).get("created", 0) <= until_ms
    ]
    if windowed and any(message.get("cost") is not None for message in windowed):
        cost = sum(message.get("cost") or 0 for message in windowed)
        tokens = {
            key: sum(((message.get("tokens") or {}).get(key) or 0) for message in windowed)
            for key in ("input", "output", "reasoning")
        }
        cache = {"read": 0, "write": 0}
        for message in windowed:
            cache["read"] += ((message.get("tokens") or {}).get("cache") or {}).get("read", 0)
            cache["write"] += ((message.get("tokens") or {}).get("cache") or {}).get("write", 0)
        tokens["cache"] = cache
        confidence = "exact"
        times = [
            (message.get("time") or {}).get("created")
            for message in windowed
            if (message.get("time") or {}).get("created")
        ]
        duration = round((max(times) - min(times)) / 1000, 1) if times else None
    else:
        cost = info.get("cost")
        tokens = info.get("tokens")
        confidence = "session_total" if cost is not None else "unavailable"
        created = info.get("time", {}).get("created")
        updated = info.get("time", {}).get("updated")
        duration = round((updated - created) / 1000, 1) if created and updated else None

    return {
        "cost": round(float(cost), 6) if cost is not None else None,
        "tokens": token_totals(tokens),
        "model": info.get("model"),
        "duration_seconds": duration,
        "confidence": confidence,
    }


def run(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        sys.exit(f"usage: {' '.join(args[:2])} failed — {result.stderr.strip()}")
    return result.stdout


def api_session_info(session_id: str) -> dict:
    raw = run([BIN, "api", "GET", f"/api/session/{session_id}"])
    payload = json.loads(raw)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ValueError("session info missing")
    return data


CONTEXT_WARN = 200_000
CONTEXT_HARD = 300_000


def context_state(tokens: int, warn: int = CONTEXT_WARN, hard: int = CONTEXT_HARD) -> tuple[int, str]:
    """(exit code, message) for one session context size."""
    if tokens >= hard:
        return (1, f"bağlam {tokens:,} token ≥ {hard:,} — yeni oturum aç")
    if tokens >= warn:
        return (0, f"bağlam {tokens:,} token ≥ {warn:,} — özet yaz, yeni oturuma geç")
    return (0, "")


def snapshot_path(issue: int, project: Path | None = None) -> Path:
    project = project or project_root()
    return project / ".orchestration" / f"usage-{issue}.json"


def current_session(project: Path | None = None) -> dict:
    project = project or project_root()
    sessions = json.loads(
        run([BIN, "session", "list", "-n", "200", "--format", "json"])
    )
    candidates = [row for row in sessions if row.get("directory") == str(project)]
    if not candidates:
        raise ValueError("no session in project")
    env_id = os.environ.get("OPENCODE_SESSION_ID")
    if env_id:
        for row in candidates:
            if row.get("id") == env_id:
                return row
    now_ms = time.time() * 1000
    recent = [row for row in candidates if row.get("updated", 0) >= now_ms - 3_600_000]
    pool = recent or candidates
    return max(
        pool,
        key=lambda row: row.get("updated", 0) - row.get("created", 0),
    )


def write_snapshot(issue: int) -> dict:
    project = project_root()
    session = current_session(project)
    info = api_session_info(session["id"])
    data = {
        "issue": issue,
        "session_id": session["id"],
        "cost": info.get("cost"),
        "tokens": info.get("tokens"),
        "time": info.get("time"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path = snapshot_path(issue, project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def read_snapshot(issue: int) -> dict | None:
    path = snapshot_path(issue)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compute_delta(snapshot: dict, current: dict) -> dict:
    if snapshot.get("session_id") != current.get("id"):
        raise ValueError("session mismatch")
    snap_tokens = token_totals(snapshot.get("tokens"))
    cur_tokens = token_totals(current.get("tokens"))
    snap_time = (snapshot.get("time") or {}).get("updated") or 0
    cur_time = (current.get("time") or {}).get("updated") or 0
    return {
        "session_id": current.get("id"),
        "cost": round(max(0.0, float(current.get("cost") or 0) - float(snapshot.get("cost") or 0)), 6),
        "tokens": {
            key: max(0, cur_tokens[key] - snap_tokens[key])
            for key in ("input", "output", "reasoning", "cache_read", "cache_write")
        },
        "duration_seconds": round(max(0, cur_time - snap_time) / 1000, 1),
        "confidence": "exact",
    }


def session_delta(issue: int) -> dict:
    snapshot = read_snapshot(issue)
    if not snapshot:
        raise ValueError("no snapshot")
    current = api_session_info(snapshot["session_id"])
    return compute_delta(snapshot, current)


def run_in(cwd: Path, args: list[str]) -> str:
    result = subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise SystemExit(f"usage: {' '.join(args[:2])} failed — {result.stderr.strip()}")
    return result.stdout


def orca_result(args: list[str]) -> dict:
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


def worktree_path(value: str) -> str:
    return value.split("::", 1)[1] if "::" in value else value


def dispatch_record(dispatch_id: str, full: bool = False) -> dict:
    args = ["orchestration", "worker-show", "--dispatch", dispatch_id, "--json"]
    if full:
        args.append("--full")
    result = orca_result(args)
    dispatch = result.get("dispatch") or {}
    worker = result.get("worker") or {}
    raw_path = str(worker.get("worktreeId") or "")
    return {
        "dispatch": dispatch,
        "path": worktree_path(raw_path),
    }


def parse_dispatch_time(value: str | None) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc)
    if "T" not in text:
        text = text.replace(" ", "T")
    return parse_time(text, datetime.now(timezone.utc))


def sessions_in(path: str) -> list[dict]:
    """OpenCode sessions whose directory is the worker worktree."""
    if not path or not Path(path).is_dir():
        return []
    try:
        raw = run_in(Path(path), [BIN, "session", "list", "-n", "200", "--format", "json"])
    except (SystemExit, OSError):
        return []
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(rows, list):
        return []
    target = str(Path(path).resolve())
    picked = []
    for row in rows:
        directory = str(row.get("directory") or "").strip()
        if not directory:
            continue
        if str(Path(directory).resolve()) == target:
            picked.append(row)
    return picked


def session_for_window(
    sessions: list[dict],
    start_ms: int,
    end_ms: int,
    slack_ms: int = 10_000,
    boot_ms: int = 120_000,
) -> dict | None:
    """Pick the worker session created right after the dispatch started.

    Ambiguous matches (two sessions within five seconds) return None instead of
    charging the wrong dispatch.
    """
    upper = min(end_ms, start_ms + boot_ms)
    candidates = []
    for session in sessions:
        created = int(session.get("created") or 0)
        if created and start_ms - slack_ms <= created <= upper:
            candidates.append(session)
    if not candidates:
        return None
    ranked = sorted(
        candidates, key=lambda item: abs(int(item.get("created") or 0) - start_ms)
    )
    if len(ranked) > 1:
        first = int(ranked[0].get("created") or 0)
        second = int(ranked[1].get("created") or 0)
        if abs(first - second) < 5_000:
            return None
    return ranked[0]


def session_export(session_id: str) -> dict:
    raw = run([BIN, "session", "export", session_id, "--sanitize"])
    return json.loads(raw)


def empty_tokens() -> dict:
    return token_totals(None)


_UNSET = object()
SESSION_MAP = "worker-sessions.json"


def state_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            candidate = Path(result.stdout.strip()).parent
            if candidate.is_dir():
                return candidate
    except (FileNotFoundError, OSError):
        pass
    return project_root()


def session_map_path() -> Path:
    return state_root() / ".orchestration" / SESSION_MAP


def load_session_map() -> dict:
    try:
        data = json.loads(session_map_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def record_session(dispatch_id: str, session: dict) -> None:
    data = load_session_map()
    data[str(dispatch_id)] = {
        "id": str(session.get("id") or ""),
        "title": str(session.get("title") or ""),
        "created": int(session.get("created") or 0),
        "updated": int(session.get("updated") or 0),
    }
    if len(data) > 200:
        for key in sorted(
            data, key=lambda item: int((data[item] or {}).get("created") or 0)
        )[: len(data) - 200]:
            data.pop(key, None)
    path = session_map_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mapped_session(dispatch_id: str) -> dict | None:
    entry = load_session_map().get(str(dispatch_id))
    return entry if isinstance(entry, dict) and entry.get("id") else None


def worker_window(dispatch_id: str) -> dict:
    record = dispatch_record(dispatch_id)
    dispatch = record["dispatch"]
    start = parse_dispatch_time(dispatch.get("dispatchedAt"))
    end = parse_dispatch_time(
        dispatch.get("completedAt") or dispatch.get("lastHeartbeatAt")
    )
    return {
        "dispatch_id": dispatch_id,
        "dispatch": dispatch,
        "path": record["path"],
        "start_ms": int(start.timestamp() * 1000),
        "end_ms": int(end.timestamp() * 1000),
    }


def dispatch_usage(
    dispatch_id: str, window: dict | None = None, session=_UNSET
) -> dict:
    """Token/cost of one supervised worker, resolved by worktree + time window."""
    window = window or worker_window(dispatch_id)
    dispatch = window["dispatch"]
    path = window["path"]
    start_ms = window["start_ms"]
    end_ms = window["end_ms"]
    base = {
        "dispatch_id": dispatch_id,
        "run_id": dispatch.get("runId"),
        "state": dispatch.get("status"),
        "worktree": path,
        "session_id": None,
        "title": None,
        "cost": None,
        "tokens": empty_tokens(),
        "context_peak": 0,
        "duration_seconds": round((end_ms - start_ms) / 1000, 1),
        "confidence": "unavailable",
    }
    if session is _UNSET:
        mapped = mapped_session(dispatch_id)
        session = (
            mapped
            if mapped
            else session_for_window(sessions_in(path), start_ms, end_ms)
        )
    if not session:
        return base
    try:
        export = session_export(str(session.get("id")))
        summary = summarize_export(export, start_ms, end_ms)
    except (SystemExit, OSError, json.JSONDecodeError):
        return base
    if summary.get("confidence") != "exact":
        return base
    peak = 0
    for message in export.get("messages") or []:
        created = int((message.get("time") or {}).get("created") or 0)
        if not start_ms <= created <= end_ms:
            continue
        tokens = message.get("tokens") or {}
        cache = tokens.get("cache") or {}
        peak = max(
            peak,
            int(tokens.get("input") or 0)
            + int(cache.get("read") or 0)
            + int(cache.get("write") or 0),
        )
    return {
        **base,
        "session_id": session.get("id"),
        "title": session.get("title"),
        "cost": summary.get("cost"),
        "tokens": summary.get("tokens"),
        "context_peak": peak,
        "duration_seconds": summary.get("duration_seconds"),
        "confidence": summary.get("confidence"),
    }


def run_workers(run_id: str) -> list[dict]:
    rows: list[dict] = []
    cursor = None
    seen: set[str] = set()
    while True:
        args = [
            "orchestration",
            "worker-list",
            "--run",
            run_id,
            "--limit",
            "100",
            "--full",
            "--json",
        ]
        if cursor:
            args += ["--cursor", str(cursor)]
        result = orca_result(args)
        page = result.get("workers") or []
        rows.extend(page)
        next_cursor = (result.get("page") or {}).get("nextCursor")
        if not next_cursor or next_cursor in seen or not page:
            break
        seen.add(str(next_cursor))
        cursor = next_cursor
    return rows


def run_usage(run_id: str) -> dict:
    rows = []
    for item in run_workers(run_id):
        window = worker_window(str(item.get("dispatchId")))
        rows.append(
            dispatch_usage(
                str(window["dispatch_id"]),
                window=window,
                session=mapped_session(str(window["dispatch_id"])),
            )
        )
    measured = [row for row in rows if row.get("confidence") != "unavailable"]
    totals = {
        "cost_usd": round(sum(float(row.get("cost") or 0) for row in measured), 6)
        if measured
        else None,
        "tokens_in": sum(row["tokens"].get("input", 0) for row in measured),
        "tokens_out": sum(row["tokens"].get("output", 0) for row in measured),
        "cache_read": sum(row["tokens"].get("cache_read", 0) for row in measured),
        "context_peak": max((row.get("context_peak") or 0) for row in rows) if rows else 0,
        "worker_count": len(rows),
        "measured": len(measured),
        "unavailable": len(rows) - len(measured),
    }
    return {"run_id": run_id, "totals": totals, "workers": rows}


def render_dispatch(row: dict) -> str:
    tokens = row.get("tokens") or {}
    cost = row.get("cost")
    cost_text = "ölçülemedi" if cost is None else f"${float(cost):.4f}"
    return "\n".join(
        [
            f"Dispatch {row['dispatch_id']} · {row.get('state')} · {row.get('confidence')}",
            f"Oturum: {row.get('session_id') or '—'} {row.get('title') or ''}".rstrip(),
            f"Token: {tokens.get('input', 0):,} in · {tokens.get('output', 0):,} out · "
            f"{tokens.get('cache_read', 0):,} cache",
            f"Bağlam tepesi: {row.get('context_peak', 0):,} · Süre: {row.get('duration_seconds')} sn",
            f"Maliyet: {cost_text}",
        ]
    )


def render_run(data: dict) -> str:
    totals = data["totals"]
    cost = totals.get("cost_usd")
    cost_text = "ölçülemedi" if cost is None else f"${float(cost):.4f}"
    lines = [
        f"Run {data['run_id']} · {totals['worker_count']} worker "
        f"({totals['measured']} ölçüldü, {totals['unavailable']} belirsiz)",
        f"Token: {totals['tokens_in']:,} in · {totals['tokens_out']:,} out · "
        f"{totals['cache_read']:,} cache · bağlam tepesi {totals['context_peak']:,}",
        f"Maliyet: {cost_text}",
    ]
    for row in data["workers"]:
        lines.append(
            f"- {row['dispatch_id']} · {row.get('confidence')} · "
            f"{row.get('title') or row.get('state') or '—'}"
        )
    return "\n".join(lines)



def collect(since: datetime, until: datetime) -> dict:
    since_ms = int(since.timestamp() * 1000)
    until_ms = int(until.timestamp() * 1000)
    try:
        sessions = json.loads(
            run([BIN, "session", "list", "-n", "200", "--format", "json"])
        )
    except FileNotFoundError:
        sys.exit(f"usage: {BIN} bulunamadı")

    project = project_root()
    rows = []
    for session in sessions:
        if session.get("directory") != str(project):
            continue
        if session.get("updated", 0) < since_ms or session.get("created", 0) > until_ms:
            continue
        try:
            export = json.loads(
                run([BIN, "session", "export", session["id"], "--sanitize"])
            )
            summary = summarize_export(export, since_ms, until_ms)
        except (json.JSONDecodeError, SystemExit):
            try:
                info = api_session_info(session["id"])
                summary = summarize_export(
                    {"info": info, "messages": []}, since_ms, until_ms
                )
            except (json.JSONDecodeError, SystemExit, ValueError):
                summary = {
                    "cost": None,
                    "tokens": token_totals(None),
                    "model": None,
                    "duration_seconds": None,
                    "confidence": "unavailable",
                }
        rows.append(
            {
                "id": session["id"],
                "title": session.get("title", ""),
                "created": session.get("created"),
                "updated": session.get("updated"),
                "spans_window": session.get("created", 0) < since_ms,
                **summary,
            }
        )

    measured = [
        row
        for row in rows
        if row["cost"] is not None
        and not (row["confidence"] == "session_total" and row.get("spans_window"))
    ]
    session_totals = [
        row
        for row in rows
        if row["cost"] is not None
        and row["confidence"] == "session_total"
        and row.get("spans_window")
    ]
    if measured:
        cost = round(sum(row["cost"] for row in measured), 6)
    else:
        cost = None
    if len(measured) < len(rows) - len(session_totals):
        confidence = "partial"
    elif measured and all(row["confidence"] == "exact" for row in measured):
        confidence = "exact"
    elif measured:
        confidence = "session_total"
    else:
        confidence = "partial"

    totals = {
        "cost": cost,
        "input": sum(row["tokens"]["input"] for row in measured),
        "output": sum(row["tokens"]["output"] for row in measured),
        "cache_read": sum(row["tokens"]["cache_read"] for row in measured),
        "sessions": len(rows),
        "measured_sessions": len(measured),
        "session_total_cost": round(sum(row["cost"] for row in session_totals), 6)
        if session_totals
        else None,
        "session_total_sessions": len(session_totals),
        "confidence": confidence,
    }
    return {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "sessions": rows,
        "totals": totals,
        "unavailable": [row["id"] for row in rows if row["confidence"] == "unavailable"],
    }


def render(data: dict) -> str:
    totals = data["totals"]
    if totals.get("cost") is None:
        cost_text = "ölçülemedi"
    else:
        cost_text = f"${totals['cost']:.4f}"
    if totals.get("confidence") == "partial":
        cost_text += " (kısmi)"
    lines = [
        f"Oturumlar: {totals['sessions']}",
        f"Token: {totals['input']:,} in · {totals['output']:,} out · {totals['cache_read']:,} cache",
        f"Maliyet: {cost_text}",
        "Kaynak: OpenCode session export (exact/session_total/unavailable)",
    ]
    for row in data["sessions"]:
        cost = "—" if row["cost"] is None else f"${row['cost']:.4f}"
        lines.append(
            f"- {row['title'][:50]} · {cost} · {row['confidence']}"
        )
    if totals.get("session_total_cost") is not None:
        lines.append(
            f"Ana oturum toplamı: ${totals['session_total_cost']:.4f} "
            f"({totals.get('session_total_sessions', 0)} oturum; epic'e atfedilemedi)"
        )
    if data["unavailable"]:
        lines.append(
            "Not: bazı oturumların export'u kesildi; maliyet ölçülemedi olarak işaretlendi."
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="session usage for a window")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--hours", type=float, default=24)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--delta", action="store_true")
    parser.add_argument("--issue", type=int)
    parser.add_argument("--check", action="store_true", help="bağlam bütçesi kontrolü")
    parser.add_argument("--context", type=int, help="oturum bağlamı (token)")
    parser.add_argument("--dispatch", help="one supervised worker dispatch id")
    parser.add_argument("--run", help="aggregate all workers of an Orca run")
    args = parser.parse_args()

    if args.check:
        if args.context is None:
            sys.exit("usage: --check için --context <token> gerekli")
        code, message = context_state(int(args.context))
        if message:
            print(message)
        return code

    if args.dispatch:
        data = dispatch_usage(args.dispatch)
        print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else render_dispatch(data))
        return 0

    if args.run:
        data = run_usage(args.run)
        print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else render_run(data))
        return 0

    if args.snapshot or args.delta:
        if not args.issue:
            sys.exit("usage: --snapshot/--delta requires --issue")
        try:
            data = write_snapshot(args.issue) if args.snapshot else session_delta(args.issue)
        except (ValueError, SystemExit, json.JSONDecodeError) as exc:
            sys.exit(f"usage: {exc}")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    until = parse_time(args.until, datetime.now(timezone.utc))
    since = parse_time(args.since, until - timedelta(hours=args.hours))
    data = collect(since, until)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
