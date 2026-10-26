#!/usr/bin/env python3
"""Build a human work report from issue, commit, Orca and usage data."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import routing  # noqa: E402

PROJECT = routing.project_root(ROOT)


def gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"report: gh failed — {result.stderr.strip()}")
    return result.stdout


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def repo_name() -> str:
    ecosystem = yaml.safe_load((PROJECT / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        sys.exit("report: ecosystem.yaml tracker.repo yok")
    return repo


def parse_children(body: str) -> list[int]:
    match = re.search(r"```yaml\s+demir-kit-epic\s*\n(.*?)```", body, re.S)
    if not match:
        return []
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return []
    children = data.get("children") or []
    return [int(item) for item in children if isinstance(item, int)]


def parse_evidence(comments: list[dict]) -> list[dict]:
    records = []
    for comment in comments:
        match = re.search(
            r"```yaml\s+demir-kit-evidence\s*\n(.*?)```",
            comment.get("body") or "",
            re.S,
        )
        if not match:
            continue
        try:
            record = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            continue
        if isinstance(record, dict):
            record["_created_at"] = comment.get("created_at")
            records.append(record)
    return records


def extract_progress(comments: list[dict]) -> dict:
    decisions, problems, done = [], [], []
    for comment in comments:
        body = comment.get("body") or ""
        for label, target in (("Karar", decisions), ("Sorun", problems), ("Ne oldu", done), ("Ne bitti", done)):
            match = re.search(rf"\*\*{label}:\*\* (.+)", body)
            if match:
                target.append(match.group(1).strip())
    return {"decisions": decisions, "problems": problems, "done": done}


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def minutes(start: datetime | None, end: datetime | None) -> str:
    if not start or not end:
        return "—"
    total = max(0, int((end - start).total_seconds() // 60))
    return f"{total} dk"


def fetch_issue(repo: str, number: int) -> dict:
    issue = json.loads(gh(["api", f"repos/{repo}/issues/{number}"]))
    comments = json.loads(
        gh(["api", f"repos/{repo}/issues/{number}/comments?per_page=100"])
    )
    return {
        "number": number,
        "title": issue.get("title", ""),
        "body": issue.get("body") or "",
        "labels": [item.get("name") for item in issue.get("labels", [])],
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "comments": comments,
        "evidence": parse_evidence(comments),
    }


def collect_usage(since: datetime, until: datetime) -> dict:
    try:
        raw = subprocess.check_output(
            [
                sys.executable,
                str(SCRIPTS / "usage.py"),
                "--since",
                since.isoformat(),
                "--until",
                until.isoformat(),
                "--json",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            cwd=PROJECT,
        )
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return {
            "totals": {},
            "sessions": [],
            "unavailable": [],
            "error": "usage unavailable",
        }


def collect_delta(issue: int) -> dict | None:
    try:
        raw = subprocess.check_output(
            [
                sys.executable,
                str(SCRIPTS / "usage.py"),
                "--delta",
                "--issue",
                str(issue),
                "--json",
            ],
            text=True,
            cwd=PROJECT,
            stderr=subprocess.DEVNULL,
        )
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return None


def collect_commits(since: datetime, until: datetime) -> list[str]:
    try:
        output = subprocess.check_output(
            [
                "git",
                "log",
                f"--since={since.isoformat()}",
                f"--until={until.isoformat()}",
                "--pretty=format:%h %s",
            ],
            text=True,
            cwd=PROJECT,
        )
    except subprocess.CalledProcessError:
        return []
    return [line for line in output.splitlines() if line.strip()]


def build_report(
    issue: dict,
    children: list[dict],
    usage: dict,
    commits: list[str],
    start=None,
    end=None,
    delta: dict | None = None,
) -> str:
    all_items = [issue] + children
    agents = sorted(
        {
            record.get("agent")
            for item in all_items
            for record in item.get("evidence", [])
            if record.get("agent")
        }
    )
    worker_records = []
    for item in all_items:
        for record in item.get("evidence", []):
            if record.get("worker"):
                worker_records.append(record["worker"])
            worker_records.extend(record.get("workers") or [])

    reviewers = sum(
        1
        for item in all_items
        for record in item.get("evidence", [])
        if (record.get("reviews") or {}).get("adversarial", {}).get("reviewer_a") == "approved"
    )

    if not start:
        starts = [parse_ts(item.get("created_at")) for item in all_items]
        start = min((item for item in starts if item), default=None)
    if not end:
        ends = [parse_ts(item.get("updated_at")) for item in all_items]
        end = max((item for item in ends if item), default=None)

    who = []
    if agents:
        who.append(f"1 ana agent (roller: {', '.join(agents)})")
    else:
        who.append("1 ana agent")
    if reviewers:
        who.append(f"{reviewers} reviewer onayı")
    who.append(f"{len(worker_records)} Orca worker" if worker_records else "0 Orca worker")
    if "epic-done" in issue["labels"]:
        who.append("1 insan (onayladı)")
    elif "human-qa" in issue["labels"]:
        who.append("1 insan (onay bekliyor)")

    progress = {"decisions": [], "problems": [], "done": []}
    for item in all_items:
        extracted = extract_progress(item["comments"])
        for key in progress:
            progress[key].extend(extracted[key])

    lines = [
        f"## İş Raporu — #{issue['number']} {issue['title']}",
        "",
        f"**Kim:** {' · '.join(who)}",
        f"**Süre:** {start.strftime('%H:%M') if start else '—'}–{end.strftime('%H:%M') if end else '—'} UTC · {minutes(start, end)}",
        "",
        "**Süreç:**",
        "| İş | Durum | Kim | Süre |",
        "|----|-------|-----|------|",
    ]
    for item in children or [issue]:
        status = next(
            (label for label in ("leaf-done", "epic-done", "human-qa", "executing", "blocked") if label in item["labels"]),
            "—",
        )
        agent = ", ".join(
            sorted({record.get("agent") for record in item.get("evidence", []) if record.get("agent")})
        ) or "—"
        times = [parse_ts(comment.get("created_at")) for comment in item["comments"]]
        times = [time for time in times if time]
        duration = minutes(min(times), max(times)) if times else "—"
        lines.append(f"| #{item['number']} {item['title'][:45]} | {status} | {agent} | {duration} |")

    lines += ["", f"**Ne yapıldı:** {'; '.join(progress['done'][-3:]) or 'Issue/commit kayıtlarına göre tamamlandı.'}"]
    lines.append(f"**Kararlar:** {'; '.join(progress['decisions'][-3:]) or 'Kayıtlı karar yok.'}")
    lines.append(f"**Sorunlar:** {'; '.join(progress['problems'][-3:]) or 'Kayıtlı sorun yok.'}")

    totals = usage.get("totals") or {}
    unavailable = len(usage.get("unavailable") or [])
    measured = int(totals.get("measured_sessions") or 0)
    cost = totals.get("cost")
    if cost is None or measured == 0:
        cost_text = "ölçülemedi"
    else:
        cost_text = f"${cost:.4f}"
        if unavailable or totals.get("confidence") == "partial":
            cost_text += " (kısmi)"
    lines.append(
        f"**Maliyet:** {totals.get('sessions', 0)} oturum · "
        f"{totals.get('input', 0):,} in / {totals.get('output', 0):,} out · "
        f"{totals.get('cache_read', 0):,} cache · {cost_text}"
    )
    if delta:
        tokens = delta.get("tokens") or {}
        lines.append(
            f"Ana oturum (epic): ${delta.get('cost', 0):.4f} · "
            f"{tokens.get('input', 0):,} in / {tokens.get('output', 0):,} out · "
            f"{delta.get('duration_seconds', 0)}s"
        )
    elif totals.get("session_total_cost") is not None:
        lines.append(
            f"Ana oturum toplamı: ${totals['session_total_cost']:.4f} "
            f"({totals.get('session_total_sessions', 0)} oturum; epic'e atfedilemedi)"
        )
    if unavailable or totals.get("confidence") == "partial":
        lines.append("Not: bazı oturumların maliyeti ölçülemedi.")

    details = [f"- Issue: #{item['number']}" for item in all_items]
    details += [f"- Commit: {commit}" for commit in commits]
    for worker in worker_records:
        details.append(
            f"- Worker: {worker.get('task_id')} / {worker.get('dispatch_id')} / {worker.get('outcome')}"
        )
    lines += ["", "**Kanıt:**", "<details>", "<summary>Teknik ayrıntı</summary>", "", *details, "", "</details>"]
    approval = "gerekiyor — epic kapanışı" if "human-qa" in issue["labels"] else "gerekmiyor"
    lines += ["", f"**Onay:** {approval}"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="human work report")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--post", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo = repo_name()
    epic = fetch_issue(repo, args.issue)
    child_numbers = parse_children(epic["body"]) or [args.issue]
    children = [
        fetch_issue(repo, number) for number in child_numbers if number != args.issue
    ]

    end = parse_time(args.until)
    start = parse_time(args.since)
    if not start:
        timestamps = [parse_ts(item["created_at"]) for item in [epic] + children]
        start = min((item for item in timestamps if item), default=datetime.now(timezone.utc))
    if not end:
        timestamps = [parse_ts(item["updated_at"]) for item in [epic] + children]
        end = max((item for item in timestamps if item), default=datetime.now(timezone.utc))

    usage = collect_usage(start, end)
    commits = collect_commits(start, end)
    report = build_report(epic, children, usage, commits, start, end, collect_delta(args.issue))

    if args.json:
        print(json.dumps({"issue": args.issue, "report": report, "usage": usage, "commits": commits}, ensure_ascii=False, indent=2))
    elif args.post:
        subprocess.run(
            [
                "gh",
                "api",
                "-X",
                "POST",
                f"repos/{repo}/issues/{args.issue}/comments",
                "--input",
                "-",
            ],
            input=json.dumps({"body": report}),
            text=True,
            check=True,
            capture_output=True,
        )
        print(f"report: #{args.issue} yorumu yazıldı")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
