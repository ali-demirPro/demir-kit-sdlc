#!/usr/bin/env python3
"""Approval-binding and evidence-ancestry checks split from doctor.py.

`check_issue_extras` returns error strings for `doctor --issue`; the caller owns
printing. Records without a `binding_sha256` stay valid (backward compatible).
Evidence commits must be ancestors of HEAD, not equal to it, so a later
checkpoint's commits do not invalidate an earlier checkpoint's evidence.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

import approvals as approvals_lib
import evidence as evidence_lib

EVIDENCE_RE = re.compile(r"```yaml\s+demir-kit-evidence\s*\n(.*?)```", re.S)


def check_binding(
    number: int, body: str, comments: list[dict], root: Path
) -> list[str]:
    result = approvals_lib.approval_binding(body, comments, number, root)
    if result.get("state") != "mismatch":
        return []
    return [
        f"issue #{number}: onay geçersiz — {result.get('detail')} "
        f"(kayıtlı {result.get('recorded')}, güncel {result.get('actual')})"
    ]


def evidence_head_errors(
    comments: list[dict], root: Path, evidence_text: str | None = None
) -> list[str]:
    """Evidence commits must be ancestors of HEAD when the issue is validated.

    ``evidence_text`` carries a record passed via ``doctor --evidence``; it is
    checked with the same ancestry rule as commented evidence.
    """
    head = evidence_lib.head_commit(root)
    errors: list[str] = []
    bodies = (
        [evidence_text]
        if evidence_text is not None
        else [comment.get("body") or "" for comment in comments]
    )
    for body in bodies:
        for raw in EVIDENCE_RE.findall(body):
            try:
                record = yaml.safe_load(raw) or {}
            except yaml.YAMLError:
                continue
            if not isinstance(record, dict):
                continue
            verification = record.get("verification")
            if not isinstance(verification, dict):
                continue
            commit = str(verification.get("commit") or "").strip()
            if not commit:
                continue
            cp_id = record.get("cp_id") or "evidence"
            if not evidence_lib.commit_exists(commit, root):
                errors.append(f"{cp_id}: verification — evidence.commit çözülemedi")
                continue
            if not head or not evidence_lib.is_ancestor(commit, head, root):
                errors.append(
                    f"{cp_id}: verification — evidence.commit HEAD'in atası değil"
                )
    return errors


def check_issue_extras(
    number: int,
    body: str,
    comments: list[dict],
    root: Path,
    evidence_text: str | None = None,
) -> list[str]:
    return check_binding(number, body, comments, root) + evidence_head_errors(
        comments, root, evidence_text
    )


if __name__ == "__main__":
    raise SystemExit("doctor_approval: library module")
