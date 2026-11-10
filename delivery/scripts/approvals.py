#!/usr/bin/env python3
"""Human approval parsing for epic/leaf gates.

Approvals may carry a ``binding_sha256`` digest over the issue seal plus the
changed-file list, so a body or diff edit after the fact invalidates the
approval. Records without the field stay valid for backward compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ACCEPT_RE = re.compile(r"```yaml\s+demir-kit-accept\s*\n(.*?)```", re.S)
SEAL_RE = re.compile(r"```yaml\s+demir-kit\s*\n(.*?)```", re.S)
HUMAN_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
BINDING_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


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


def _canonical_seal(body: str) -> str:
    """Canonical text of the ``demir-kit`` seal block; formatting-independent."""
    match = SEAL_RE.search(body or "")
    text = match.group(1) if match else (body or "")
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return text.strip()
    if not isinstance(data, dict):
        return text.strip()
    return yaml.safe_dump(data, sort_keys=True, allow_unicode=True).strip()


def normalize_files(files) -> list[str]:
    """Sorted, deduplicated, slash-normalised file list."""
    items = {
        str(item).replace("\\", "/").strip()
        for item in files or []
        if str(item).strip()
    }
    return sorted(items)


def binding_digest(body: str, files) -> str:
    """Canonical sha256 over the issue seal and the changed-file list."""
    payload = json.dumps(
        {"body": _canonical_seal(body), "files": normalize_files(files)},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git(args: list[str], root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotePath=false", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None
    return result.stdout if result.returncode == 0 else None


def _git_names(args: list[str], root: Path) -> list[str]:
    raw = _git([*args, "-z"], root)
    if raw is None:
        return []
    return [item.strip("\n") for item in raw.split("\0") if item.strip("\n")]


def changed_files(root: Path | str = ".") -> list[str]:
    """Union of branch, staged/worktree and untracked changes, sorted."""
    root = Path(root)
    base = _git(["merge-base", "origin/main", "HEAD"], root)
    if base is None:
        base = _git(["rev-list", "--max-parents=0", "-1", "HEAD"], root)
    paths: set[str] = set()
    if base:
        paths.update(_git_names(["diff", "--name-only", f"{base.strip()}...HEAD"], root))
    paths.update(_git_names(["diff", "--name-only", "HEAD"], root))
    paths.update(_git_names(["ls-files", "--others", "--exclude-standard"], root))
    return sorted(paths)


def _binding_of(block: dict) -> str:
    return str(block.get("binding_sha256") or "").strip()


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
            "binding_sha256": _binding_of(block),
            "approved_at": comment.get("created_at") or comment.get("createdAt"),
        }
    return found


def human_acceptance(comments: list[dict], epic: int | str) -> dict | None:
    """Return the latest human decision only when it is an acceptance."""
    found = latest_human_decision(comments, epic)
    return found if found and found.get("decision") == "accepted" else None


def human_acceptance_for(comments: list[dict], issue: int | str) -> dict | None:
    """Latest human accept/reject block for an issue; acceptance only.

    Leaf comments use ``issue``; epic comments historically use ``epic``.
    Only the latest eligible block counts, so a later reject revokes an
    earlier acceptance.
    """
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
            if int(block.get("issue")) != int(issue):
                continue
        except (TypeError, ValueError):
            continue
        author = login(comment)
        if not block.get("by") or str(block["by"]) != author:
            continue
        found = {
            "issue": int(issue),
            "by": author,
            "association": association(comment),
            "decision": decision,
            "comment_id": comment.get("id") or comment.get("url"),
            "body": comment.get("body"),
            "binding_sha256": _binding_of(block),
            "approved_at": comment.get("created_at") or comment.get("createdAt"),
        }
    return found if found and found.get("decision") == "accepted" else None


def approval_binding(
    body: str,
    files,
    comments: list[dict],
    issue: int | str,
) -> dict:
    """Compare the latest human acceptance digest with the current state.

    States: ``none`` (no human acceptance), ``legacy`` (record without a
    digest), ``bound`` (digest matches) and ``mismatch`` (stale approval).
    """
    acceptance = human_acceptance_for(comments, issue)
    if not acceptance:
        return {"state": "none", "detail": "insan kabulü yok"}
    recorded = str(acceptance.get("binding_sha256") or "")
    if not recorded:
        return {"state": "legacy", "detail": "digest taşımayan eski onay"}
    if not BINDING_RE.fullmatch(recorded):
        return {
            "state": "mismatch",
            "recorded": recorded,
            "actual": binding_digest(body, files),
            "by": acceptance.get("by"),
            "approved_at": acceptance.get("approved_at"),
            "detail": "onay digest'i sha256 biçiminde değil",
        }
    actual = binding_digest(body, files)
    if recorded != actual:
        return {
            "state": "mismatch",
            "recorded": recorded,
            "actual": actual,
            "by": acceptance.get("by"),
            "approved_at": acceptance.get("approved_at"),
            "detail": "onay digest'i güncel seal + dosya listesiyle uyuşmuyor",
        }
    return {
        "state": "bound",
        "recorded": recorded,
        "actual": actual,
        "by": acceptance.get("by"),
        "approved_at": acceptance.get("approved_at"),
        "detail": "onay digest'i güncel",
    }


def _load_comments(path: Path) -> list[dict]:
    """Read comments JSON; supports concatenated pages from gh --paginate."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    decoder = json.JSONDecoder()
    index = 0
    items: list[dict] = []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        try:
            value, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            return []
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            items.append(value)
    return items


def _read_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="approval binding digest")
    sub = parser.add_subparsers(dest="command", required=True)

    digest_p = sub.add_parser("digest", help="print the binding digest")
    digest_p.add_argument("--body-file", type=Path, required=True)
    digest_p.add_argument("--root", type=Path, default=Path("."))
    digest_p.add_argument("--files-file", type=Path)

    check_p = sub.add_parser("check-binding", help="exit 1 on a stale approval")
    check_p.add_argument("--issue", type=int, required=True)
    check_p.add_argument("--body-file", type=Path, required=True)
    check_p.add_argument("--comments-file", type=Path, required=True)
    check_p.add_argument("--root", type=Path, default=Path("."))
    check_p.add_argument("--files-file", type=Path)
    check_p.add_argument("--quiet", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "digest":
        files = (
            _read_lines(args.files_file)
            if args.files_file
            else changed_files(args.root)
        )
        print(binding_digest(args.body_file.read_text(encoding="utf-8"), files))
        return 0

    body = args.body_file.read_text(encoding="utf-8")
    comments = _load_comments(args.comments_file)
    files = (
        _read_lines(args.files_file)
        if args.files_file
        else changed_files(args.root)
    )
    result = approval_binding(body, files, comments, args.issue)
    stale = result.get("state") == "mismatch"
    if not args.quiet or stale:
        print(json.dumps(result, ensure_ascii=False))
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
