#!/usr/bin/env python3
"""Kit self-check against the installed Orca command schema.

Product projects never compare Orca versions. This script is for kit
maintenance: it names the exact commands/flags the kit relies on and reports
what the installed Orca build no longer provides, so the kit can adapt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import orca_capabilities  # noqa: E402

REQUIRED: dict[str, tuple[str, ...]] = {
    "status": ("json",),
    "agent-context": ("json",),
    "host list": ("json",),
    "worktree create": ("name", "issue", "repo", "json"),
    "worktree current": ("json",),
    "worktree list": ("json",),
    "worktree set": ("comment", "workspace-status", "unread", "read", "issue", "pr", "json"),
    "worktree rm": ("worktree", "json"),
    "worktree ps": ("json",),
    "ports": ("json",),
    "repo set-base-ref": ("repo", "ref", "json"),
    "reference add": ("worktree", "json"),
    "orchestration run-create": ("objective", "json"),
    "orchestration run-use": ("id", "json"),
    "orchestration run-show": ("id", "json"),
    "orchestration task-create": ("spec", "task-title", "deps", "run", "json"),
    "orchestration task-update": ("id", "status", "result", "run", "json"),
    "orchestration task-list": ("run", "json"),
    "orchestration worker-start": (
        "task",
        "spec",
        "worktree",
        "agent",
        "run",
        "model",
        "effort",
        "json",
    ),
    "orchestration worker-release": ("dispatch", "json"),
    "orchestration worker-read": ("dispatch", "json"),
    "orchestration worker-list": ("run", "json"),
    "orchestration check": ("run", "wait", "types", "timeout-ms", "json"),
    "orchestration send": ("to", "subject", "body", "type", "json"),
    "orchestration ask": ("question", "options", "timeout-ms", "json"),
    "orchestration reply": ("id", "body", "json"),
    "orchestration inbox": ("json",),
    "orchestration gate-create": ("task", "question", "options", "json"),
    "orchestration gate-resolve": ("id", "resolution", "json"),
    "orchestration gate-list": ("json",),
    "terminal create": ("worktree", "command", "json"),
    "terminal wait": ("for", "timeout-ms", "json"),
    "terminal read": ("json",),
    "terminal send": ("text", "enter", "json"),
    "file open-changed": ("mode", "worktree", "json"),
    "tab profile list": ("json",),
    "goto": ("url", "json"),
    "snapshot": ("json",),
    "click": ("element", "json"),
    "fill": ("element", "value", "json"),
    "screenshot": ("json",),
    "full-screenshot": ("json",),
    "pdf": ("json",),
    "console": ("limit", "json"),
    "network": ("limit", "json"),
    "set device": ("name", "json"),
    "computer permissions": ("json",),
    "computer get-app-state": ("app", "json"),
    "emulator list": ("json",),
    "emulator attach": ("json",),
    "emulator tap": ("json",),
    "emulator type": ("json",),
    "emulator gesture": ("json",),
    "emulator button": ("json",),
    "emulator rotate": ("json",),
    "emulator kill": ("json",),
    "artifacts share": ("json",),
    "search": ("query", "scope", "limit", "sort", "json"),
    "automations list": ("json",),
    "automations create": ("name", "trigger", "prompt", "provider", "json"),
    "automations run": ("json",),
    "automations runs": ("id", "json"),
    "automations remove": ("json",),
    "skills install": ("skill", "json"),
    "skills update": ("all", "json"),
    "skills get": ("json",),
}


def check(project: Path | None = None, schema: dict | None = None) -> list[str]:
    schema = schema or orca_capabilities.load_schema(project)
    issues: list[str] = []
    for command, needed in REQUIRED.items():
        item = orca_capabilities.resolve_command(schema, command)
        if not item:
            issues.append(f"komut yok: orca {command}")
            continue
        available = {str(flag) for flag in item.get("flags") or []}
        missing = sorted(set(needed) - available)
        if missing:
            issues.append(f"orca {command}: eksik flag — {', '.join(missing)}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="kit ↔ Orca schema compatibility")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        schema = orca_capabilities.load_schema(args.project)
    except orca_capabilities.OrcaCapabilityError as exc:
        print(f"compat: {exc}", file=sys.stderr)
        return 1

    issues = check(args.project, schema)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not issues,
                    "schema_version": schema.get("schemaVersion"),
                    "commands": len(REQUIRED),
                    "issues": issues,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif issues:
        for issue in issues:
            print(f"[fail] {issue}")
    else:
        print(f"compat: ok ({len(REQUIRED)} komut)")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
