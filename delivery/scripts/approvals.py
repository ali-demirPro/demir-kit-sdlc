#!/usr/bin/env python3
"""Human approval parsing for epic/leaf gates."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ACCEPT_RE = re.compile(r"```yaml\s+demir-kit-accept\s*\n(.*?)```", re.S)
HUMAN_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


def login(comment: dict) -> str:
    user = comment.get("user") or comment.get("author") or {}
    return str(user.get("login") or "")


def association(comment: dict) -> str:
    return str(
        comment.get("author_association") or comment.get("authorAssociation") or ""
    )


def is_human(comment: dict) -> bool:
    name = login(comment)
    if not name or name.endswith("[bot]"):
        return False
    if name in {"github-actions", "dependabot", "renovate"}:
        return False
    return association(comment) in HUMAN_ASSOCIATIONS


def acceptance_block(comment: dict) -> dict | None:
    match = ACCEPT_RE.search(comment.get("body") or "")
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def latest_human_decision(comments: list[dict], epic: int | str) -> dict | None:
    """Latest human accept/reject block for an epic; author is authoritative."""
    found = None
    for comment in comments:
        if not is_human(comment):
            continue
        block = acceptance_block(comment)
        if not block:
            continue
        decision = block.get("decision")
        if decision not in {"accepted", "rejected"}:
            continue
        try:
            if int(block.get("epic")) != int(epic):
                continue
        except (TypeError, ValueError):
            continue
        author = login(comment)
        if not block.get("by") or str(block["by"]) != author:
            continue
        found = {
            "epic": int(epic),
            "by": author,
            "association": association(comment),
            "decision": decision,
            "comment_id": comment.get("id") or comment.get("url"),
            "body": comment.get("body"),
        }
    return found


def human_acceptance(comments: list[dict], epic: int | str) -> dict | None:
    """Return the latest human decision only when it is an acceptance."""
    found = latest_human_decision(comments, epic)
    return found if found and found.get("decision") == "accepted" else None


def main() -> int:
    print("approvals: library module", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
