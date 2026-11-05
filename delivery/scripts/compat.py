#!/usr/bin/env python3
"""Kit self-check against the installed Orca command schema.

Product projects never compare Orca versions. This script is for kit
maintenance: it names the exact commands/flags the kit relies on and reports
what the installed Orca build no longer provides, so the kit can adapt.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

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


SHAPE_TIMEOUT_SECONDS = 10

#: Salt-okunur komut → yanıt şekli doğrulayıcısı.
SHAPES: dict[str, str] = {
    "orchestration run-current": "run-current",
    "orchestration run-list": "run-list",
    "orchestration task-list": "task-list",
}

Runner = Callable[..., dict]


def _run_current_state(payload: object) -> tuple[str, str | None]:
    """("ok", run_id) | ("skip", None) | ("drift", ayrıntı) döner.

    Bağlı Run yoksa (`runId`/`run` null, `result` yok, `ok:false`) bu bir
    drift değildir: prob atlanır.
    """
    if not isinstance(payload, dict):
        return "drift", "yanıt obje değil"
    if payload.get("ok") is False:
        return "skip", None
    result = payload.get("result")
    if result is None:
        return "skip", None
    if not isinstance(result, dict):
        return "drift", f"result obje değil ({type(result).__name__})"
    run_id = result.get("runId")
    if isinstance(run_id, str) and run_id.strip():
        return "ok", run_id
    if "run" in result:
        run = result["run"]
        if run is None:
            return "skip", None
        if not isinstance(run, dict):
            return "drift", f"result.run obje değil ({type(run).__name__})"
        nested = run.get("id")
        if isinstance(nested, str) and nested.strip():
            return "ok", nested
        return "drift", "result.run.id yok"
    if "runId" in result:
        if run_id is None:
            return "skip", None
        return "drift", f"result.runId metin değil ({type(run_id).__name__})"
    return "drift", "result.runId veya result.run.id yok"


def _list_state(payload: object, key: str) -> tuple[str, str | None]:
    if not isinstance(payload, dict):
        return "drift", "yanıt obje değil"
    if payload.get("ok") is False:
        return "skip", None
    result = payload.get("result")
    if result is None:
        return "skip", None
    if not isinstance(result, dict):
        return "drift", f"result obje değil ({type(result).__name__})"
    if key not in result:
        return "drift", f"result.{key} yok"
    value = result.get(key)
    if isinstance(value, list):
        return "ok", None
    return "drift", f"result.{key} liste değil ({type(value).__name__})"


VALIDATORS = {
    "run-current": _run_current_state,
    "run-list": lambda payload: _list_state(payload, "runs"),
    "task-list": lambda payload: _list_state(payload, "tasks"),
}


def _default_runner(command: str, extra: list[str] | None = None) -> dict:
    """`orca <command> --json` çalıştır; yalnız salt-okunur komutlar."""
    args = ["orca", *command.split(), *(extra or []), "--json"]
    proc = subprocess.run(
        args, capture_output=True, text=True, timeout=SHAPE_TIMEOUT_SECONDS
    )
    if proc.returncode != 0:
        raise OSError(proc.stderr.strip() or f"orca {command} rc={proc.returncode}")
    data = json.loads(proc.stdout)
    if not isinstance(data, dict):
        raise ValueError(f"orca {command}: JSON kökü obje değil")
    return data


SKIP_ERRORS = (OSError, ValueError, subprocess.SubprocessError)


def _probe(
    runner: Runner, command: str, extra: list[str] | None = None
) -> dict | None:
    """Probu çalıştır; çağrı başarısızsa None (prob atlanır, diğerleri sürer)."""
    try:
        return runner(command, extra)
    except SKIP_ERRORS:
        return None


def check_shapes(runner: Runner | None = None) -> list[str]:
    """Salt-okunur Orca komutlarının yanıt şeklini doğrula.

    Problar birbirinden bağımsızdır: biri hata verirse yalnız o atlanır, o ana
    kadar bulunan drift korunur. `orca` yoksa boş liste döner; CI düşmez.
    """
    runner = runner or _default_runner
    issues: list[str] = []

    current = _probe(runner, "orchestration run-current")
    if current is None:
        run_state, run_id = "skip", None
    else:
        run_state, detail = VALIDATORS[SHAPES["orchestration run-current"]](current)
        if run_state == "drift":
            issues.append(f"orca orchestration run-current: yanıt şekli — {detail}")
        run_id = detail if run_state == "ok" else None

    listing = _probe(runner, "orchestration run-list")
    if listing is not None:
        state, detail = VALIDATORS[SHAPES["orchestration run-list"]](listing)
        if state == "drift":
            issues.append(f"orca orchestration run-list: yanıt şekli — {detail}")

    if run_state == "ok" and run_id:
        tasks = _probe(runner, "orchestration task-list", ["--run", run_id])
        if tasks is not None:
            state, detail = VALIDATORS[SHAPES["orchestration task-list"]](tasks)
            if state == "drift":
                issues.append(f"orca orchestration task-list: yanıt şekli — {detail}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="kit ↔ Orca schema compatibility")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--no-shapes", action="store_true", help="yanıt şekli problarını atla"
    )
    args = parser.parse_args()

    try:
        schema = orca_capabilities.load_schema(args.project)
    except orca_capabilities.OrcaCapabilityError as exc:
        print(f"compat: {exc}", file=sys.stderr)
        return 1

    issues = check(args.project, schema)
    if not args.no_shapes:
        issues += check_shapes()
        shapes_note = f", {len(SHAPES)} yanıt şekli"
    else:
        shapes_note = ", yanıt şekli probu atlandı"
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not issues,
                    "schema_version": schema.get("schemaVersion"),
                    "commands": len(REQUIRED),
                    "shapes_checked": not args.no_shapes,
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
        print(f"compat: ok ({len(REQUIRED)} komut{shapes_note})")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
