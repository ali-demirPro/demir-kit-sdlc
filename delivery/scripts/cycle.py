#!/usr/bin/env python3
"""Cycle log: real wall-clock record of every state transition.

One JSON line per transition in ``<project>/.kit/cycle.jsonl``. The log is the
source of truth for durations: GitHub labels are applied in batches at close
time, so they cannot report when work actually started.

The log always lives in the main checkout, never in an epic worktree. Rows are
written from the worktree but read after the worktree is gone, so
:func:`project_root` resolves the git common dir instead of the current one.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DIR = ".kit"
NAME = "cycle.jsonl"
STAGES = (
    "scope-confirmed",
    "agent-approved",
    "executing",
    "review",
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


def git_root(cwd: Path | None = None) -> Path | None:
    """Main checkout root, even when called from a linked worktree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=str(cwd or Path.cwd()),
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    common = Path(result.stdout.strip())
    return common.parent if common.name == ".git" else common


def project_root(kit_root: Path, cwd: Path | None = None) -> Path:
    """Directory that owns ``.kit/``: the main checkout when it is a project."""
    override = os.environ.get("DEMIR_KIT_CYCLE_ROOT")
    if override:
        return Path(override)
    root = git_root(cwd)
    if root and (root / "kit.config.yaml").is_file():
        return root
    current = Path(cwd or Path.cwd())
    if (current / "kit.config.yaml").is_file():
        return current
    return Path(kit_root)


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
        try:
            number = int(row.get("issue"))
        except (TypeError, ValueError):
            continue
        if issue is not None and number != int(issue):
            continue
        rows.append(row)
    rows.sort(key=lambda item: str(item.get("ts")))
    return rows


def _first(rows: list[dict], stage: str) -> datetime | None:
    for row in rows:
        if row.get("stage") == stage:
            return parse_ts(row.get("ts"))
    return None


def phases(rows: list[dict]) -> list[dict]:
    """Named buckets: claim, exec, close. Review is measured separately."""
    ordered = sorted(rows, key=lambda item: str(item.get("ts")))
    if not ordered:
        return []
    sealed = _first(ordered, "agent-approved")
    executing = _first(ordered, "executing")
    done = _first(ordered, "leaf-done")
    closed = _first(ordered, "epic-done")

    anchors = [
        ("claim", "seal", "executing", sealed, executing),
        ("exec", "executing", "leaf-done", executing, done),
        ("close", "leaf-done", "epic-done", done, closed),
    ]
    result: list[dict] = []
    for key, label_from, label_to, begin, end in anchors:
        if not begin or not end or end <= begin:
            continue
        result.append(
            {
                "key": key,
                "from": label_from,
                "to": label_to,
                "minutes": max(0, int((end - begin).total_seconds() // 60)),
            }
        )
    return result


def review_minutes(rows: list[dict]) -> int:
    """Review tail: last review before leaf-done, never the gap between rounds.

    A multi-checkpoint leaf records one review row per checkpoint; summing every
    review row would count the next checkpoint's implementation as review time.
    """
    ordered = sorted(rows, key=lambda item: str(item.get("ts")))
    done = _first(ordered, "leaf-done")
    if not done:
        return 0
    last = None
    for row in ordered:
        if row.get("stage") == "review":
            stamp = parse_ts(row.get("ts"))
            if stamp and stamp < done:
                last = stamp
    if not last:
        return 0
    return max(0, int((done - last).total_seconds() // 60))


def summary(rows: list[dict]) -> dict:
    """Phase breakdown with percentages that add up to 100."""
    items = phases(rows)
    total = sum(item["minutes"] for item in items)
    if total:
        running = 0
        for item in items[:-1]:
            item["percent"] = round(100 * item["minutes"] / total)
            running += item["percent"]
        items[-1]["percent"] = max(0, 100 - running)
    else:
        for item in items:
            item["percent"] = 0
    return {
        "total_minutes": total,
        "phases": items,
        "review_minutes": review_minutes(rows),
    }


def section(
    rows: list[dict],
    label: str = "Döngü",
    cost: float | None = None,
    tokens: int | None = None,
) -> str:
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
    if data["review_minutes"]:
        share = (
            round(100 * data["review_minutes"] / data["total_minutes"])
            if data["total_minutes"]
            else 0
        )
        note = f"review {data['review_minutes']} dk (%{share}, exec içinde)"
        exec_parts = [part for part in parts if part.startswith("executing→")]
        if exec_parts:
            parts[parts.index(exec_parts[0])] += f" · {note}"
        else:
            parts.append(note)
    suffix = ""
    if tokens:
        suffix += f" · {int(tokens):,} token"
    if cost is not None:
        suffix += f" · ${float(cost):.4f}"
    return f"**{label}:** toplam {data['total_minutes']} dk · " + " · ".join(parts) + suffix


def close_wait(project: Path, issue: int, ts: str | None = None) -> bool:
    """Mark an open approval wait as finished."""
    rows = read(project, issue)
    if not any(row.get("stage") == "wait" for row in rows):
        return False
    if any(row.get("stage") == "wait-done" for row in rows):
        return False
    record(project, make_row(issue, "wait-done", actor="human", ts=ts))
    return True


STAGE_LABELS = {
    "scope-confirmed": "scope-confirmed",
    "agent-approved": "agent-approved",
    "executing": "executing",
    "leaf-done": "leaf-done",
    "epic-done": "epic-done",
}


def replay_rows(events: list[dict], existing: list[dict]) -> list[dict]:
    """Rows for label events the log does not have yet; nothing is invented."""
    seen = {str(row.get("stage")) for row in existing}
    rows: list[dict] = []
    for event in events:
        label = (event.get("label") or {}).get("name")
        stage = STAGE_LABELS.get(str(label or ""))
        stamp = event.get("created_at")
        if not stage or not stamp or stage in seen:
            continue
        seen.add(stage)
        rows.append(make_row(int(event.get("issue") or 0), stage, actor="replay", ts=stamp))
    return rows


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="cycle log reader")
    parser.add_argument("--project", default=".")
    parser.add_argument("--issue", type=int)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--replay", action="store_true", help="GitHub timeline'dan eksik satırları yaz")
    parser.add_argument("--repo", help="owner/repo (replay)")
    args = parser.parse_args()

    project = Path(args.project)
    if args.replay:
        if not args.issue or not args.repo:
            sys.exit("cycle: --replay için --issue ve --repo gerekli")
        import subprocess

        raw = subprocess.check_output(
            ["gh", "api", f"repos/{args.repo}/issues/{args.issue}/timeline?per_page=100"],
            text=True,
        )
        events = json.loads(raw)
        for event in events:
            event.setdefault("issue", args.issue)
        existing = read(project, args.issue)
        added = 0
        for row in replay_rows(events, existing):
            record(project, row)
            added += 1
        print(f"cycle: {added} satır eklendi")
        return 0

    rows = read(project, args.issue)
    if args.json:
        print(json.dumps({"rows": rows, "summary": summary(rows)}, ensure_ascii=False, indent=2))
    else:
        print(section(rows, f"#{args.issue}" if args.issue else "Döngü"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
