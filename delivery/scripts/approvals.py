#!/usr/bin/env python3
"""Human approval parsing for epic/leaf gates.

Approvals may carry a ``binding_sha256`` digest over the issue seal and the
``binding_base`` commit the human approved against. A seal edited after the
fact, or a base commit that is no longer an ancestor of HEAD, invalidates the
approval. Short ``binding_base`` shas resolve to the full 40-char commit before
hashing, so producers and validators agree. Records without the digest stay
valid for backward compatibility.
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
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")


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


def resolve_commit(value: str, root: Path) -> str | None:
    result = _git(["rev-parse", "--verify", f"{value}^{{commit}}"], root)
    return result.strip() if result else None


def canonical_base(base_commit: str, root: Path | str = ".") -> str:
    """Full 40-char sha of ``base_commit``; the raw value when unresolvable.

    Approval producers and validators share this helper, so a short sha in
    ``binding_base`` hashes to the same value as the full sha it names.
    """
    value = str(base_commit or "").strip()
    if not value:
        return ""
    return resolve_commit(value, Path(root)) or value


def _payload_digest(body: str, base_text: str) -> str:
    payload = json.dumps(
        {"body": _canonical_seal(body), "base": base_text},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def binding_digest(body: str, base_commit: str, root: Path | str = ".") -> str:
    """Canonical sha256 over the issue seal and the approved base commit."""
    return _payload_digest(body, canonical_base(base_commit, root))


def is_ancestor(commit: str, head: str, root: Path) -> bool:
    """True when ``commit`` is an ancestor of (or equal to) ``head``."""
    if not (COMMIT_RE.fullmatch(commit or "") and COMMIT_RE.fullmatch(head or "")):
        return False
    return _git(["merge-base", "--is-ancestor", commit, head], root) is not None


def head_commit(root: Path) -> str | None:
    return resolve_commit("HEAD", root)


def _binding_of(block: dict) -> str:
    return str(block.get("binding_sha256") or "").strip()


def _base_of(block: dict) -> str:
    value = block.get("binding_base")
    return "" if value is None else str(value).strip()


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
            "binding_base": _base_of(block),
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
            "binding_base": _base_of(block),
            "approved_at": comment.get("created_at") or comment.get("createdAt"),
        }
    return found if found and found.get("decision") == "accepted" else None


def _mismatch(acceptance: dict, recorded: str, actual: str, detail: str) -> dict:
    return {
        "state": "mismatch",
        "recorded": recorded,
        "actual": actual,
        "base": acceptance.get("binding_base"),
        "by": acceptance.get("by"),
        "approved_at": acceptance.get("approved_at"),
        "detail": detail,
    }


def approval_binding(
    body: str,
    comments: list[dict],
    issue: int | str,
    root: Path | str = ".",
) -> dict:
    """Compare the latest human acceptance with the current seal and HEAD.

    States: ``none`` (no human acceptance), ``legacy`` (record without a
    digest), ``bound`` (digest matches and the base commit is an ancestor of
    HEAD) and ``mismatch`` (stale approval). Live changed files never enter the
    comparison; only the seal and the approved base commit do. A digest over the
    raw short ``binding_base`` (produced before canonical hashing) stays bound
    for backward compatibility.
    """
    root = Path(root)
    acceptance = human_acceptance_for(comments, issue)
    if not acceptance:
        return {"state": "none", "detail": "insan kabulü yok"}
    recorded = str(acceptance.get("binding_sha256") or "")
    if not recorded:
        return {"state": "legacy", "detail": "digest taşımayan eski onay"}
    base = str(acceptance.get("binding_base") or "").strip()
    actual = binding_digest(body, base, root)
    if not BINDING_RE.fullmatch(recorded):
        return _mismatch(
            acceptance, recorded, actual, "onay digest'i sha256 biçiminde değil"
        )
    if not base:
        return _mismatch(
            acceptance, recorded, actual, "onay taban commit taşımıyor"
        )
    if not COMMIT_RE.fullmatch(base):
        return _mismatch(
            acceptance, recorded, actual, "onay taban commit'i sha biçiminde değil"
        )
    resolved = resolve_commit(base, root)
    if not resolved:
        return _mismatch(
            acceptance,
            recorded,
            actual,
            "onay taban commit'i çözülemedi — HEAD'in atası değil",
        )
    actual = _payload_digest(body, resolved)
    if recorded != actual and recorded != _payload_digest(body, base):
        return _mismatch(
            acceptance, recorded, actual, "onay digest'i güncel seal gövdesiyle uyuşmuyor"
        )
    head = head_commit(root)
    if not head or not is_ancestor(resolved, head, root):
        return _mismatch(
            acceptance, recorded, actual, "onay taban commit'i HEAD'in atası değil"
        )
    return {
        "state": "bound",
        "recorded": recorded,
        "actual": actual,
        "base": base,
        "by": acceptance.get("by"),
        "approved_at": acceptance.get("approved_at"),
        "detail": "onay digest'i ve taban commit güncel",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="approval binding digest")
    sub = parser.add_subparsers(dest="command", required=True)

    digest_p = sub.add_parser("digest", help="print the binding digest")
    digest_p.add_argument("--body-file", type=Path, required=True)
    digest_p.add_argument("--root", type=Path, default=Path("."))
    digest_p.add_argument(
        "--base", default="HEAD", help="onay anındaki taban commit (varsayılan HEAD)"
    )

    check_p = sub.add_parser("check-binding", help="exit 1 on a stale approval")
    check_p.add_argument("--issue", type=int, required=True)
    check_p.add_argument("--body-file", type=Path, required=True)
    check_p.add_argument("--comments-file", type=Path, required=True)
    check_p.add_argument("--root", type=Path, default=Path("."))
    check_p.add_argument("--quiet", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "digest":
        base = resolve_commit(args.base, args.root)
        if not base:
            print(
                f"approvals: taban commit çözülemedi: {args.base}",
                file=sys.stderr,
            )
            return 1
        print(binding_digest(args.body_file.read_text(encoding="utf-8"), base, args.root))
        return 0

    body = args.body_file.read_text(encoding="utf-8")
    comments = _load_comments(args.comments_file)
    result = approval_binding(body, comments, args.issue, args.root)
    stale = result.get("state") == "mismatch"
    if not args.quiet or stale:
        print(json.dumps(result, ensure_ascii=False))
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
