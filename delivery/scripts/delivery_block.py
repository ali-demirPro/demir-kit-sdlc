#!/usr/bin/env python3
"""Inject the demir-kit delivery entry point into a product AGENTS.md.

The block is intentionally short: it names the exact commands so an agent
working in the product repo cannot fall back to a plain branch plus native
subagents without noticing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
START = "<!-- demir-kit:delivery:start -->"
END = "<!-- demir-kit:delivery:end -->"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def managed_block(text: str) -> str | None:
    match = re.search(re.escape(START) + r"(.*?)" + re.escape(END), text, re.S)
    return match.group(0) if match else None


def render_block(prefix: str = "") -> str:
    prefix = prefix.strip("/")
    base = f"./{prefix}/" if prefix else "./"
    lines = [
        START,
        "## demir-kit çalışma akışı",
        "",
        "- Epic başına **tek worktree**: `orca worktree create --name epic-<N> --issue <N>`.",
        f"- Claim: `{base}delivery/scripts/next-leaf.sh --claim`; epic worktree'yi bulur veya açar.",
        "- Kaynak değişikliği yalnız epic worktree'sinde: "
        f"`{base}delivery/scripts/guard.sh --issue <N>` ana checkout'u reddeder.",
        "- Her leaf: `orca orchestration task-create` + "
        "`worker-start --worktree <epic path>`; native subagent yalnız degrade modda.",
        "- Leaf kapanışı: commit + evidence + `transition.sh --to leaf-done`; "
        "main'e merge yok.",
        "- Epic kapanışı: tek PR `epic-<N>` → main, merge, sonra `orca worktree rm`.",
        "- Rebase yok; yeni leaf öncesi `git merge origin/main`.",
        "",
        "Bu blok otomatik üretilir; `delivery_block.py --apply` ile yenilenir.",
        END,
    ]
    return "\n".join(lines)


def proposed_text(existing: str, block: str) -> str:
    current = managed_block(existing)
    if current is not None:
        return existing.replace(current, block, 1)
    body = existing.rstrip("\n")
    if not body:
        return "# Agents\n\n" + block + "\n"
    return body + "\n\n" + block + "\n"


def inject(project: Path, prefix: str = "", apply: bool = False) -> dict:
    root = Path(project).resolve()
    agents = root / "AGENTS.md"
    existing = read_text(agents)
    block = render_block(prefix)
    text = proposed_text(existing, block)
    changed = text != existing
    if apply and changed:
        agents.write_text(text, encoding="utf-8")
    return {
        "project": str(root),
        "changed": changed,
        "applied": bool(apply and changed),
        "block": block,
        "text": text,
    }


def check(project: Path, prefix: str = "") -> list[str]:
    root = Path(project).resolve()
    agents = root / "AGENTS.md"
    if not agents.is_file():
        return ["AGENTS.md yok"]
    text = read_text(agents)
    if managed_block(text) is None:
        return ["AGENTS.md içinde demir-kit çalışma bloğu yok"]
    if managed_block(text) != render_block(prefix):
        return ["demir-kit çalışma bloğu bayat; `delivery_block.py --apply` çalıştır"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="inject the demir-kit delivery block")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--prefix", default="", help="vendored kit path, e.g. demir-kit")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.check:
        issues = check(args.project, args.prefix)
        for issue in issues:
            print(f"[fail] {issue}")
        return 1 if issues else 0

    result = inject(args.project, args.prefix, apply=args.apply)
    if args.json:
        import json

        print(
            json.dumps(
                {
                    "project": result["project"],
                    "changed": result["changed"],
                    "applied": result["applied"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        state = "yazıldı" if result["applied"] else "değişmedi"
        print(f"{result['project']}/AGENTS.md: {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
