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
    """Latest status per (cp_id, finding id); only still-open findings."""
    latest: dict[tuple[str, str], dict] = {}
    for record in evidence_blocks(comments):
        cp_id = str(record.get("cp_id") or "?")
        for finding in record.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            finding_id = str(finding.get("id") or "?")
            latest[(cp_id, finding_id)] = {
                "id": finding_id,
                "cp_id": cp_id,
                "status": str(finding.get("status") or ""),
                "note": str(finding.get("note") or ""),
            }
    return [row for row in latest.values() if row["status"] == "open"]


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
    prefix = "\n".join(header) + "\n"
    middle = "\n" + tail + "\n## Diff\n"
    closing = "\n\n" + "\n".join(review) + "\n"

    def size(text: str) -> int:
        return len(text.encode("utf-8"))

    def trim(text: str, limit: int, note: str) -> str:
        raw = text.encode("utf-8")[: max(0, limit)].decode("utf-8", "ignore")
        return raw + note

    body = diff.strip() or "(diff yok)"
    brief_part = brief_text.strip()

    room_for_brief = max_chars - size(prefix + middle + closing)
    if room_for_brief <= 0:
        note = "\n... [paket kısaltıldı: --max-chars artır]"
        packet = prefix + brief_part + middle + body + closing
        keep = max(0, max_chars - size(note))
        trimmed = packet.encode("utf-8")[:keep].decode("utf-8", "ignore")
        return (trimmed + note) if size(trimmed + note) <= max_chars else trimmed
    if size(brief_part) > room_for_brief:
        brief_part = trim(brief_part, room_for_brief - 40, "\n... [brief kısaltıldı]")

    fixed = prefix + brief_part + middle
    room = max_chars - size(fixed + closing)
    if room <= 0:
        body = "[diff sığmadı: --max-chars artır]"
    elif size(body) > room:
        keep = max(0, room - 90)
        body = trim(body, keep, "") + (
            f"\n... [diff kısaltıldı: {size(body) - keep} bayt]"
        )
    packet = fixed + body + closing
    if size(packet) > max_chars:
        packet = packet.encode("utf-8")[:max_chars].decode("utf-8", "ignore")
    return packet


def packet_for(
    issue_number: int,
    cp_id: str,
    commit: str = "HEAD",
    delta: str | None = None,
    max_chars: int = 12_000,
) -> str:
    issue = json.loads(
        gh(["api", f"repos/{repo_name()}/issues/{issue_number}"])
    )
    comments = json.loads(
        gh(
            [
                "api",
                f"repos/{repo_name()}/issues/{issue_number}/comments?per_page=100",
            ]
        )
    )
    seal = routing.seal_body(issue.get("body") or "")
    if not seal:
        raise SystemExit("review_packet: issue seal (`demir-kit` bloğu) yok")
    project = routing.project_root(ROOT)
    seal_profile = str((seal.get("factory") or {}).get("profile") or "")
    brief_text = brief.render_cp_brief(
        {"issue": issue_number, "risk": (seal.get("risk") or {}).get("level")},
        seal,
        cp_id,
        routing.kit_prefix(ROOT),
        profile_gates=profiles.gates_for(project, seal_profile),
        include_evidence=False,
    )
    commit = git(["rev-parse", commit]).strip()
    span = commit_range(commit, delta)
    diff_stat = git(["diff", "--stat", span])
    files = git(["diff", "--name-only", span]).strip().splitlines()
    diff = git(["diff", span])
    header = [
        f"## Review packet — #{issue_number} {cp_id}",
        f"Commit: {commit[:12]}"
        + (f" · Delta: {delta}..{commit[:12]}" if delta else " · Tam commit"),
        f"Boyut sınırı: {max_chars} bayt",
        "Değişen dosyalar:",
    ]
    header += [f"- {name}" for name in files if name]
    return compose_packet(
        header,
        brief_text,
        open_findings(comments),
        diff_stat,
        diff,
        max_chars,
    )


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

    packet = packet_for(
        args.issue, args.cp, args.commit, args.delta, args.max_chars
    )
    commit = git(["rev-parse", args.commit]).strip()

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
