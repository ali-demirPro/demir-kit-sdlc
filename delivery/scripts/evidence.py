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
PLACEHOLDER_RE = re.compile(r"^reviewer[_-][a-z]$", re.I)
STRICT_SINCE = "2026-11-08T09:00:00+00:00"
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


def fetch_commit(commit: str, root: Path = ROOT) -> bool:
    """Fetch one commit from origin so a branch-only commit can be verified.

    Epic leaves close before the epic branch is merged, so a CI checkout of the
    default branch may not carry the commit object. Fetching keeps diff_hash
    verification intact instead of trusting a remote existence check.
    """
    if not COMMIT_RE.fullmatch(commit or ""):
        return False
    try:
        result = subprocess.run(
            ["git", "fetch", "--no-tags", "origin", commit],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and commit_exists(commit, root)


def resolve_commit(value: str, root: Path = ROOT) -> str | None:
    result = git(["rev-parse", value], root)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def head_commit(root: Path = ROOT) -> str | None:
    return resolve_commit("HEAD", root)


def is_head(commit: str, root: Path = ROOT) -> bool:
    """True when ``commit`` resolves to the checkout's HEAD."""
    resolved = resolve_commit(commit, root)
    head = head_commit(root)
    return bool(resolved and head and resolved == head)


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


def is_ancestor(base: str, after: str, root: Path = ROOT) -> bool:
    if not (COMMIT_RE.fullmatch(base or "") and COMMIT_RE.fullmatch(after or "")):
        return False
    return git(["merge-base", "--is-ancestor", base, after], root).returncode == 0


def changed_files(base: str, after: str, root: Path = ROOT) -> int | None:
    """Files changed between two commits, or None when the range is unreadable."""
    if not (COMMIT_RE.fullmatch(base or "") and COMMIT_RE.fullmatch(after or "")):
        return None
    result = git(["diff", "--name-only", "--no-renames", f"{base}..{after}"], root)
    if result.returncode != 0:
        return None
    return len([line for line in result.stdout.splitlines() if line.strip()])


def commit_count(base: str, after: str, root: Path = ROOT) -> int | None:
    """Commits between base..after, or None when the range is unreadable."""
    resolved_base = resolve_commit(base, root)
    resolved_after = resolve_commit(after, root)
    if not resolved_base or not resolved_after:
        return None
    result = git(["rev-list", "--count", f"{resolved_base}..{resolved_after}"], root)
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip() or "0")
    except ValueError:
        return None


def range_diff_hash(base: str, after: str, root: Path = ROOT) -> str | None:
    """Hash the whole baseline..after diff; reviewers must review this range."""
    resolved_base = resolve_commit(base, root)
    resolved_after = resolve_commit(after, root)
    if not resolved_base or not resolved_after:
        return None
    result = git(["diff", "--binary", f"{resolved_base}..{resolved_after}"], root)
    if result.returncode != 0:
        return None
    return hash_text(result.stdout)


def verify_refactor(
    block,
    root: Path = ROOT,
    repo: str | None = None,
    commit: str | None = None,
) -> list[str]:
    """Refactor proof: behavior unchanged between a baseline and an after commit."""
    errors: list[str] = []
    if not isinstance(block, dict):
        return ["refactor bloğu mapping değil"]
    if block.get("unchanged") is not True:
        errors.append("refactor unchanged true olmalı")
    commits: dict[str, str] = {}
    for label in ("baseline", "after"):
        point = block.get(label)
        if not isinstance(point, dict):
            errors.append(f"refactor.{label} yok")
            continue
        ref = str(point.get("commit") or "")
        local = commit_exists(ref, root)
        if not local and repo:
            local = fetch_commit(ref, root)
        if not local:
            errors.append(f"refactor.{label} commit bulunamadı: {ref or 'yok'}")
        if point.get("tests") != "pass":
            errors.append(f"refactor.{label} tests pass olmalı")
        commits[label] = ref
    base = commits.get("baseline")
    after = commits.get("after")
    if base and after:
        if base == after:
            errors.append("refactor baseline ve after aynı commit")
        elif commit_exists(base, root) and commit_exists(after, root):
            if not is_ancestor(base, after, root):
                errors.append("refactor baseline, after'ın atası değil")
    if commit and after:
        resolved_after = resolve_commit(after, root)
        resolved_commit = resolve_commit(commit, root)
        if not resolved_after or not resolved_commit:
            errors.append("refactor.after çözümlenemedi")
        elif resolved_after != resolved_commit:
            errors.append("refactor.after kanıt commit'i ile aynı olmalı")
    declared = block.get("files_changed")
    if not isinstance(declared, int) or isinstance(declared, bool) or declared < 1:
        errors.append("refactor files_changed pozitif tam sayı olmalı")
    elif base and after and commit_exists(base, root) and commit_exists(after, root):
        actual = changed_files(base, after, root)
        if actual is None:
            errors.append("refactor dosya sayısı ölçülemedi")
        elif declared != actual:
            errors.append(
                f"refactor files_changed {declared} ama gerçek değişim {actual}"
            )
        elif actual > 20:
            errors.append(f"refactor {actual} dosya (üst sınır 20)")
    baseline_point = block.get("baseline")
    after_point = block.get("after")
    baseline_point = baseline_point if isinstance(baseline_point, dict) else {}
    after_point = after_point if isinstance(after_point, dict) else {}
    if block.get("ui_unchanged") is True:
        before = baseline_point.get("snapshots")
        final = after_point.get("snapshots")
        if not before or not final:
            errors.append("ui_unchanged için iki snapshot hash gerekli")
        elif before != final:
            errors.append("ui_unchanged ama snapshot hash farklı")
    baseline_perf = baseline_point.get("perf_ms")
    after_perf = after_point.get("perf_ms")
    if (baseline_perf is None) != (after_perf is None):
        errors.append("perf_ms iki tarafta da olmalı ya da hiç olmamalı")
    return errors


def commit_time(commit: str, root: Path = ROOT) -> str:
    result = git(["show", "-s", "--format=%cI", commit], root)
    return result.stdout.strip() if result.returncode == 0 else ""


def _aware(value: str):
    from datetime import datetime, timezone

    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def placeholder_review_error(reviewer_id: str, when: str) -> str | None:
    """Placeholder reviewer ids are rejected only for evidence after the cutoff."""
    if not PLACEHOLDER_RE.match(str(reviewer_id or "")):
        return None
    stamp, cutoff = _aware(when), _aware(STRICT_SINCE)
    if not stamp or not cutoff or stamp < cutoff:
        return None
    return "reviewer id yer tutucu; gerçek oturum id'si gerekli"


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
    local_commit = commit_exists(commit, root)
    if not local_commit and repo:
        local_commit = fetch_commit(commit, root)
    if not local_commit:
        errors.append(f"commit bulunamadı: {commit or 'yok'}")

    expected = diff_hash(commit, root) if local_commit else None
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
        if risk == "critical":
            errors.append("risk critical için CI skipped kabul edilmez")
        elif risk == "high":
            local = record.get("local_gate")
            if not isinstance(local, dict):
                errors.append(
                    "risk high için CI skipped yalnız yerel kapı kaydıyla kabul edilir "
                    "(local_gate)"
                )
            else:
                if not str(local.get("command") or "").strip():
                    errors.append("local_gate.command yok")
                if local.get("exit_code") != 0:
                    errors.append("local_gate.exit_code 0 değil")
    else:
        errors.append("CI status success veya skipped olmalı")

    allowed_diffs = {expected} if expected else set()
    refactor_block = (
        record.get("refactor") if isinstance(record.get("refactor"), dict) else {}
    )
    if refactor_block:
        baseline_point = refactor_block.get("baseline")
        after_point = refactor_block.get("after")
        base_ref = (
            str(baseline_point.get("commit") or "")
            if isinstance(baseline_point, dict)
            else ""
        )
        after_ref = (
            str(after_point.get("commit") or "")
            if isinstance(after_point, dict)
            else ""
        )
        if base_ref and after_ref:
            range_hash = range_diff_hash(base_ref, after_ref, root)
            if range_hash:
                steps = commit_count(base_ref, after_ref, root)
                if steps is not None and steps > 1:
                    allowed_diffs = {range_hash}
                else:
                    allowed_diffs.add(range_hash)

    reviewers = record.get("reviewers")
    reviewers = reviewers if isinstance(reviewers, list) else []
    minimum = 2 if risk in {"high", "critical"} else 1
    if len(reviewers) < minimum:
        errors.append(f"en az {minimum} reviewer kaydı gerekli")
    seen: set[str] = set()
    reviewed_at = commit_time(commit, root) if commit else ""
    for index, reviewer in enumerate(reviewers, 1):
        if not isinstance(reviewer, dict):
            errors.append(f"reviewer {index} mapping değil")
            continue
        for key in ("role", "id", "model", "prompt_hash", "diff_hash"):
            if not str(reviewer.get(key) or "").strip():
                errors.append(f"reviewer {index}: {key} yok")
        reviewer_id = str(reviewer.get("id") or "")
        message = placeholder_review_error(reviewer_id, reviewed_at)
        if message:
            errors.append(f"reviewer {index}: {message}")
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
        elif allowed_diffs and reviewer_diff not in allowed_diffs:
            errors.append(f"reviewer {index}: farklı diff'i incelemiş")

    if "refactor" in record:
        errors += verify_refactor(
            record.get("refactor"), root=root, repo=repo, commit=commit
        )

    return errors


def build(
    commit: str,
    implementer: str | None,
    ci_run: str | None,
    ci_skipped: str | None,
    reviewers: list[str],
    root: Path = ROOT,
    local_gate: str | None = None,
    local_gate_exit: int = 0,
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

    data = {
        "commit": resolved,
        "diff_hash": expected,
        "ci": ci,
        "reviewers": parsed,
    }
    if local_gate:
        data["local_gate"] = {
            "command": local_gate,
            "exit_code": int(local_gate_exit),
        }
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="build evidence v3 verification")
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--implementer")
    parser.add_argument("--ci-run")
    parser.add_argument("--ci-skipped")
    parser.add_argument("--local-gate", help="high risk için yerel kapı komutu")
    parser.add_argument(
        "--local-gate-exit", type=int, default=0, help="yerel kapı exit kodu"
    )
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
            local_gate=args.local_gate,
            local_gate_exit=args.local_gate_exit,
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
