#!/usr/bin/env python3
"""Build a narrow review packet for one checkpoint.

Usage:
  python3 delivery/scripts/review_packet.py --issue 144 --cp CP-1 --commit HEAD
  python3 delivery/scripts/review_packet.py --issue 144 --cp CP-1 --commit HEAD \
      --delta <base>
  python3 delivery/scripts/review_packet.py --issue 144 --cp CP-1 --commit HEAD \
      --write /tmp/review
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

import brief  # noqa: E402
import profiles  # noqa: E402
import routing  # noqa: E402


def gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"review_packet: gh failed — {result.stderr.strip()}")
    return result.stdout


def repo_name() -> str:
    project = routing.project_root(ROOT)
    ecosystem = yaml.safe_load((project / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        raise SystemExit("review_packet: ecosystem.yaml tracker.repo yok")
    return repo


def git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"review_packet: git failed — {result.stderr.strip()}")
    return result.stdout


def evidence_blocks(comments: list[dict]) -> list[dict]:
    records = []
    for comment in comments:
        body = comment.get("body") or ""
        for block in re.findall(
            r"```yaml\s+demir-kit-evidence\s*\n(.*?)```", body, re.S
        ):
            try:
                data = yaml.safe_load(block) or {}
            except yaml.YAMLError:
                continue
            if isinstance(data, dict):
                records.append(data)
    return records


def open_findings(comments: list[dict]) -> list[dict]:
    rows = []
    for record in evidence_blocks(comments):
        for finding in record.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            if finding.get("status") != "open":
                continue
            rows.append(
                {
                    "id": str(finding.get("id") or "?"),
                    "cp_id": str(record.get("cp_id") or "?"),
                    "note": str(finding.get("note") or ""),
                }
            )
    return rows


def commit_range(commit: str, delta: str | None) -> str:
    return f"{delta}..{commit}" if delta else f"{commit}^..{commit}"


def compose_packet(
    header: list[str],
    brief_text: str,
    findings: list[dict],
    diff_stat: str,
    diff: str,
    max_chars: int = 12_000,
) -> str:
    finding_lines = ["## Açık bulgular"]
    if findings:
        for item in findings:
            note = f" — {item['note']}" if item.get("note") else ""
            finding_lines.append(f"- {item['id']} ({item['cp_id']}): {note.lstrip(' —')}")
    else:
        finding_lines.append("- yok")

    review = [
        "## Reviewer kontrolü",
        "- Her AC en az bir testle kapsanmış mı?",
        "- Gate ve evidence risk seviyesine uygun mu?",
        "- Yeni davranış test edilmiş mi; regresyon var mı?",
        "- Açık bulgular dosya:satır taşıyor mu?",
    ]

    tail = "\n".join(finding_lines + ["## Diff özeti", diff_stat.strip() or "(boş)"])
    fixed = "\n".join(header + [brief_text.strip(), tail, "## Diff"])
    footer = "\n".join(review)

    def assemble(payload: str) -> str:
        return fixed + "\n" + payload + "\n\n" + footer + "\n"

    def size(text: str) -> int:
        return len(text.encode("utf-8"))

    body = diff.strip() or "(diff yok)"
    budget = max_chars - size(assemble(""))
    if budget <= 0:
        body = "[diff sığmadı: --max-chars artır]"
    elif size(body) > budget:
        keep = max(0, budget - 80)
        raw = body.encode("utf-8")[:keep].decode("utf-8", "ignore")
        body = raw + f"\n... [diff kısaltıldı: {size(body) - size(raw)} bayt]"
    return assemble(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="review packet for one checkpoint")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--cp", required=True)
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--delta", help="base ref for a fix-only packet")
    parser.add_argument("--max-chars", type=int, default=12_000)
    parser.add_argument("--write", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    issue = json.loads(
        gh(
            [
                "api",
                f"repos/{repo_name()}/issues/{args.issue}",
            ]
        )
    )
    comments = json.loads(
        gh(
            [
                "api",
                f"repos/{repo_name()}/issues/{args.issue}/comments?per_page=100",
            ]
        )
    )
    seal = routing.seal_body(issue.get("body") or "")
    if not seal:
        raise SystemExit("review_packet: issue seal (`demir-kit` bloğu) yok")
    project = routing.project_root(ROOT)
    seal_profile = str((seal.get("factory") or {}).get("profile") or "")
    brief_text = brief.render_cp_brief(
        {"issue": args.issue, "risk": (seal.get("risk") or {}).get("level")},
        seal,
        args.cp,
        routing.kit_prefix(ROOT),
        profile_gates=profiles.gates_for(project, seal_profile),
        include_evidence=False,
    )
    commit = git(["rev-parse", args.commit]).strip()
    span = commit_range(commit, args.delta)
    diff_stat = git(["diff", "--stat", span])
    diff = git(["diff", span])
    header = [
        f"## Review packet — #{args.issue} {args.cp}",
        f"Commit: {commit[:12]}"
        + (f" · Delta: {args.delta}..{commit[:12]}" if args.delta else " · Tam commit"),
        f"Boyut sınırı: {args.max_chars} karakter",
    ]
    packet = compose_packet(
        header,
        brief_text,
        open_findings(comments),
        diff_stat,
        diff,
        args.max_chars,
    )

    if args.write:
        args.write.mkdir(parents=True, exist_ok=True)
        path = args.write / f"review-{args.cp}.md"
        path.write_text(packet, encoding="utf-8")
        print(path)
    elif args.json:
        print(
            json.dumps(
                {
                    "issue": args.issue,
                    "cp_id": args.cp,
                    "commit": commit,
                    "delta": args.delta,
                    "chars": len(packet),
                    "packet": packet,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(packet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
