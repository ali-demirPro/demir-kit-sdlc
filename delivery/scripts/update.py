#!/usr/bin/env python3
"""Write a short human progress/summary comment.

No YAML, no JSON, no repo file. If no --issue is given, print to stdout.

Usage:
  python3 delivery/scripts/update.py --who developer --what "Leaf mühürlendi"
  python3 delivery/scripts/update.py --issue 21 --who "developer" --what "İki worker bitti" --next "Epic kapanışı"
  python3 delivery/scripts/update.py --issue 21 --kind summary --who owner --what "Epic tamam" --approval yes --ask "Kapanışı onaylıyor musun?"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import routing  # noqa: E402


def repo_name() -> str:
    project = routing.project_root(ROOT)
    ecosystem = yaml.safe_load((project / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        sys.exit("update: ecosystem.yaml tracker.repo yok")
    return repo


def render(
    kind: str,
    who: str,
    what: str,
    decision: str | None = None,
    problem: str | None = None,
    next_step: str | None = None,
    approval: bool = False,
    ask: str | None = None,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    heading = "Özet" if kind == "summary" else "İlerleme"
    what_label = "Ne bitti" if kind == "summary" else "Ne oldu"
    next_label = "Kalan" if kind == "summary" else "Sırada"

    lines = [f"## {heading} — {stamp}", ""]
    lines.append(f"**Kim:** {who}")
    lines.append(f"**{what_label}:** {what}")
    if decision:
        lines.append(f"**Karar:** {decision}")
    if problem:
        lines.append(f"**Sorun:** {problem}")
    if next_step:
        lines.append(f"**{next_label}:** {next_step}")
    if approval:
        lines.append(f"**Onay:** gerekiyor — {ask or 'Karar onayı bekleniyor.'}")
    else:
        lines.append("**Onay:** gerekmiyor")
    return "\n".join(lines) + "\n"


def post_comment(repo: str, issue: int, body: str) -> None:
    result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{repo}/issues/{issue}/comments",
            "--input",
            "-",
        ],
        input=json.dumps({"body": body}),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        sys.exit(f"update: yorum yazılamadı — {result.stderr.strip()}")


def request_approval(repo: str, issue: int) -> None:
    result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{repo}/issues/{issue}/labels",
            "-f",
            "labels[]=human-qa",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"update: human-qa etiketi eklenemedi — {result.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="human progress/summary comment")
    parser.add_argument("--issue", type=int)
    parser.add_argument("--kind", choices=["progress", "summary"], default="progress")
    parser.add_argument("--who", default="ekip")
    parser.add_argument("--what", required=True)
    parser.add_argument("--decision")
    parser.add_argument("--problem")
    parser.add_argument("--next", dest="next_step")
    parser.add_argument("--approval", choices=["yes", "no"], default="no")
    parser.add_argument("--ask")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.what.strip():
        sys.exit("update: --what boş olamaz")

    body = render(
        args.kind,
        args.who,
        args.what.strip(),
        decision=args.decision,
        problem=args.problem,
        next_step=args.next_step,
        approval=args.approval == "yes",
        ask=args.ask,
    )

    if args.issue is None or args.dry_run:
        print(body)
    else:
        repo = repo_name()
        post_comment(repo, args.issue, body)
        if args.approval == "yes":
            request_approval(repo, args.issue)
        print(f"update: #{args.issue} yorumu yazıldı")
    return 0


if __name__ == "__main__":
    sys.exit(main())
