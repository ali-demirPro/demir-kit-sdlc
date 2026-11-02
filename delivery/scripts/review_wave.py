#!/usr/bin/env python3
"""Run independent reviewers as one parallel Orca wave.

Usage:
  python3 delivery/scripts/review_wave.py --issue 156 --cp CP-1 --commit HEAD
  python3 delivery/scripts/review_wave.py --issue 156 --cp CP-1 --commit HEAD \
      --reviewers adversarial-a,adversarial-b --apply
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import closure  # noqa: E402
import review_packet  # noqa: E402
import routing  # noqa: E402
import worker_cleanup  # noqa: E402

SETTLED = {"succeeded", "failed", "stopped"}


def orca(args: list[str]) -> dict:
    try:
        result = subprocess.run(
            ["orca", *args], capture_output=True, text=True, timeout=180
        )
    except (FileNotFoundError, OSError):
        return {}
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict) or not payload.get("ok"):
        return {}
    data = payload.get("result")
    return data if isinstance(data, dict) else {}


def epic_of(issue: int) -> int | None:
    payload = json.loads(
        review_packet.gh(
            ["api", f"repos/{review_packet.repo_name()}/issues/{issue}"]
        )
    )
    seal = routing.seal_body(payload.get("body") or "")
    epic = seal.get("epic")
    return int(epic) if isinstance(epic, int) else None


def reviewer_spec(name: str, packet: str, issue: int, cp_id: str) -> str:
    return (
        f"demir-kit #{issue} {cp_id} — bağımsız reviewer {name}\n\n"
        f"{packet}\n\n"
        "Görev: paketi incele. Gerekirse yalnız paketteki değişen dosyaları aç "
        "(rg/sed); tüm repoyu tarama, dosya değiştirme.\n"
        "Son mesaj biçimi:\n"
        "approved: true|false\n"
        "findings:\n"
        "- {severity, location, reason}\n"
        "not: tek cümle\n"
    )


def parse_verdict(text: str) -> bool | None:
    matches = re.findall(
        r"approved:\s*(true|false)\s*$", text or "", re.I | re.M
    )
    if matches:
        return matches[-1].lower() == "true"
    lowered = (text or "").lower()
    if "true|false" in lowered:
        return None
    if (
        "rejected" in lowered
        or "not approved" in lowered
        or "approved=false" in lowered
        or "approved: false" in lowered
        or "not yet approved" in lowered
        or "not approved yet" in lowered
        or "onaylanmadı" in lowered
    ):
        return False
    if "approved" in lowered or "onaylandı" in lowered:
        return True
    return None


def start_worker(
    name: str, spec: str, run_id: str, worktree: str
) -> dict:
    task = orca(
        [
            "orchestration",
            "task-create",
            "--spec",
            spec,
            "--task-title",
            name,
            "--deps",
            "[]",
            "--run",
            run_id,
            "--json",
        ]
    )
    task_id = str((task.get("task") or {}).get("id") or task.get("taskId") or "")
    if not task_id:
        return {"name": name, "error": "task oluşmadı"}
    started = orca(
        [
            "orchestration",
            "worker-start",
            "--timeout-ms",
            "300000",
            "--task",
            task_id,
            "--worktree",
            worktree,
            "--agent",
            "opencode2",
            "--run",
            run_id,
            "--json",
        ]
    )
    dispatch = str(started.get("dispatchId") or "")
    return {
        "name": name,
        "task_id": task_id,
        "dispatch_id": dispatch,
        "state": "dispatched" if dispatch else "failed",
        "error": None if dispatch else "worker başlamadı",
    }


def wait_workers(workers: list[dict], timeout: int, poll: int = 5) -> list[dict]:
    deadline = time.time() + timeout
    while True:
        pending = []
        for item in workers:
            if not item.get("dispatch_id") or item.get("state") in SETTLED:
                continue
            shown = orca(
                [
                    "orchestration",
                    "worker-show",
                    "--dispatch",
                    str(item["dispatch_id"]),
                    "--json",
                ]
            )
            state = str((shown.get("worker") or {}).get("state") or "")
            if state in SETTLED:
                item["state"] = state
            else:
                pending.append(item)
        if not pending or time.time() >= deadline:
            break
        time.sleep(poll)
    return workers


def read_output(dispatch_id: str) -> str:
    data = orca(
        [
            "orchestration",
            "worker-read",
            "--dispatch",
            dispatch_id,
            "--source",
            "auto",
            "--json",
        ]
    )
    terminal = data.get("terminal") or {}
    return "\n".join(str(line) for line in terminal.get("tail") or [])


def collect(workers: list[dict], run_id: str | None = None) -> list[dict]:
    check = (
        orca(["orchestration", "check", "--run", run_id, "--json"])
        if run_id
        else {}
    )
    messages = check.get("messages") or []
    texts: dict[str, str] = {}
    for message in messages:
        handle = str(message.get("from_handle") or "")
        if handle:
            texts[handle] = (
                f"{message.get('subject') or ''}\n{message.get('body') or ''}"
            )
    for item in workers:
        if not item.get("dispatch_id"):
            item["verdict"] = None
            continue
        shown = orca(
            [
                "orchestration",
                "worker-show",
                "--dispatch",
                str(item["dispatch_id"]),
                "--json",
            ]
        )
        handle = str((shown.get("worker") or {}).get("agentTerminalHandle") or "")
        output = read_output(str(item["dispatch_id"]))
        if handle and handle in texts:
            output += "\n" + texts[handle]
        item["verdict"] = parse_verdict(output)
        item["summary"] = "\n".join(output.splitlines()[-25:])
        worker_cleanup.release(str(item["dispatch_id"]))
    delivery = str(check.get("deliveryId") or "")
    if run_id and delivery:
        orca(
            ["orchestration", "check", "--run", run_id, "--ack", delivery]
        )
    return workers


def main() -> int:
    parser = argparse.ArgumentParser(description="parallel reviewer wave")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--cp", required=True)
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--delta")
    parser.add_argument(
        "--base", help="full CP range base (default: origin/main merge-base)"
    )
    parser.add_argument("--reviewers", default="adversarial-a")
    parser.add_argument("--max-chars", type=int, default=12_000)
    parser.add_argument("--run", help="Orca run id (default: epic run)")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    names = [name.strip() for name in args.reviewers.split(",") if name.strip()]
    if not names:
        raise SystemExit("review_wave: reviewer yok")
    packet = review_packet.packet_for(
        args.issue, args.cp, args.commit, args.delta, args.max_chars, args.base
    )
    specs = {name: reviewer_spec(name, packet, args.issue, args.cp) for name in names}
    plan = {
        "issue": args.issue,
        "cp_id": args.cp,
        "commit": args.commit,
        "reviewers": names,
        "packet_chars": len(packet.encode("utf-8")),
        "spec_chars": {name: len(spec.encode("utf-8")) for name, spec in specs.items()},
    }
    if not args.apply:
        print(
            json.dumps(plan, ensure_ascii=False, indent=2)
            if args.json
            else "\n".join(
                [
                    f"Reviewer wave — #{args.issue} {args.cp}",
                    "reviewer: " + ", ".join(names),
                    f"paket: {plan['packet_chars']} bayt",
                    "başlatmak için --apply",
                ]
            )
        )
        return 0

    run_id = args.run
    if not run_id:
        epic = epic_of(args.issue)
        run_id = closure.run_id_for(epic) if epic else None
    if not run_id:
        raise SystemExit("review_wave: Orca run bulunamadı (--run ver)")
    worktree = str(routing.project_root(ROOT))

    workers = [
        start_worker(name, specs[name], run_id, worktree) for name in names
    ]
    workers = wait_workers(workers, args.timeout)
    workers = collect(workers, run_id)
    verdicts = {
        item["name"]: (
            None if item.get("verdict") is None else bool(item["verdict"])
        )
        for item in workers
    }
    approved = all(value is True for value in verdicts.values())
    result = {
        **plan,
        "run_id": run_id,
        "workers": workers,
        "verdicts": verdicts,
        "approved": approved,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in workers:
            verdict = item.get("verdict")
            label = "?" if verdict is None else ("approved" if verdict else "rejected")
            print(f"- {item['name']}: {label} ({item.get('state')})")
        print("approved" if approved else "rejected")
    return 0 if approved else 1


if __name__ == "__main__":
    sys.exit(main())
