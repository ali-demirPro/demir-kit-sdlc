#!/usr/bin/env python3
"""Dependency-aware leaf queue for demir-kit delivery."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

SKIP_LABELS = {"executing", "blocked", "deferred", "leaf-done", "epic-done"}


def gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"next-leaf: gh failed — {result.stderr.strip()}")
    return result.stdout


def parse_seal(body: str) -> dict:
    match = re.search(r"```yaml\s+demir-kit\s*\n(.*?)```", body, re.S)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="pick the next executable leaf")
    parser.add_argument("--list", action="store_true", help="all eligible leaves")
    parser.add_argument("--claim", action="store_true", help="claim the first leaf")
    parser.add_argument("--json", action="store_true", help="machine output")
    args = parser.parse_args()

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

    if args.json:
        print(json.dumps(eligible, indent=2))
    elif args.list:
        for item in eligible:
            print(f"#{item['number']}  {item['title']}  [{item['risk']}]")
    else:
        first = eligible[0]
        print(first["number"])
        if args.claim:
            run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
            gh(["issue", "edit", str(first["number"]), "--add-label", "executing", "--add-assignee", "@me"])
            gh(
                [
                    "issue",
                    "comment",
                    str(first["number"]),
                    "--body",
                    f"run claim: `{run_id}`\n\nEpic: #{first['epic']} · risk: {first['risk']}",
                ]
            )
            snapshot = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parent / "usage.py"),
                    "--snapshot",
                    "--issue",
                    str(first["number"]),
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
            print(f"claimed #{first['number']} ({run_id})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
