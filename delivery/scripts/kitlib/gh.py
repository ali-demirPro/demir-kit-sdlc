"""``gh`` CLI templates and pagination shared by delivery scripts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable, Iterable


class GhError(RuntimeError):
    """A ``gh`` call failed; callers keep their own message prefix."""

    def __init__(self, args: Iterable[str], stderr: str = "") -> None:
        self.gh_args = [str(item) for item in args]
        self.stderr = str(stderr or "").strip()
        super().__init__(self.stderr or "gh failed")


def capture(
    args: Iterable[str],
    *,
    optional: bool = False,
    cwd: Path | None = None,
) -> str:
    """Run ``gh`` and return stdout.

    ``optional`` turns any failure into an empty string, matching the silent
    best-effort calls scripts used for labels and assignees.
    """
    command = ["gh", *[str(item) for item in args]]
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError) as exc:
        if optional:
            return ""
        raise GhError(args, str(exc)) from exc
    if result.returncode != 0:
        if optional:
            return ""
        raise GhError(args, result.stderr)
    return result.stdout


def issue_view_args(number: int, fields: str) -> list[str]:
    return ["issue", "view", str(number), "--json", fields]


def issue_list_args(state: str, limit: int, fields: str) -> list[str]:
    return ["issue", "list", "--state", state, "--limit", str(limit), "--json", fields]


def issue_comment_args(number: int, body: str) -> list[str]:
    return ["issue", "comment", str(number), "--body", body]


def issue_edit_args(number: int, *flags: str) -> list[str]:
    return ["issue", "edit", str(number), *flags]


def api_args(path: str) -> list[str]:
    return ["api", path]


def issue_comments_args(
    repo: str, number: int, page: int = 1, page_size: int = 100
) -> list[str]:
    return [
        "api",
        f"repos/{repo}/issues/{number}/comments?per_page={page_size}&page={page}",
    ]


def timeline_args(
    repo: str, issue: int, page: int = 1, page_size: int = 100
) -> list[str]:
    return [
        "api",
        f"repos/{repo}/issues/{issue}/timeline?per_page={page_size}&page={page}",
    ]


def _paginate(
    build: Callable[[int], list[str]],
    request: Callable[[list[str]], str],
    page_size: int,
) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        raw = request(build(page))
        try:
            batch = json.loads(raw)
        except json.JSONDecodeError:
            break
        if not isinstance(batch, list) or not batch:
            break
        rows.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < page_size:
            break
        page += 1
    return rows


def issue_comments(
    repo: str,
    number: int,
    page_size: int = 100,
    request: Callable[[list[str]], str] | None = None,
) -> list[dict]:
    """Every comment on an issue, page by page."""
    return _paginate(
        lambda page: issue_comments_args(repo, number, page, page_size),
        request or capture,
        page_size,
    )


def timeline(
    repo: str,
    issue: int,
    page_size: int = 100,
    request: Callable[[list[str]], str] | None = None,
) -> list[dict]:
    """Every timeline event on an issue, page by page."""
    return _paginate(
        lambda page: timeline_args(repo, issue, page, page_size),
        request or capture,
        page_size,
    )
