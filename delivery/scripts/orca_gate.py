#!/usr/bin/env python3
"""Enforce the epic worktree + orchestration run gate.

Orca availability is measured, never self-declared. When Orca is running, a
source change must happen in the epic worktree with a bound run and at least one
orchestration task. ``degrade`` is the only escape and it leaves an issue record.
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
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import epic_worktree  # noqa: E402
import routing  # noqa: E402


def project_root(project: Path | None = None) -> Path:
    return Path(project).resolve() if project else routing.project_root(ROOT)


def repo_name(project: Path) -> str:
    config = epic_worktree.load_config(project)
    repo = (config.get("tracker") or {}).get("repo")
    if not repo:
        try:
            ecosystem = yaml.safe_load(
                (project / "ecosystem.yaml").read_text(encoding="utf-8")
            ) or {}
        except (FileNotFoundError, yaml.YAMLError):
            ecosystem = {}
        repo = (ecosystem.get("tracker") or {}).get("repo")
    return str(repo or "")


def fetch_issue(project: Path, number: int) -> dict:
    repo = repo_name(project)
    if not repo:
        raise RuntimeError("tracker.repo yok; Orca kapısı doğrulanamıyor")
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/issues/{number}"],
        cwd=str(project),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"issue #{number} okunamadı")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise RuntimeError(f"issue #{number} okunamadı")
    return data


def task_count(project: Path, run_id: str | None) -> int:
    if not run_id:
        return 0
    payload = epic_worktree.orca_json(
        ["orchestration", "task-list", "--run", run_id, "--json"], project
    )
    result = (payload or {}).get("result") or {}
    tasks = result.get("tasks") or []
    return len(tasks) if isinstance(tasks, list) else 0


def degrade_record(project: Path, issue: int) -> dict | None:
    path = (
        epic_worktree.main_root(project)
        / epic_worktree.STATE_DIR
        / f"degrade-{issue}.json"
    )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def evaluate(project: Path, issue: dict) -> dict:
    project = project_root(project)
    if not epic_worktree.epic_worktree_enabled(project):
        return {
            "ok": True,
            "mode": "disabled",
            "reason": "orca.epic_worktree kapalı",
        }
    number = int(issue.get("number") or 0)
    recorded = degrade_record(project, number)
    if recorded:
        return {
            "ok": True,
            "mode": "degrade",
            "reason": str(recorded.get("reason") or "kayıtlı degrade"),
        }
    if not epic_worktree.orca_available(project):
        return {
            "ok": False,
            "mode": "degrade",
            "reason": (
                "Orca çalışmıyor ve kayıtlı degrade yok; "
                "`guard.sh --issue N --degrade --reason \"...\"` ile kaydet"
            ),
        }

    seal = routing.seal_body(issue.get("body") or "")
    epic = seal.get("epic")
    if not epic:
        return {
            "ok": True,
            "mode": "normal",
            "reason": "leaf epic'e bağlı değil; worktree kapısı uygulanmaz",
        }
    try:
        checked = epic_worktree.check(int(epic), project)
    except epic_worktree.WorktreeError as exc:
        return {"ok": False, "mode": "blocked", "reason": str(exc), "epic": epic}

    run_id = checked.get("run_id")
    if not run_id:
        return {
            "ok": False,
            "mode": "blocked",
            "reason": (
                f"epic #{epic} için orchestration run yok; "
                f"`orca orchestration run-create --objective \"epic #{epic}\"`"
            ),
            "epic": epic,
        }
    if task_count(project, run_id) == 0:
        return {
            "ok": False,
            "mode": "blocked",
            "reason": (
                f"epic #{epic} run'ında task yok; "
                "`orca orchestration task-create` ile CP task'ı aç"
            ),
            "epic": epic,
            "run_id": run_id,
        }
    return {
        "ok": True,
        "mode": "orca",
        "epic": epic,
        "run_id": run_id,
        "path": checked.get("path"),
        "branch": checked.get("branch"),
    }


def orca_action(project: Path, args: list[str]) -> dict:
    payload = epic_worktree.orca_json(args, project)
    if not payload or not payload.get("ok"):
        message = ""
        if payload:
            message = str((payload.get("error") or {}).get("message") or "")
        raise RuntimeError(message or f"orca {' '.join(args[:2])} başarısız")
    return payload


def ask(
    project: Path,
    question: str,
    options: list[str] | None = None,
    run_id: str | None = None,
    timeout_ms: int = 600_000,
) -> dict:
    if not 1 <= timeout_ms <= 1_800_000:
        raise RuntimeError("ask timeout 1–1800000 ms arasında olmalı")
    args = ["orchestration", "ask", "--question", question, "--timeout-ms", str(timeout_ms), "--json"]
    if run_id:
        args += ["--run", run_id]
    if options:
        args += ["--options", ",".join(options)]
    return orca_action(project, args)


def reply(project: Path, message_id: str, answer: str) -> dict:
    return orca_action(
        project,
        [
            "orchestration",
            "reply",
            "--id",
            message_id,
            "--body",
            answer,
            "--json",
        ],
    )


def gate_create(
    project: Path, task_id: str, question: str, options: list[str] | None = None
) -> dict:
    args = [
        "orchestration",
        "gate-create",
        "--task",
        task_id,
        "--question",
        question,
        "--json",
    ]
    if options:
        args += ["--options", json.dumps(options)]
    return orca_action(project, args)


def gate_resolve(project: Path, gate_id: str, resolution: str) -> dict:
    return orca_action(
        project,
        [
            "orchestration",
            "gate-resolve",
            "--id",
            gate_id,
            "--resolution",
            resolution,
            "--json",
        ],
    )


def gate_list(project: Path) -> dict:
    return orca_action(project, ["orchestration", "gate-list", "--json"])


def inbox(project: Path, peek: bool = False) -> dict:
    return orca_action(project, ["orchestration", "inbox", "--json"])


def send(
    project: Path,
    to: str,
    subject: str,
    body: str = "",
    type_: str = "status",
) -> dict:
    args = [
        "orchestration",
        "send",
        "--to",
        to,
        "--subject",
        subject,
        "--type",
        type_,
        "--json",
    ]
    if body:
        args += ["--body", body]
    return orca_action(project, args)


def record_degrade(project: Path, issue: int, reason: str) -> dict:
    project = project_root(project)
    repo = repo_name(project)
    if not repo:
        raise RuntimeError("tracker.repo yok; degrade kaydı yazılamıyor")
    body = f"run degrade: issue #{issue}\nreason: {reason}"
    result = subprocess.run(
        ["gh", "issue", "comment", str(issue), "--repo", repo, "--body", body],
        cwd=str(project),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "degrade kaydı issue'ya yazılamadı: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    path = (
        epic_worktree.main_root(project)
        / epic_worktree.STATE_DIR
        / f"degrade-{issue}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "issue": issue,
                "reason": reason,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {"ok": True, "mode": "degrade", "issue": issue, "reason": reason}


def main() -> int:
    parser = argparse.ArgumentParser(description="Orca worktree/run gate")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--project", type=Path, default=argparse.SUPPRESS)
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    check_p = sub.add_parser("check")
    common(check_p)
    check_p.add_argument("--issue", type=int, required=True)

    degrade_p = sub.add_parser("degrade")
    common(degrade_p)
    degrade_p.add_argument("--issue", type=int, required=True)
    degrade_p.add_argument("--reason", required=True)

    ask_p = sub.add_parser("ask")
    common(ask_p)
    ask_p.add_argument("--question", required=True)
    ask_p.add_argument("--options", help="virgülle ayrılmış seçenekler")
    ask_p.add_argument("--run")
    ask_p.add_argument("--timeout-ms", type=int, default=600_000)

    reply_p = sub.add_parser("reply")
    common(reply_p)
    reply_p.add_argument("--id", required=True)
    reply_p.add_argument("--body", required=True)

    gate_p = sub.add_parser("gate-create")
    common(gate_p)
    gate_p.add_argument("--task", required=True)
    gate_p.add_argument("--question", required=True)
    gate_p.add_argument("--options", help="JSON dizi veya virgülle ayrılmış")

    resolve_p = sub.add_parser("gate-resolve")
    common(resolve_p)
    resolve_p.add_argument("--id", required=True)
    resolve_p.add_argument("--resolution", required=True)

    gate_list_p = sub.add_parser("gate-list")
    common(gate_list_p)

    inbox_p = sub.add_parser("inbox")
    common(inbox_p)

    send_p = sub.add_parser("send")
    common(send_p)
    send_p.add_argument("--to", required=True)
    send_p.add_argument("--subject", required=True)
    send_p.add_argument("--body", default="")
    send_p.add_argument("--type", default="status")

    args = parser.parse_args()
    try:
        if args.command == "degrade":
            data = record_degrade(args.project, args.issue, args.reason)
        elif args.command == "ask":
            options = [item.strip() for item in (args.options or "").split(",") if item.strip()]
            data = ask(args.project, args.question, options, args.run, args.timeout_ms)
        elif args.command == "reply":
            data = reply(args.project, args.id, args.body)
        elif args.command == "gate-create":
            raw = args.options or ""
            try:
                options = json.loads(raw) if raw.strip().startswith("[") else [
                    item.strip() for item in raw.split(",") if item.strip()
                ]
            except json.JSONDecodeError:
                options = [item.strip() for item in raw.split(",") if item.strip()]
            data = gate_create(args.project, args.task, args.question, options)
        elif args.command == "gate-resolve":
            data = gate_resolve(args.project, args.id, args.resolution)
        elif args.command == "gate-list":
            data = gate_list(args.project)
        elif args.command == "inbox":
            data = inbox(args.project)
        elif args.command == "send":
            data = send(args.project, args.to, args.subject, args.body, args.type)
        else:
            data = evaluate(args.project, fetch_issue(args.project, args.issue))
    except (RuntimeError, json.JSONDecodeError) as exc:
        data = {"ok": False, "mode": "blocked", "reason": str(exc)}

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        prefix = "OK" if data.get("ok") else "BLOCKED"
        print(f"orca_gate: {prefix} ({data.get('mode')}) — {data.get('reason') or '-'}")
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
