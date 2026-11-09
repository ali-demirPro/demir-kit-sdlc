#!/usr/bin/env python3
"""Close stale approval requests with a note instead of blocking forever.

An `update.py --approval yes` comment carries a `demir-kit-request` block with a
deadline. When the deadline passes without a human answer, the sweep writes a
`demir-kit-accept` block with `via: timeout`, drops `human-qa` and keeps the
decision visible on the timeline.

    approval_sweep.py --project .            # dry-run
    approval_sweep.py --project . --apply
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import approvals  # noqa: E402
import cycle  # noqa: E402

REQUEST_RE = re.compile(r"```yaml\s+demir-kit-request\s*\n(.*?)```", re.S)
TIMEOUTS = {"low": 60, "medium": 60, "high": 240, "critical": 0, "irreversible": 0}
LABEL = "approval-timeout"


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def _yaml(text: str) -> dict:
    import yaml

    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def request_block(comments: list[dict]) -> dict | None:
    """Latest request block that carries a deadline."""
    found = None
    for comment in comments:
        match = REQUEST_RE.search(comment.get("body") or "")
        if not match:
            continue
        data = _yaml(match.group(1))
        if data.get("deadline"):
            found = data
    return found


def already_timed_out(comments: list[dict], asked_at: datetime | None) -> bool:
    for comment in comments:
        match = re.search(r"```yaml\s+demir-kit-accept\s*\n(.*?)```", comment.get("body") or "", re.S)
        if not match:
            continue
        if _yaml(match.group(1)).get("via") != "timeout":
            continue
        created = parse_ts(comment.get("created_at"))
        if not asked_at or not created or created >= asked_at:
            return True
    return False


def answered_by_human(comments: list[dict], asked_at: datetime) -> bool:
    for comment in comments:
        if not approvals.is_human(comment):
            continue
        created = parse_ts(comment.get("created_at"))
        if created and created >= asked_at:
            return True
    return False


def decide(
    issue: int,
    comments: list[dict],
    now: datetime | None = None,
    risk: str | None = "low",
    timeouts: dict | None = None,
) -> dict | None:
    if not risk:
        return None
    now = now or datetime.now(timezone.utc)
    request = request_block(comments)
    if not request:
        return None
    asked_at = parse_ts(request.get("asked_at")) or parse_ts(request.get("deadline"))
    if not asked_at:
        return None
    if answered_by_human(comments, asked_at):
        return None
    if already_timed_out(comments, asked_at):
        return None
    policy = (timeouts or TIMEOUTS).get(risk)
    if policy is not None and policy <= 0:
        return None
    block_minutes = request.get("timeout_minutes")
    try:
        block = int(block_minutes)
    except (TypeError, ValueError):
        block = 0
    minutes = max(block, int(policy or 0), 1)
    deadline = asked_at + timedelta(minutes=minutes)
    if now < deadline:
        return None
    return {
        "issue": int(issue),
        "via": "timeout",
        "note": f"{minutes} dakika içinde yanıt gelmedi; not düşülüp devam edildi.",
        "deadline": deadline.isoformat(),
    }


def accept_block(issue: int, note: str) -> str:
    return (
        "```yaml demir-kit-accept\n"
        "decision: accepted\n"
        f"issue: {int(issue)}\n"
        "via: timeout\n"
        f'note: "{note}"\n'
        "by: approval-sweep\n"
        "```\n"
    )


def _gh(args: list[str], repo: str | None = None) -> str:
    command = list(args)
    if repo and command and command[0] == "issue":
        command += ["--repo", repo]
    result = subprocess.run(["gh", *command], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"approval_sweep: gh failed — {result.stderr.strip()}")
    return result.stdout


def apply(issue: int, note: str, repo: str) -> None:
    _gh(["issue", "comment", str(issue), "--body", accept_block(issue, note)], repo)
    _gh(["issue", "edit", str(issue), "--add-label", LABEL], repo)
    _gh(["issue", "edit", str(issue), "--remove-label", "human-qa"], repo)


def record_wait_done(project: Path, issue: int) -> bool:
    """Close an open approval wait in the project's cycle log.

    Called from an epic worktree the log lives in the main checkout, so resolve
    the owning project root instead of writing into the worktree.
    """
    root = cycle.project_root(Path(project), cwd=Path(project))
    return cycle.close_wait(root, int(issue))


def repo_name(project: Path) -> str:
    import yaml

    data = yaml.safe_load((project / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    repo = (data.get("tracker") or {}).get("repo")
    if not repo:
        raise SystemExit("approval_sweep: ecosystem.yaml tracker.repo yok")
    return str(repo)


def risk_of(body: str) -> str | None:
    if "human_gate: irreversible" in body:
        return "irreversible"
    match = re.search(r"```yaml\s+demir-kit\s*\n(.*?)```", body, re.S)
    if not match:
        return None
    level = ((_yaml(match.group(1)).get("risk") or {}).get("level"))
    return str(level) if level else None


def main() -> int:
    parser = argparse.ArgumentParser(description="timeout stale approval requests")
    parser.add_argument("--project", default=".")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    repo = repo_name(project)
    issues = json.loads(
        _gh(["issue", "list", "--repo", repo, "--state", "open",
             "--label", "human-qa", "--limit", "100", "--json", "number,body"])
    )
    now = datetime.now(timezone.utc)
    results = []
    for issue in issues:
        comments = json.loads(
            _gh(["api", f"repos/{repo}/issues/{issue['number']}/comments?per_page=100"])
        )
        decision = decide(
            int(issue["number"]), comments, now=now, risk=risk_of(issue.get("body") or "")
        )
        if not decision:
            continue
        if args.apply:
            apply(decision["issue"], decision["note"], repo)
            record_wait_done(project, decision["issue"])
        results.append(decision)

    if args.json:
        print(json.dumps({"now": now.isoformat(), "applied": bool(args.apply),
                          "results": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print(f"#{item['issue']}: {item['via']} — {item['note']}")
        if not results:
            print("approval_sweep: süresi dolan istek yok")
        elif not args.apply:
            print("(dry-run; yazmak için --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
