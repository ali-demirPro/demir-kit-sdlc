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
sys.path.insert(0, str(SCRIPTS))
import routing  # noqa: E402
import epic_worktree  # noqa: E402

PROJECT = routing.project_root(ROOT)


def orca(args: list[str]) -> str:
    try:
        result = subprocess.run(["orca", *args], capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit("orca_wave: orca CLI yok; degrade modda wave çalıştırılmaz")
    if result.returncode != 0:
        sys.exit(f"orca_wave: orca failed — {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def start_command(
    task: dict,
    agent: str,
    worktree: str,
    task_id: str | None = None,
    run_id: str | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> list[str]:
    command = ["orca", "orchestration", "worker-start"]
    if task_id:
        command += ["--task", task_id]
    else:
        command += ["--spec", task["spec"]]
    command += ["--worktree", worktree, "--agent", agent]
    if run_id:
        command += ["--run", run_id]
    if model:
        command += ["--model", model]
    if effort:
        command += ["--effort", effort]
    command += ["--json"]
    return command


def task_command(task: dict, run_id: str, deps: list[str]) -> list[str]:
    command = [
        "orca",
        "orchestration",
        "task-create",
        "--spec",
        task["spec"],
        "--task-title",
        str(task.get("title") or task["id"]),
        "--deps",
        json.dumps(deps),
        "--run",
        run_id,
        "--json",
    ]
    return command


def try_orca(args: list[str]) -> dict | None:
    try:
        raw = orca(args)
    except SystemExit:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) and data.get("ok") else None


def ensure_run_id(plan: dict, args) -> tuple[str | None, dict]:
    """Resume the epic Run when possible; create one only for a new epic."""
    epic = plan.get("epic") or getattr(args, "epic", None)
    if not epic:
        raw = orca(["orchestration", "run-create", "--objective", args.objective, "--json"])
        return (json.loads(raw).get("result") or {}).get("run", {}).get("id"), {}
    project = PROJECT
    state = epic_worktree.load_state(project, int(epic))
    run_id = str(state.get("run_id") or "")
    if run_id:
        resumed = try_orca(["orchestration", "run-use", "--id", run_id, "--json"])
        if resumed:
            return run_id, state
        shown = try_orca(["orchestration", "run-show", "--id", run_id, "--json"])
        if shown:
            # The Run exists but this terminal is not its coordinator; worker
            # commands can still target it explicitly with --run.
            return run_id, state
    raw = orca(["orchestration", "run-create", "--objective", args.objective, "--json"])
    run = (json.loads(raw).get("result") or {}).get("run") or {}
    run_id = run.get("id")
    if run_id:
        state["run_id"] = run_id
        epic_worktree.save_state(project, int(epic), state)
    return run_id, state


def create_tasks(plan: dict, run_id: str | None, state: dict) -> dict[str, dict]:
    """Create one Orca Task per CP; deps must be created first."""
    if not run_id:
        return {}
    created: dict[str, dict] = {}
    stored = state.setdefault("tasks", {})
    for task in plan.get("tasks") or []:
        task_key = str(task.get("id") or "")
        if not task_key:
            continue
        if isinstance(stored.get(task_key), dict) and stored[task_key].get("task_id"):
            created[task_key] = stored[task_key]
            continue
        dep_ids = []
        for dep in task.get("deps") or []:
            dep_key = str(dep).replace("task:", "")
            dep_record = created.get(dep_key) or stored.get(dep_key) or {}
            if dep_record.get("task_id"):
                dep_ids.append(dep_record["task_id"])
        payload = try_orca(task_command(task, run_id, dep_ids)[1:])
        if not payload:
            return {}
        task_id = (payload.get("result") or {}).get("taskId") or (
            payload.get("result") or {}
        ).get("id")
        if not task_id:
            return {}
        record = {
            "task_id": task_id,
            "status": "pending",
            "dispatch_id": None,
        }
        gate = task.get("gate")
        if isinstance(gate, dict) and gate.get("question"):
            gate_args = [
                "orchestration",
                "gate-create",
                "--task",
                task_id,
                "--question",
                str(gate["question"]),
                "--json",
            ]
            if gate.get("options"):
                gate_args += ["--options", json.dumps(gate["options"])]
            gate_payload = try_orca(gate_args)
            gate_result = (gate_payload or {}).get("result") or {}
            gate_id = gate_result.get("gateId") or gate_result.get("id")
            if gate_id:
                record["gate_id"] = gate_id
        created[task_key] = record
        stored[task_key] = record
    if plan.get("epic"):
        epic_worktree.save_state(PROJECT, int(plan["epic"]), state)
    return created


def update_task(
    task_id: str | None, status: str, result: str | None, run_id: str | None
) -> None:
    if not task_id:
        return
    args = [
        "orchestration",
        "task-update",
        "--id",
        task_id,
        "--status",
        status,
        "--json",
    ]
    if result:
        args += ["--result", result]
    if run_id:
        args += ["--run", run_id]
    try_orca(args)


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


def failed_dispatches(done: dict[str, dict]) -> list[str]:
    failed = []
    for dispatch, message in done.items():
        payload = message.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        if payload.get("outcome") == "failed":
            failed.append(dispatch)
    return sorted(failed)


def attention_messages(messages: list[dict]) -> list[dict]:
    return [
        message
        for message in messages
        if message.get("type") in {"question", "escalation"}
    ]


def summary_text(summary: dict) -> str:
    total = len(summary.get("tasks") or [])
    done = len(summary.get("done") or [])
    missing = len(summary.get("missing") or [])
    attention = len(summary.get("attention") or [])
    failed = len(summary.get("failed") or [])
    duration = summary.get("duration_seconds")
    suffix = f" ({duration}s)" if duration is not None else ""
    if failed:
        return f"{total} görevden {done} tamamlandı; {failed} başarısız{suffix}."
    if missing:
        return f"{total} görevden {done} tamamlandı; {missing} eksik{suffix}."
    if attention:
        return f"{total} görevden {done} tamamlandı; insan kararı gerekiyor{suffix}."
    return f"{total} worker paralel çalıştı; hepsi tamamlandı{suffix}."


def notify_command(issue: int, summary: dict) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPTS / "update.py"),
        "--issue",
        str(issue),
        "--kind",
        "summary",
        "--who",
        "Orca wave",
        "--what",
        summary_text(summary),
        "--decision",
        "Bağımsız görevler aynı run'da paralel çalıştırıldı.",
        "--next",
        "Sonuçları issue'da inceleyin.",
    ]
    if summary.get("missing") or summary.get("attention") or summary.get("failed"):
        command += [
            "--approval",
            "yes",
            "--ask",
            "Eksik/başarısız worker'ı inceleyip yeni bir dalga başlatalım mı?",
        ]
    return command


def normalize_dep(value: str) -> str:
    return value[5:] if value.startswith("task:") else value


def topological_waves(tasks: list[dict]) -> list[list[str]]:
    ids = [task["id"] for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task id")
    by_id = {task["id"]: task for task in tasks}
    deps = {
        task["id"]: {normalize_dep(dep) for dep in (task.get("deps") or [])}
        for task in tasks
    }
    for task_id, dep_set in deps.items():
        missing = dep_set - set(by_id)
        if missing:
            raise ValueError(f"{task_id}: unknown dependency {sorted(missing)}")
    done: set[str] = set()
    waves: list[list[str]] = []
    while deps:
        ready_ids = {task_id for task_id, dep_set in deps.items() if dep_set <= done}
        if not ready_ids:
            raise ValueError("dependency cycle")
        ready = [task_id for task_id in ids if task_id in ready_ids]
        waves.append(ready)
        for task_id in ready:
            done.add(task_id)
            del deps[task_id]
    return waves


def execute_dag(plan: dict, args) -> dict:
    tasks = plan.get("tasks") or []
    waves = topological_waves(tasks)
    by_id = {task["id"]: task for task in tasks}

    if args.dry_run:
        commands = [["orca", "orchestration", "run-create", "--objective", args.objective, "--json"]]
        for index, wave in enumerate(waves, 1):
            if not args.json:
                print(f"[dry-run] wave {index}: {', '.join(wave)}")
            for task_id in wave:
                commands.append(start_command(by_id[task_id], args.agent, args.worktree))
        task_commands = [
            task_command(
                by_id[task_id],
                "<run_id>",
                [f"task:{dep}" for dep in by_id[task_id].get("deps") or []],
            )
            for wave in waves
            for task_id in wave
        ]
        if not args.json:
            for command in commands:
                print("[dry-run] " + shlex.join(command))
            for command in task_commands:
                print("[dry-run] " + shlex.join(command))
        return {
            "dry_run": True,
            "run_id": None,
            "tasks": [{"id": task["id"]} for task in tasks],
            "waves": [{"tasks": wave, "done": [], "missing": [], "failed": []} for wave in waves],
            "done": [],
            "missing": [],
            "failed": [],
            "attention": [],
            "commands": [shlex.join(command) for command in commands],
            "task_commands": [shlex.join(command) for command in task_commands],
        }

    run_id, state = ensure_run_id(plan, args)
    task_map = create_tasks(plan, run_id, state)
    started_at = time.monotonic()
    deadline = time.time() + args.timeout_ms / 1000
    receipts: list[dict] = []
    done: dict[str, dict] = {}
    attention: list[dict] = []
    wave_results: list[dict] = []

    for wave in waves:
        wave_receipts = []
        for task_id in wave:
            task = by_id[task_id]
            record = task_map.get(task_id) or {}
            raw = orca(
                [
                    "orchestration",
                    "worker-start",
                    *start_command(
                        task,
                        str(task.get("agent") or args.agent),
                        args.worktree,
                        record.get("task_id"),
                        run_id,
                        task.get("model"),
                        task.get("effort"),
                    )[3:],
                ]
            )
            receipt = json.loads(raw)
            if not receipt.get("ok"):
                sys.exit(f"orca_wave: worker-start failed for {task_id}: {receipt.get('error')}")
            result = receipt["result"]
            item = {
                "id": task_id,
                "task_id": result.get("taskId") or record.get("task_id"),
                "dispatch_id": result["dispatchId"],
                "terminal": next(
                    (effect.get("id") for effect in result.get("effects") or [] if effect.get("kind") == "terminal"),
                    None,
                ),
            }
            if item["task_id"] and plan.get("epic"):
                stored = state.setdefault("tasks", {}).setdefault(task_id, {})
                stored.update(
                    {
                        "task_id": item["task_id"],
                        "dispatch_id": item["dispatch_id"],
                        "status": "dispatched",
                    }
                )
                epic_worktree.save_state(PROJECT, int(plan["epic"]), state)
            receipts.append(item)
            wave_receipts.append(item)

        expected = {item["dispatch_id"] for item in wave_receipts}
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

        for item in wave_receipts:
            if item["dispatch_id"] in done:
                message = done[item["dispatch_id"]]
                payload = message.get("payload") or {}
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        payload = {}
                outcome = payload.get("outcome")
                update_task(
                    item.get("task_id"),
                    "completed" if outcome == "succeeded" else "failed",
                    json.dumps(
                        {
                            "outcome": outcome,
                            "subject": message.get("subject"),
                        },
                        ensure_ascii=False,
                    ),
                    run_id,
                )
                orca(["orchestration", "worker-release", "--dispatch", item["dispatch_id"], "--json"])

        missing = sorted(expected - set(done))
        failed = failed_dispatches(done)
        wave_results.append(
            {
                "tasks": wave,
                "done": sorted(expected - set(missing)),
                "missing": missing,
                "failed": failed,
            }
        )
        if missing or attention or failed:
            break

    summary = {
        "dry_run": False,
        "run_id": run_id,
        "tasks": receipts,
        "waves": wave_results,
        "done": sorted(done),
        "missing": sorted(set(item["dispatch_id"] for item in receipts) - set(done)),
        "failed": failed_dispatches(done),
        "attention": [
            {"type": item.get("type"), "subject": item.get("subject")} for item in attention
        ],
        "commands": [],
        "duration_seconds": round(time.monotonic() - started_at),
    }
    return summary


def load_plan(args) -> dict:
    if args.from_json:
        return json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    if not args.issue:
        sys.exit("orca_wave: --issue or --from-json required")
    output = subprocess.check_output(
        [sys.executable, str(SCRIPTS / "orca_plan.py"), str(args.issue), "--json"],
        text=True,
        cwd=PROJECT,
    )
    return json.loads(output)


def resolve_worktree(plan: dict, args) -> dict | None:
    """Resolve ``--worktree epic`` to the single epic worktree."""
    if args.worktree != "epic":
        return None
    epic = plan.get("epic") or args.epic
    if not epic:
        # Older plan payloads (or --from-json without an epic) keep the old
        # current-worktree behaviour; sealed plans always carry an epic.
        args.worktree = "current"
        return None
    try:
        record = epic_worktree.ensure(
            int(epic), PROJECT, create=not args.dry_run
        )
    except epic_worktree.WorktreeError as exc:
        if not args.dry_run:
            sys.exit(f"orca_wave: epic worktree hazır değil — {exc}")
        record = {
            "epic": int(epic),
            "name": epic_worktree.epic_name(int(epic)),
            "path": f"<{epic_worktree.epic_name(int(epic))}>",
            "branch": epic_worktree.epic_name(int(epic)),
            "run_id": None,
        }
    args.worktree = str(record.get("path") or "current")
    return record


def execute_wave(plan: dict, args) -> dict:
    tasks = ready_tasks(plan)
    if not tasks:
        sys.exit("orca_wave: no ready tasks (all depend on something)")

    if args.dry_run:
        commands = [
            ["orca", "orchestration", "run-create", "--objective", args.objective, "--json"]
        ]
        commands += [start_command(task, args.agent, args.worktree) for task in tasks]
        task_commands = [task_command(task, "<run_id>", []) for task in tasks]
        if not args.json:
            for command in commands:
                print("[dry-run] " + shlex.join(command))
            for command in task_commands:
                print("[dry-run] " + shlex.join(command))
        return {
            "dry_run": True,
            "run_id": None,
            "tasks": [{"id": task["id"]} for task in tasks],
            "done": [],
            "missing": [],
            "attention": [],
            "commands": [shlex.join(command) for command in commands],
            "task_commands": [shlex.join(command) for command in task_commands],
        }

    run_id, state = ensure_run_id(plan, args)
    task_map = create_tasks(plan, run_id, state)
    started = time.monotonic()

    receipts = []
    for task in tasks:
        record = task_map.get(str(task["id"])) or {}
        raw = orca(
            [
                "orchestration",
                "worker-start",
                *start_command(
                    task,
                    str(task.get("agent") or args.agent),
                    args.worktree,
                    record.get("task_id"),
                    run_id,
                    task.get("model"),
                    task.get("effort"),
                )[3:],
            ]
        )
        receipt = json.loads(raw)
        if not receipt.get("ok"):
            sys.exit(f"orca_wave: worker-start failed for {task['id']}: {receipt.get('error')}")
        result = receipt["result"]
        item = {
            "id": task["id"],
            "task_id": result.get("taskId") or record.get("task_id"),
            "dispatch_id": result["dispatchId"],
            "terminal": next(
                (effect.get("id") for effect in result.get("effects") or [] if effect.get("kind") == "terminal"),
                None,
            ),
        }
        if item["task_id"] and plan.get("epic"):
            stored = state.setdefault("tasks", {}).setdefault(str(task["id"]), {})
            stored.update(
                {
                    "task_id": item["task_id"],
                    "dispatch_id": item["dispatch_id"],
                    "status": "dispatched",
                }
            )
            epic_worktree.save_state(PROJECT, int(plan["epic"]), state)
        receipts.append(item)

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
            message = done[item["dispatch_id"]]
            payload = message.get("payload") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {}
            outcome = payload.get("outcome")
            update_task(
                item.get("task_id"),
                "completed" if outcome == "succeeded" else "failed",
                json.dumps(
                    {"outcome": outcome, "subject": message.get("subject")},
                    ensure_ascii=False,
                ),
                run_id,
            )
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
        "duration_seconds": round(time.monotonic() - started),
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="independent Orca task wave")
    parser.add_argument("--issue", type=int)
    parser.add_argument("--from-json", help="plan-like JSON with tasks[]")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dag", action="store_true", help="run dependency waves")
    parser.add_argument("--notify", action="store_true", help="post one human summary comment")
    parser.add_argument("--objective", default="demir-kit wave")
    parser.add_argument("--agent", default="opencode2")
    parser.add_argument(
        "--worktree",
        default="epic",
        help="'epic' (varsayılan), 'current' veya hazır bir worktree yolu",
    )
    parser.add_argument("--epic", type=int, default=None)
    parser.add_argument("--timeout-ms", type=int, default=240_000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.execute:
        args.dry_run = False
    if not args.execute and not args.dry_run:
        args.dry_run = True

    plan = load_plan(args)
    worktree = resolve_worktree(plan, args)
    summary = execute_dag(plan, args) if args.dag else execute_wave(plan, args)
    if worktree is not None:
        summary["epic_worktree"] = {
            "name": worktree.get("name"),
            "path": worktree.get("path"),
            "branch": worktree.get("branch"),
            "run_id": worktree.get("run_id"),
        }
        if args.dry_run and not args.json:
            print(
                "[dry-run] orca worktree create --name "
                f"{worktree.get('name')} --issue {worktree.get('epic')} "
                "--json"
            )

    if args.notify:
        if not args.issue:
            sys.exit("orca_wave: --notify requires --issue")
        if args.dry_run:
            message = "[notify skipped: dry-run] " + " ".join(notify_command(args.issue, summary))
            print(message, file=sys.stderr if args.json else sys.stdout)
        else:
            result = subprocess.run(
                notify_command(args.issue, summary),
                cwd=PROJECT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                sys.exit(
                    "orca_wave: human summary could not be posted — "
                    + (result.stderr.strip() or result.stdout.strip())
                )

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"run: {summary['run_id'] or '(dry-run)'}")
        for item in summary["tasks"]:
            print(f"  - {item['id']} task={item.get('task_id')} dispatch={item.get('dispatch_id')}")
        print(f"done: {len(summary['done'])} · missing: {len(summary['missing'])}")
        if summary.get("attention"):
            print(f"attention: {len(summary['attention'])}")
    return 1 if summary["missing"] or summary.get("attention") or summary.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
