"""Issue comment identity and posting helpers."""

from __future__ import annotations

import json
import re
import subprocess


def comment_id(comment: dict) -> int:
    """Accept REST comments (int id) and GraphQL/node payloads (URL suffix)."""
    for key in ("databaseId", "id"):
        raw = comment.get(key)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    match = re.search(
        r"(?:issuecomment-|/comments/)(\d+)", comment.get("url") or ""
    )
    if match:
        return int(match.group(1))
    raise ValueError("comment id okunamadı (id/url yok)")


def body(comment: dict) -> str:
    return comment.get("body") or ""


def post(repo: str, issue: int, text: str) -> str | None:
    """Post one issue comment through the API; return its id when readable."""
    result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{repo}/issues/{issue}/comments",
            "--input",
            "-",
        ],
        capture_output=True,
        text=True,
        input=json.dumps({"body": text}),
    )
    if result.returncode != 0:
        return None
    try:
        return str(json.loads(result.stdout).get("id") or "")
    except json.JSONDecodeError:
        return None


def delete(repo: str, comment_id: str) -> bool:
    result = subprocess.run(
        ["gh", "api", "-X", "DELETE", f"repos/{repo}/issues/comments/{comment_id}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
