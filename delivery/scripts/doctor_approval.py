#!/usr/bin/env python3
"""Approval-binding and evidence-HEAD checks split from doctor.py.

`check_issue_extras` returns error strings for `doctor --issue`; the caller owns
printing. Records without a `binding_sha256` stay valid (backward compatible).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

import approvals as approvals_lib
import evidence as evidence_lib

EVIDENCE_RE = re.compile(r"```yaml\s+demir-kit-evidence\s*\n(.*?)```", re.S)


def changed_files(root: Path) -> list[str]:
    return approvals_lib.changed_files(root)


def check_binding(
    number: int, body: str, comments: list[dict], root: Path
) -> list[str]:
    result = approvals_lib.approval_binding(
        body, changed_files(root), comments, number
    )
    if result.get("state") != "mismatch":
        return []
    return [
        f"issue #{number}: onay geçersiz — {result.get('detail')} "
        f"(kayıtlı {result.get('recorded')}, güncel {result.get('actual')})"
    ]


def evidence_head_errors(comments: list[dict], root: Path) -> list[str]:
    """Evidence commits must match HEAD when the issue is validated."""
    errors: list[str] = []
    for comment in comments:
        for raw in EVIDENCE_RE.findall(comment.get("body") or ""):
            try:
                record = yaml.safe_load(raw) or {}
            except yaml.YAMLError:
                continue
            if not isinstance(record, dict):
                continue
            verification = record.get("verification")
            if not isinstance(verification, dict):
                continue
            commit = str(verification.get("commit") or "")
            if not commit or not evidence_lib.resolve_commit(commit, root):
                continue
            if not evidence_lib.is_head(commit, root):
                cp_id = record.get("cp_id") or "evidence"
                errors.append(
                    f"{cp_id}: verification — evidence.commit HEAD ile aynı değil"
                )
    return errors


def check_issue_extras(
    number: int, body: str, comments: list[dict], root: Path
) -> list[str]:
    return check_binding(number, body, comments, root) + evidence_head_errors(
        comments, root
    )


if __name__ == "__main__":
    raise SystemExit("doctor_approval: library module")
