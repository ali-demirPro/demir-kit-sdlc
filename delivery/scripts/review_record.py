#!/usr/bin/env python3
"""Write the review round's short ``demir-kit-review`` record to the issue.

Only ``verdict: revise_required`` records are rejection sources for
``brief.py``; an ``approved`` record closes an earlier rejection.

Usage:
  python3 delivery/scripts/review_record.py --issue 335 --cp CP-1 \
      --verdict revise_required --reviewer adversarial-a \
      --finding "AR-1|blocking|open|parser ret kaydını görmüyor"
  python3 delivery/scripts/review_record.py --issue 335 --cp CP-1 \
      --verdict revise_required --reviewer adversarial-a \
      --findings /tmp/findings.yaml --apply
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import routing  # noqa: E402

VERDICTS = ("revise_required", "approved")
SEVERITIES = ("blocking", "nit")
STATUSES = ("open", "fixed", "waived")
CP_RE = re.compile(r"^CP-[0-9]+$")


def repo_name() -> str:
    project = routing.project_root(ROOT)
    try:
        ecosystem = yaml.safe_load(
            (project / "ecosystem.yaml").read_text(encoding="utf-8")
        ) or {}
    except (OSError, yaml.YAMLError):
        ecosystem = {}
    repo = (
        (ecosystem.get("tracker") or {}).get("repo")
        if isinstance(ecosystem, dict)
        else None
    )
    if not repo:
        raise SystemExit("review_record: ecosystem.yaml tracker.repo yok")
    return str(repo)


def git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"review_record: git failed — {result.stderr.strip()}")
    return result.stdout


def one_line(text) -> str:
    return " ".join(str(text or "").split())


def normalize_finding(item: dict, index: int) -> dict:
    """One finding in the canonical ``id/severity/status/note`` shape."""
    if not isinstance(item, dict):
        raise SystemExit(f"review_record: bulgu {index} mapping olmalı")
    identifier = one_line(item.get("id"))
    severity = one_line(item.get("severity")).lower()
    status = one_line(item.get("status")).lower()
    note = one_line(item.get("note")) or "-"
    if not identifier:
        raise SystemExit(f"review_record: bulgu {index} id taşımalı")
    if severity not in SEVERITIES:
        raise SystemExit(
            f"review_record: bulgu {identifier} severity blocking|nit olmalı"
        )
    if status not in STATUSES:
        raise SystemExit(
            f"review_record: bulgu {identifier} status open|fixed|waived olmalı"
        )
    return {
        "id": identifier,
        "severity": severity,
        "status": status,
        "note": note,
    }


def parse_finding_arg(text: str, index: int) -> dict:
    """``id|severity|status|note`` or a JSON finding object."""
    raw = str(text or "").strip()
    if raw.startswith("{"):
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"review_record: bulgu JSON geçersiz — {exc}") from exc
        return normalize_finding(item, index)
    parts = [part.strip() for part in raw.split("|", 3)]
    if len(parts) < 3:
        raise SystemExit(
            "review_record: --finding biçimi id|severity|status[|note]"
        )
    parts += [""] * (4 - len(parts))
    return normalize_finding(
        {
            "id": parts[0],
            "severity": parts[1],
            "status": parts[2],
            "note": parts[3],
        },
        index,
    )


def load_findings(path: Path, extra: list[str] | None = None) -> list[dict]:
    items: list = []
    if path is not None:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise SystemExit(f"review_record: bulgu dosyası okunamadı — {exc}") from exc
        except yaml.YAMLError as exc:
            raise SystemExit(f"review_record: bulgu YAML geçersiz — {exc}") from exc
        if isinstance(data, dict):
            data = data.get("findings") or []
        if not isinstance(data, list):
            raise SystemExit("review_record: bulgu dosyası liste olmalı")
        items.extend(data)
    normalized = [
        normalize_finding(item, index)
        for index, item in enumerate(items, start=1)
    ]
    for offset, text in enumerate(extra or [], start=len(normalized) + 1):
        normalized.append(parse_finding_arg(text, offset))
    return normalized


def build_record(
    issue: int,
    cp: str,
    verdict: str,
    reviewed_commit: str,
    reviewer: str,
    findings: list[dict] | None = None,
) -> dict:
    """The comment payload one review round writes."""
    if issue < 1:
        raise SystemExit("review_record: issue pozitif olmalı")
    if not CP_RE.fullmatch(str(cp or "")):
        raise SystemExit("review_record: --cp CP-<n> biçiminde olmalı")
    if verdict not in VERDICTS:
        raise SystemExit(
            "review_record: verdict revise_required|approved olmalı"
        )
    commit = one_line(reviewed_commit)
    person = one_line(reviewer)
    if not commit:
        raise SystemExit("review_record: reviewed_commit boş olamaz")
    if not person:
        raise SystemExit("review_record: reviewer boş olamaz")
    return {
        "issue": issue,
        "cp": cp,
        "verdict": verdict,
        "reviewed_commit": commit,
        "reviewer": person,
        "findings": findings or [],
    }


def comment_body(record: dict) -> str:
    return (
        "```yaml\ndemir-kit-review\n"
        + yaml.safe_dump(record, sort_keys=False, allow_unicode=True)
        + "```\n"
    )


def post_comment(repo: str, issue: int, body: str, run=None) -> str | None:
    """Post the record; return the comment id when the tracker answers."""
    runner = run or subprocess.run
    result = runner(
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
        input=json.dumps({"body": body}),
    )
    if result.returncode != 0:
        raise SystemExit(
            f"review_record: yorum yazılamadı — {result.stderr.strip()}"
        )
    try:
        return str(json.loads(result.stdout).get("id") or "")
    except json.JSONDecodeError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="write a demir-kit-review record")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--cp", required=True)
    parser.add_argument("--verdict", required=True, choices=VERDICTS)
    parser.add_argument("--commit", default="HEAD", help="reviewed commit")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--findings", type=Path, help="YAML/JSON finding list")
    parser.add_argument(
        "--finding",
        action="append",
        default=[],
        help="id|severity|status[|note] (tekrarlanabilir)",
    )
    parser.add_argument("--repo", help="owner/repo (varsayılan ecosystem)")
    parser.add_argument("--apply", action="store_true", help="issue'ya yaz")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    commit = git(["rev-parse", args.commit]).strip()
    findings = load_findings(args.findings, args.finding)
    record = build_record(
        args.issue,
        args.cp,
        args.verdict,
        commit,
        args.reviewer,
        findings,
    )
    body = comment_body(record)
    if not args.apply:
        print(
            json.dumps(record, ensure_ascii=False, indent=2)
            if args.json
            else body
        )
        return 0

    repo = args.repo or repo_name()
    comment_id = post_comment(repo, args.issue, body)
    payload = {**record, "comment_id": comment_id, "body": body}
    print(
        json.dumps(payload, ensure_ascii=False, indent=2)
        if args.json
        else f"review_record: yorum yazıldı — {comment_id or 'id yok'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
