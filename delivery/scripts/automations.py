#!/usr/bin/env python3
"""Create and inspect Orca scheduled automations from kit templates.

Templates live in ``delivery/automations`` and are disabled by default. The
script never enables an automation without ``--enable``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "delivery" / "automations"


def project_root(project: Path | None = None) -> Path:
    return Path(project).resolve() if project else Path.cwd()


def orca(args: list[str], project: Path) -> dict:
    try:
        result = subprocess.run(
            ["orca", *args], cwd=str(project), capture_output=True, text=True
        )
    except FileNotFoundError as exc:
        raise RuntimeError("orca CLI yok") from exc
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Orca JSON çıktısı geçersiz") from exc
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError(str((data.get("error") or {}).get("message") or "Orca hatası"))
    return data


def load_template(name: str) -> dict:
    path = TEMPLATES / f"{name}.yml"
    if not path.is_file():
        path = TEMPLATES / f"{name}.yaml"
    if not path.is_file():
        raise RuntimeError(f"otomasyon şablonu yok: {name}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"şablon mapping değil: {path}")
    return data


def create_command(template: dict, enable: bool) -> list[str]:
    required = ("name", "trigger", "prompt", "provider")
    missing = [key for key in required if not template.get(key)]
    if missing:
        raise RuntimeError("şablon eksik: " + ", ".join(missing))
    args = [
        "automations",
        "create",
        "--name",
        str(template["name"]),
        "--trigger",
        str(template["trigger"]),
        "--prompt",
        str(template["prompt"]),
        "--provider",
        str(template["provider"]),
        "--json",
    ]
    if template.get("time"):
        args += ["--time", str(template["time"])]
    if template.get("timezone"):
        args += ["--timezone", str(template["timezone"])]
    if template.get("precheck"):
        args += ["--precheck", str(template["precheck"])]
    if template.get("repo"):
        args += ["--repo", str(template["repo"])]
    if template.get("workspace"):
        args += ["--workspace", str(template["workspace"])]
    if template.get("reuse_session"):
        args += ["--reuse-session"]
    if template.get("extra_agent_args"):
        args += [f"--extra-agent-args={template['extra_agent_args']}"]
    if not enable:
        args += ["--disabled"]
    return args


def main() -> int:
    parser = argparse.ArgumentParser(description="Orca automation templates")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--project", type=Path, default=argparse.SUPPRESS)
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    templates_p = sub.add_parser("templates")
    common(templates_p)
    list_p = sub.add_parser("list")
    common(list_p)

    create_p = sub.add_parser("create")
    common(create_p)
    create_p.add_argument("--template", required=True)
    create_p.add_argument("--apply", action="store_true")
    create_p.add_argument("--enable", action="store_true")

    run_p = sub.add_parser("run")
    common(run_p)
    run_p.add_argument("--id", required=True)

    runs_p = sub.add_parser("runs")
    common(runs_p)
    runs_p.add_argument("--id", required=True)

    remove_p = sub.add_parser("remove")
    common(remove_p)
    remove_p.add_argument("--id", required=True)

    args = parser.parse_args()
    project = project_root(args.project)
    try:
        if args.command == "templates":
            names = sorted(
                path.stem for path in TEMPLATES.glob("*.y*ml") if path.is_file()
            )
            data = {"ok": True, "templates": names}
        elif args.command == "list":
            data = orca(["automations", "list", "--json"], project)
        elif args.command == "create":
            template = load_template(args.template)
            command = create_command(template, enable=args.enable)
            if not args.apply:
                data = {"ok": True, "command": shlex.join(command), "applied": False}
            else:
                data = orca(command, project)
                data["applied"] = True
        elif args.command == "run":
            data = orca(["automations", "run", args.id, "--json"], project)
        elif args.command == "runs":
            data = orca(["automations", "runs", "--id", args.id, "--json"], project)
        else:
            data = orca(["automations", "remove", args.id, "--json"], project)
    except RuntimeError as exc:
        print(f"automations: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif data.get("command"):
        print(data["command"])
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
