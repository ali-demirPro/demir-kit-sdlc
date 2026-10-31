#!/usr/bin/env python3
"""Feature-detect the installed Orca CLI without comparing versions.

Orca ships new commands and flags frequently. Product projects must not pin an
Orca version; the kit reads ``orca agent-context --json`` and adapts. The schema
is cached under ``.orchestration`` (gitignored) for a short TTL.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import routing  # noqa: E402

CACHE_TTL_SECONDS = 3600
CACHE_VERSION = 1


class OrcaCapabilityError(RuntimeError):
    """The installed Orca CLI lacks a command or flag the kit needs."""


def project_root(project: Path | None = None) -> Path:
    return Path(project).resolve() if project else routing.project_root(ROOT)


def cache_path(project: Path) -> Path:
    return project / ".orchestration" / "orca-schema.json"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def fetch_schema(project: Path) -> dict:
    try:
        result = run(["orca", "agent-context", "--json"], project)
    except FileNotFoundError as exc:
        raise OrcaCapabilityError("orca CLI bulunamadı") from exc
    if result.returncode != 0:
        raise OrcaCapabilityError(
            "orca agent-context başarısız: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise OrcaCapabilityError("orca agent-context JSON geçersiz") from exc
    if not isinstance(data, dict) or not isinstance(data.get("commands"), list):
        raise OrcaCapabilityError("orca agent-context şeması beklenen biçimde değil")
    return data


def load_schema(project: Path | None = None, refresh: bool = False) -> dict:
    project = project_root(project)
    path = cache_path(project)
    if not refresh and path.is_file():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}
        fetched_at = float(cached.get("fetched_at") or 0)
        if (
            cached.get("cache_version") == CACHE_VERSION
            and time.time() - fetched_at < CACHE_TTL_SECONDS
            and isinstance(cached.get("commands"), list)
        ):
            return cached
    data = fetch_schema(project)
    data["cache_version"] = CACHE_VERSION
    data["fetched_at"] = time.time()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return data


def command_map(schema: dict) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    for item in schema.get("commands") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("command") or "").strip()
        if name:
            mapping[name] = item
    return mapping


def resolve_command(schema: dict, command: str) -> dict | None:
    commands = command_map(schema)
    candidates = [
        command,
        command.replace("-", " "),
        command.replace(".", " "),
        command.replace("_", " "),
    ]
    for candidate in candidates:
        if candidate in commands:
            return commands[candidate]
    return None


def has(command: str, project: Path | None = None, schema: dict | None = None) -> bool:
    schema = schema or load_schema(project)
    return resolve_command(schema, command) is not None


def flags(
    command: str, project: Path | None = None, schema: dict | None = None
) -> set[str]:
    schema = schema or load_schema(project)
    item = resolve_command(schema, command)
    if not item:
        return set()
    return {str(flag) for flag in item.get("flags") or []}


def require(
    command: str,
    needed: tuple[str, ...] = (),
    project: Path | None = None,
    schema: dict | None = None,
) -> dict:
    schema = schema or load_schema(project)
    item = resolve_command(schema, command)
    if not item:
        raise OrcaCapabilityError(
            f"Orca komutu yok: 'orca {command}'; Orca'yı güncelle veya degrade kaydı aç"
        )
    missing = sorted(set(needed) - {str(flag) for flag in item.get("flags") or []})
    if missing:
        raise OrcaCapabilityError(
            f"'orca {command}' şu flag'leri desteklemiyor: {', '.join(missing)}"
        )
    return item


def runtime_ok(project: Path | None = None) -> bool:
    project = project_root(project)
    result = run(["orca", "status", "--json"], project)
    if result.returncode != 0:
        return False
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return bool(data.get("ok"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Orca capability detection")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--check", help="command name, optionally 'cmd:flag1,flag2'")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        schema = load_schema(args.project, refresh=args.refresh)
    except OrcaCapabilityError as exc:
        print(f"orca_capabilities: {exc}", file=sys.stderr)
        return 1

    if args.check:
        command, _, raw_flags = args.check.partition(":")
        needed = tuple(item for item in raw_flags.split(",") if item)
        try:
            item = require(command, needed, args.project, schema)
        except OrcaCapabilityError as exc:
            print(f"orca_capabilities: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(item, ensure_ascii=False, indent=2))
        else:
            print(f"ok: orca {item['command']} ({len(item.get('flags') or [])} flag)")
        return 0

    if args.list:
        for name in sorted(command_map(schema)):
            print(name)
        return 0

    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": schema.get("schemaVersion"),
                    "command_count": len(schema.get("commands") or []),
                    "cache": str(cache_path(project_root(args.project))),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(
            f"orca schema v{schema.get('schemaVersion')} · "
            f"{len(schema.get('commands') or [])} komut"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
