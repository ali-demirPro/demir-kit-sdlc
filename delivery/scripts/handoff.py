#!/usr/bin/env python3
"""Hand an epic to a successor agent through Orca.

Writes the durable handoff note (issue comment), launches the successor in the
same worktree, and can close the old terminal once the new agent is ready.

    python3 delivery/scripts/handoff.py --issue 277 --worktree . --leaf 282 --next "N7"
    python3 delivery/scripts/handoff.py --issue 277 --worktree . --apply
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path


def handoff_note(
    issue: int, leaf: str, done: str, next_step: str, decisions: str = ""
) -> str:
    lines = [
        f"## Devir — #{issue}",
        "",
        f"- Leaf: {leaf or '-'}",
        f"- Bitti: {done or '-'}",
        f"- Sıradaki: {next_step or '-'}",
        f"- Kararlar: {decisions or '-'}",
        "",
        "Devam: issue mührünü ve `next-leaf.sh --claim` çıktısını oku; sohbet geçmişi taşınmaz.",
    ]
    return "\n".join(lines)


def launch_command(
    worktree: Path, prompt: str, retry_launch: str = ""
) -> list[str]:
    command = [
        "orca",
        "agent",
        "launch",
        "--worktree",
        f"path:{worktree}",
        "--agent",
        "opencode2",
        "--prompt",
        prompt,
        "--json",
    ]
    if retry_launch:
        command += ["--retry-launch", retry_launch]
    return command


def close_command(terminal: str) -> list[str]:
    return ["orca", "terminal", "close", "--terminal", terminal, "--json"]


def post(issue: int, body: str, worktree: Path) -> bool:
    result = subprocess.run(
        ["gh", "issue", "comment", str(issue), "--body", body],
        cwd=str(worktree),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def close_terminal(terminal: str) -> bool:
    if not terminal:
        return True
    result = subprocess.run(close_command(terminal), capture_output=True, text=True)
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="epic handoff via Orca")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--worktree", default=".")
    parser.add_argument("--leaf", default="")
    parser.add_argument("--done", default="")
    parser.add_argument("--next", dest="next_step", default="")
    parser.add_argument("--decisions", default="")
    parser.add_argument("--close-terminal", default="")
    parser.add_argument("--retry-launch", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    worktree = Path(args.worktree).expanduser().resolve()
    note = handoff_note(
        args.issue, args.leaf, args.done, args.next_step, args.decisions
    )
    prompt = (
        f"Devir: issue #{args.issue}. Önce `gh issue view {args.issue} --comments` "
        "ve son devir yorumunu oku; kaldığın yerden devam et. Sohbet geçmişi yok."
    )
    launch = launch_command(worktree, prompt, args.retry_launch)
    plan = {
        "issue": args.issue,
        "note": note,
        "launch": launch,
        "close": close_command(args.close_terminal) if args.close_terminal else [],
    }
    if not args.apply:
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(note)
            print("\n" + shlex.join(launch))
            if plan["close"]:
                print(shlex.join(plan["close"]))
        return 0

    if not args.retry_launch and not post(args.issue, note, worktree):
        sys.exit("handoff: devir yorumu yazılamadı")
    started = subprocess.run(launch, capture_output=True, text=True)
    if started.returncode != 0:
        sys.exit(
            "handoff: successor başlatılamadı; launch yanıtı kaybolduysa "
            "aynı komutu --retry-launch <operationId> ile tekrar et — "
            + started.stderr.strip()
        )
    if args.close_terminal and not close_terminal(args.close_terminal):
        sys.exit("handoff: eski terminal kapatılamadı; elle kontrol et")
    # Launch success is treated as ready: Orca opens the agent tab synchronously.
    print("handoff: devir yazıldı, successor başlatıldı")
    return 0


if __name__ == "__main__":
    sys.exit(main())
