#!/usr/bin/env python3
"""Run independent Orca tasks as one wave.

Default is a dry run. Pass --execute to start workers.

Usage:
  python3 delivery/scripts/orca_wave.py --issue 20
  python3 delivery/scripts/orca_wave.py --from-json /tmp/wave.json --execute --json
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent


def orca(args: list[str]) -> str:
    result = subprocess.run(["orca", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"orca_wave: orca failed — {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def start_command(task: dict, agent: str, worktree: str) -> list[str]:
    return [
        "orca",
        "orchestration",
        "worker-start",
        "--spec",
        task["spec"],
        "--worktree",
        worktree,
        "--agent",
        agent,
        "--json",
    ]


def ready_tasks(plan: dict) -> list[dict]:
    return [task for task in plan.get("tasks") or [] if not task.get("deps")]


def done_dispatches(messages: list[dict], expected: set[str]) -> dict[str, dict]:
    done: dict[str, dict] = {}
    for message in messages:
        if message.get("type") != "worker_done":
            continue
        payload = message.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        dispatch = payload.get("dispatchId")
        if dispatch in expected:
            done[dispatch] = message
    return done


def attention_messages(messages: list[dict]) -> list[dict]:
    return [
        message
        for message in messages
        if message.get("type") in {"question", "escalation"}
    ]


def load_plan(args) -> dict:
    if args.from_json:
        return json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    if not args.issue:
        sys.exit("orca_wave: --issue or --from-json required")
    output = subprocess.check_output(
        [sys.executable, str(SCRIPTS / "orca_plan.py"), str(args.issue), "--json"],
        text=True,
        cwd=ROOT,
    )
    return json.loads(output)


def execute_wave(plan: dict, args) -> dict:
    tasks = ready_tasks(plan)
    if not tasks:
        sys.exit("orca_wave: no ready tasks (all depend on something)")

    if args.dry_run:
        commands = [
            ["orca", "orchestration", "run-create", "--objective", args.objective, "--json"]
        ]
        commands += [start_command(task, args.agent, args.worktree) for task in tasks]
        if not args.json:
            for command in commands:
                print("[dry-run] " + shlex.join(command))
        return {
            "dry_run": True,
            "run_id": None,
            "tasks": [{"id": task["id"]} for task in tasks],
            "done": [],
            "missing": [],
            "attention": [],
            "commands": [shlex.join(command) for command in commands],
        }

    run = json.loads(
        orca(["orchestration", "run-create", "--objective", args.objective, "--json"])
    )["result"]["run"]
    run_id = run["id"]

    receipts = []
    for task in tasks:
        raw = orca(
            [
                "orchestration",
                "worker-start",
                *start_command(task, args.agent, args.worktree)[3:],
            ]
        )
        receipt = json.loads(raw)
        if not receipt.get("ok"):
            sys.exit(f"orca_wave: worker-start failed for {task['id']}: {receipt.get('error')}")
        result = receipt["result"]
        receipts.append(
            {
                "id": task["id"],
                "task_id": result["taskId"],
                "dispatch_id": result["dispatchId"],
                "terminal": next(
                    (item.get("id") for item in result.get("effects") or [] if item.get("kind") == "terminal"),
                    None,
                ),
            }
        )

    expected = {item["dispatch_id"] for item in receipts}
    done: dict[str, dict] = {}
    attention: list[dict] = []
    deadline = time.time() + args.timeout_ms / 1000
    while expected - set(done) and time.time() < deadline:
        remaining = int((deadline - time.time()) * 1000)
        raw = orca(
            [
                "orchestration",
                "check",
                "--run",
                run_id,
                "--wait",
                "--types",
                "worker_done,escalation,question",
                "--timeout-ms",
                str(min(remaining, 60_000)),
                "--json",
            ]
        )
        result = json.loads(raw).get("result") or {}
        messages = result.get("messages") or []
        done.update(done_dispatches(messages, expected))
        attention = attention_messages(messages)
        if attention:
            # Process before ack: a question/escalation needs a human or a reply.
            break
        delivery_id = result.get("deliveryId")
        if delivery_id:
            orca(
                [
                    "orchestration",
                    "check",
                    "--ack",
                    delivery_id,
                    "--run",
                    run_id,
                    "--json",
                ]
            )
        if result.get("timedOut"):
            continue

    for item in receipts:
        if item["dispatch_id"] in done:
            orca(["orchestration", "worker-release", "--dispatch", item["dispatch_id"], "--json"])

    summary = {
        "dry_run": False,
        "run_id": run_id,
        "tasks": receipts,
        "done": sorted(done),
        "missing": sorted(expected - set(done)),
        "attention": [
            {"type": item.get("type"), "subject": item.get("subject")} for item in attention
        ],
        "commands": [],
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="independent Orca task wave")
    parser.add_argument("--issue", type=int)
    parser.add_argument("--from-json", help="plan-like JSON with tasks[]")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--objective", default="demir-kit wave")
    parser.add_argument("--agent", default="opencode2")
    parser.add_argument("--worktree", default="current")
    parser.add_argument("--timeout-ms", type=int, default=240_000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.execute:
        args.dry_run = False
    if not args.execute and not args.dry_run:
        args.dry_run = True

    plan = load_plan(args)
    summary = execute_wave(plan, args)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"run: {summary['run_id'] or '(dry-run)'}")
        for item in summary["tasks"]:
            print(f"  - {item['id']} task={item.get('task_id')} dispatch={item.get('dispatch_id')}")
        print(f"done: {len(summary['done'])} · missing: {len(summary['missing'])}")
        if summary.get("attention"):
            print(f"attention: {len(summary['attention'])}")
    return 1 if summary["missing"] or summary.get("attention") else 0


if __name__ == "__main__":
    sys.exit(main())
