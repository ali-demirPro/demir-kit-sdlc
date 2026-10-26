#!/usr/bin/env python3
"""Dependency-aware leaf queue with lease-based claiming."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

SKIP_LABELS = {"executing", "blocked", "deferred", "leaf-done", "epic-done"}
CLAIM_PREFIX = "run claim:"
RELEASE_PREFIX = "run release:"
EVIDENCE_TAG = "demir-kit-evidence"
LEASE_HOURS = 2


def gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"next-leaf: gh failed — {result.stderr.strip()}")
    return result.stdout


def gh_optional(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def parse_seal(body: str) -> dict:
    match = re.search(r"```yaml\s+demir-kit\s*\n(.*?)```", body, re.S)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def comment_id(comment: dict) -> int:
    """Accept REST comments (int id) and GraphQL/node payloads (URL suffix)."""
    for key in ("databaseId", "id"):
        raw = comment.get(key)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    url = comment.get("url") or ""
    match = re.search(r"(?:issuecomment-|/comments/)(\d+)", url)
    if match:
        return int(match.group(1))
    sys.exit("next-leaf: comment id okunamadı (id/url yok)")


def comment_body(comment: dict) -> str:
    return comment.get("body") or ""


def run_id_from(comment: dict) -> str | None:
    match = re.search(r"run claim:\s*`?([^\s`]+)`?", comment_body(comment))
    return match.group(1) if match else None


def lease_until_from(comment: dict) -> datetime | None:
    match = re.search(r"lease_until:\s*`?([^\s`]+)`?", comment_body(comment))
    return parse_time(match.group(1)) if match else None


def fetch_comments(repo: str, number: int, page_size: int = 100) -> list[dict]:
    comments: list[dict] = []
    page = 1
    while True:
        raw = gh(
            [
                "api",
                f"repos/{repo}/issues/{number}/comments?per_page={page_size}&page={page}",
            ]
        )
        try:
            batch = json.loads(raw)
        except json.JSONDecodeError:
            break
        if not isinstance(batch, list) or not batch:
            break
        comments.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return comments


def fetch_issue(number: int) -> dict:
    raw = gh(
        [
            "issue",
            "view",
            str(number),
            "--json",
            "number,title,state,body,labels,assignees,url",
        ]
    )
    data = json.loads(raw)
    if not isinstance(data, dict):
        sys.exit(f"next-leaf: issue #{number} okunamadı")
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/\d+", data.get("url") or "")
    if not match:
        sys.exit(f"next-leaf: issue #{number} repo adresi okunamadı")
    data["comments"] = fetch_comments(
        f"{match.group(1)}/{match.group(2)}", number
    )
    return data


def lease_state(issue: dict, at: datetime | None = None) -> dict:
    """Return the active lease after the latest release, if any."""
    at = at or now()
    comments = sorted(issue.get("comments") or [], key=comment_id)
    releases = [item for item in comments if RELEASE_PREFIX in comment_body(item)]
    cutoff = max((comment_id(item) for item in releases), default=0)
    claims = [
        item
        for item in comments
        if CLAIM_PREFIX in comment_body(item) and comment_id(item) > cutoff
    ]
    if not claims:
        return {"active": None, "expired": False, "evidence_after": []}

    active = min(claims, key=comment_id)
    created = (
        parse_time(active.get("createdAt") or active.get("created_at")) or at
    )
    expires = lease_until_from(active) or created + timedelta(hours=LEASE_HOURS)
    evidence_after = [
        item
        for item in comments
        if comment_id(item) > comment_id(active) and EVIDENCE_TAG in comment_body(item)
    ]
    return {
        "active": active,
        "run_id": run_id_from(active),
        "expires_at": expires,
        "expired": at >= expires,
        "evidence_after": evidence_after,
    }


def claim_winner(issue: dict) -> int | None:
    """Concurrent claims are ordered by comment id; the lowest id wins."""
    comments = sorted(issue.get("comments") or [], key=comment_id)
    releases = [item for item in comments if RELEASE_PREFIX in comment_body(item)]
    cutoff = max((comment_id(item) for item in releases), default=0)
    claims = [
        item
        for item in comments
        if CLAIM_PREFIX in comment_body(item) and comment_id(item) > cutoff
    ]
    return min((comment_id(item) for item in claims), default=None)


def write_snapshot(number: int) -> None:
    snapshot = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "usage.py"),
            "--snapshot",
            "--issue",
            str(number),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )
    if snapshot.returncode != 0:
        print(
            f"next-leaf: usage snapshot skipped — {snapshot.stderr.strip()}",
            file=sys.stderr,
        )


def claim(number: int, epic: int | None, risk: str) -> int:
    issue = fetch_issue(number)
    if issue.get("state") != "OPEN":
        sys.exit(f"next-leaf: #{number} açık değil")

    lease = lease_state(issue)
    if lease.get("active"):
        if not lease["expired"]:
            sys.exit(f"next-leaf: #{number} zaten claim edilmiş (lease aktif)")
        sys.exit(
            f"next-leaf: #{number} lease'i bayat; "
            f"`next-leaf --release --issue {number}` çalıştır"
        )

    run_id = now().strftime("run-%Y%m%dT%H%M%S%fZ")
    expires = now() + timedelta(hours=LEASE_HOURS)
    body = (
        f"run claim: `{run_id}`\n"
        f"lease_until: `{expires.isoformat()}`\n\n"
        f"Epic: #{epic} · risk: {risk}"
    )
    gh(["issue", "comment", str(number), "--body", body])
    gh(["issue", "edit", str(number), "--add-label", "executing"])
    gh_optional(["issue", "edit", str(number), "--add-assignee", "@me"])

    refreshed = fetch_issue(number)
    winner = claim_winner(refreshed)
    ours = next(
        (
            comment_id(item)
            for item in refreshed.get("comments") or []
            if run_id in comment_body(item)
        ),
        None,
    )
    if ours is None or winner != ours:
        gh_optional(["issue", "edit", str(number), "--remove-assignee", "@me"])
        print(f"claim lost: #{number} ({run_id})", file=sys.stderr)
        return 1

    write_snapshot(number)
    print(f"claimed #{number} ({run_id})", file=sys.stderr)
    return 0


def release(number: int, force: bool, reason: str) -> int:
    issue = fetch_issue(number)
    lease = lease_state(issue)
    active = lease.get("active")

    if active and not lease["expired"] and not force:
        sys.exit(
            f"next-leaf: #{number} lease aktif; "
            "`--force --reason \"...\"` olmadan bırakılmaz"
        )
    if active and lease["evidence_after"] and not force:
        sys.exit(
            f"next-leaf: #{number} lease'den sonra evidence var; "
            "`--force --reason \"...\"` olmadan bırakılmaz"
        )

    run_id = lease.get("run_id") or "none"
    gh_optional(["issue", "edit", str(number), "--remove-label", "executing"])
    for assignee in issue.get("assignees") or []:
        login = assignee.get("login")
        if login:
            gh_optional(["issue", "edit", str(number), "--remove-assignee", login])
    gh(
        [
            "issue",
            "comment",
            str(number),
            "--body",
            f"run release: `{run_id}`\nreason: {reason}",
        ]
    )
    print(f"released #{number} ({run_id})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="pick the next executable leaf")
    parser.add_argument("--list", action="store_true", help="all eligible leaves")
    parser.add_argument("--claim", action="store_true", help="claim the first leaf")
    parser.add_argument("--release", action="store_true", help="release a lease")
    parser.add_argument("--issue", type=int, help="issue for --release")
    parser.add_argument("--force", action="store_true", help="force a release")
    parser.add_argument("--reason", default="stale claim", help="release reason")
    parser.add_argument("--json", action="store_true", help="machine output")
    args = parser.parse_args()

    if args.release:
        if not args.issue:
            sys.exit("next-leaf: --release requires --issue N")
        return release(args.issue, args.force, args.reason)

    open_issues = json.loads(
        gh(
            [
                "issue",
                "list",
                "--state",
                "open",
                "--limit",
                "200",
                "--json",
                "number,title,body,labels,createdAt",
            ]
        )
    )
    all_issues = json.loads(
        gh(
            [
                "issue",
                "list",
                "--state",
                "all",
                "--limit",
                "1000",
                "--json",
                "number,state,labels",
            ]
        )
    )
    done: set[int] = set()
    for item in all_issues:
        labels = {label["name"] for label in item.get("labels", [])}
        if item["state"] == "CLOSED" or labels & {"leaf-done", "epic-done", "deferred"}:
            done.add(item["number"])

    executing_epics: set[int] = set()
    for issue in open_issues:
        labels = {label["name"] for label in issue["labels"]}
        if "executing" in labels:
            seal = parse_seal(issue.get("body", ""))
            if seal.get("epic"):
                executing_epics.add(seal["epic"])

    eligible = []
    for issue in open_issues:
        labels = {label["name"] for label in issue["labels"]}
        if "agent-approved" not in labels or labels & SKIP_LABELS:
            continue
        seal = parse_seal(issue.get("body", ""))
        if not seal:
            continue
        deps = [
            dep
            for dep in seal.get("dependencies") or []
            if isinstance(dep, dict) and dep.get("kind", "blocks") == "blocks"
        ]
        if any(dep.get("issue") not in done for dep in deps):
            continue
        epic = seal.get("epic")
        if epic and epic in executing_epics:
            continue
        eligible.append(
            {
                "number": issue["number"],
                "title": issue["title"],
                "epic": epic,
                "risk": (seal.get("risk") or {}).get("level", "low"),
                "createdAt": issue["createdAt"],
            }
        )

    eligible.sort(key=lambda item: item["createdAt"])
    if not eligible:
        if args.json:
            print("[]")
        else:
            print("no work")
        return 0

    if args.json and not args.claim:
        print(json.dumps(eligible, indent=2))
        return 0

    if args.list and not args.claim:
        for item in eligible:
            print(f"#{item['number']}  {item['title']}  [{item['risk']}]")
        return 0

    if args.claim:
        target = None
        if args.issue:
            target = next(
                (item for item in eligible if item["number"] == args.issue), None
            )
            if not target:
                sys.exit(f"next-leaf: #{args.issue} uygun değil")
        else:
            target = eligible[0]
        status = claim(target["number"], target["epic"], target["risk"])
        if status == 0:
            print(target["number"])
        return status

    print(eligible[0]["number"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
