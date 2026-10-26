#!/usr/bin/env python3
"""Collect OpenCode session duration, tokens and cost for a time window."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
    args = parser.parse_args()

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
