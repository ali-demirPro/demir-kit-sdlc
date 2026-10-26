#!/usr/bin/env python3
"""Build and verify demir-kit evidence v3 verification blocks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def git(args: list[str], root: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True
    )


def hash_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def commit_exists(commit: str, root: Path = ROOT) -> bool:
    if not COMMIT_RE.fullmatch(commit or ""):
        return False
    return git(["cat-file", "-e", f"{commit}^{{commit}}"], root).returncode == 0


def resolve_commit(value: str, root: Path = ROOT) -> str | None:
    result = git(["rev-parse", value], root)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def diff_hash(commit: str, root: Path = ROOT) -> str | None:
    """Hash the binary diff of a commit; root commits use `git show`."""
    result = git(["diff", "--binary", f"{commit}^", commit], root)
    if result.returncode != 0:
        result = git(["show", "--binary", "--format=", commit], root)
    if result.returncode != 0:
        return None
    return hash_text(result.stdout)


def ci_status(repo: str, run_id: str) -> dict | None:
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/actions/runs/{run_id}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def verify(
    record: dict,
    root: Path = ROOT,
    repo: str | None = None,
    risk: str = "low",
    implementer: str | None = None,
    ci_check: bool = True,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["verification mapping değil"]

    commit = str(record.get("commit") or "")
    if not commit_exists(commit, root):
        errors.append(f"commit bulunamadı: {commit or 'yok'}")

    expected = diff_hash(commit, root) if commit_exists(commit, root) else None
    recorded_diff = str(record.get("diff_hash") or "")
    if not HASH_RE.fullmatch(recorded_diff):
        errors.append("diff_hash sha256 biçiminde değil")
    elif expected and recorded_diff != expected:
        errors.append("diff_hash commit ile eşleşmiyor")

    ci = record.get("ci") if isinstance(record.get("ci"), dict) else {}
    status = ci.get("status")
    if status == "success":
        run_id = str(ci.get("run_id") or "")
        if not run_id:
            errors.append("CI success için run_id yok")
        elif not repo:
            errors.append("CI doğrulaması için repo yok")
        elif ci_check:
            info = ci_status(repo, run_id)
            if not info:
                errors.append(f"CI run bulunamadı: {run_id}")
            else:
                head = str(info.get("head_sha") or "")
                if not head.startswith(commit):
                    errors.append("CI run farklı commit'te")
                if info.get("conclusion") != "success":
                    errors.append("CI run success değil")
    elif status == "skipped":
        if not str(ci.get("reason") or "").strip():
            errors.append("CI skipped için reason yok")
        if risk in {"high", "critical"}:
            errors.append(f"risk {risk} için CI skipped kabul edilmez")
    else:
        errors.append("CI status success veya skipped olmalı")

    reviewers = record.get("reviewers")
    reviewers = reviewers if isinstance(reviewers, list) else []
    minimum = 2 if risk in {"high", "critical"} else 1
    if len(reviewers) < minimum:
        errors.append(f"en az {minimum} reviewer kaydı gerekli")
    seen: set[str] = set()
    for index, reviewer in enumerate(reviewers, 1):
        if not isinstance(reviewer, dict):
            errors.append(f"reviewer {index} mapping değil")
            continue
        for key in ("role", "id", "model", "prompt_hash", "diff_hash"):
            if not str(reviewer.get(key) or "").strip():
                errors.append(f"reviewer {index}: {key} yok")
        reviewer_id = str(reviewer.get("id") or "")
        if reviewer_id and reviewer_id in seen:
            errors.append(f"reviewer id tekrarlı: {reviewer_id}")
        seen.add(reviewer_id)
        if implementer and reviewer_id == implementer:
            errors.append("reviewer uygulayıcıyla aynı")
        prompt_hash = str(reviewer.get("prompt_hash") or "")
        if prompt_hash and not HASH_RE.fullmatch(prompt_hash):
            errors.append(f"reviewer {index}: prompt_hash sha256 değil")
        reviewer_diff = str(reviewer.get("diff_hash") or "")
        if reviewer_diff and not HASH_RE.fullmatch(reviewer_diff):
            errors.append(f"reviewer {index}: diff_hash sha256 değil")
        elif expected and reviewer_diff != expected:
            errors.append(f"reviewer {index}: farklı diff'i incelemiş")

    return errors


def build(
    commit: str,
    implementer: str | None,
    ci_run: str | None,
    ci_skipped: str | None,
    reviewers: list[str],
    root: Path = ROOT,
) -> dict:
    resolved = resolve_commit(commit, root)
    if not resolved:
        raise ValueError(f"commit çözülemedi: {commit}")
    expected = diff_hash(resolved, root)
    if not expected:
        raise ValueError(f"diff hash hesaplanamadı: {resolved}")

    if ci_run:
        ci = {"status": "success", "run_id": ci_run}
    elif ci_skipped:
        ci = {"status": "skipped", "reason": ci_skipped}
    else:
        raise ValueError("--ci-run veya --ci-skipped gerekli")

    parsed: list[dict] = []
    for raw in reviewers:
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"reviewer JSON geçersiz: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError("reviewer JSON object olmalı")
        if not item.get("diff_hash"):
            item["diff_hash"] = expected
        parsed.append(item)

    return {
        "commit": resolved,
        "diff_hash": expected,
        "ci": ci,
        "reviewers": parsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="build evidence v3 verification")
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--implementer")
    parser.add_argument("--ci-run")
    parser.add_argument("--ci-skipped")
    parser.add_argument("--reviewer", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        data = build(
            args.commit,
            args.implementer,
            args.ci_run,
            args.ci_skipped,
            args.reviewer,
        )
    except ValueError as exc:
        sys.exit(f"evidence: {exc}")

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("verification:")
        print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
