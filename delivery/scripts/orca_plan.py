#!/usr/bin/env python3
"""Turn a sealed demir-kit leaf into Orca task specs.

Usage:
  python3 delivery/scripts/orca_plan.py 17
  python3 delivery/scripts/orca_plan.py 17 --json
  python3 delivery/scripts/orca_plan.py 17 --write /tmp/orca-plan
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import routing  # noqa: E402


def gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"orca_plan: gh failed — {result.stderr.strip()}")
    return result.stdout


def repo_name() -> str:
    ecosystem = yaml.safe_load((ROOT / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        sys.exit("orca_plan: ecosystem.yaml tracker.repo yok")
    return repo


def build_plan(registry: dict, issue: int, title: str, body: str, labels: set[str]) -> dict:
    seal = routing.seal_body(body)
    if not seal:
        raise ValueError("issue seal (`demir-kit` bloğu) yok")
    if "agent-approved" not in labels:
        raise ValueError("leaf agent-approved değil")
    path_id, signal = routing.detect_path(registry, title, body, seal)
    agents = routing.resolve_agents(registry, path_id, signal)
    surfaces = ", ".join(seal.get("surfaces") or []) or "n/a"
    epic = seal.get("epic")
    risk = (seal.get("risk") or {}).get("level", "n/a")

    tasks = []
    for cp in seal.get("checkpoints") or []:
        if not isinstance(cp, dict):
            continue
        cp_id = cp.get("id")
        gates = cp.get("gates") or {}
        role = "designer" if gates.get("ui") else "developer"
        docs = "\n".join(f"- {item}" for item in routing.role_docs(role))
        deps = [f"task:{item}" for item in cp.get("depends_on") or []]
        spec = (
            f"demir-kit #{issue} {cp_id}: {cp.get('title', '')}\n"
            f"Target: issue #{issue}, epic #{epic}, surfaces: {surfaces}\n"
            f"Role: {role}\n"
            f"Read:\n{docs}\n"
            f"- delivery/CONTRACT.md\n"
            f"- delivery/policies/quality-gates.md\n"
            f"Change: implement only {cp_id} for this sealed leaf.\n"
            f"Ownership: edit only files required by {cp_id}; never touch other CPs, "
            f"the contract, CI or another agent's files. Surfaces: {surfaces}.\n"
            f"Constraints: no work outside issue #{issue}; do not self-approve; "
            f"do not touch other CPs; risk is {risk}.\n"
            f"Acceptance: `./delivery/scripts/doctor.sh --issue {issue} --checkpoint {cp_id}` "
            f"exit 0, then post evidence with agent: {role}.\n"
        )
        tasks.append(
            {
                "id": cp_id,
                "role": role,
                "deps": deps,
                "spec": spec,
            }
        )

    return {
        "issue": issue,
        "title": title,
        "epic": epic,
        "path_id": path_id,
        "signal": signal.get("id") if signal else None,
        "risk": risk,
        "active_agents": agents["active"],
        "tasks": tasks,
    }


def write_plan(plan: dict, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = [directory / "plan.json"]
    written[0].write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    for task in plan["tasks"]:
        path = directory / f"{task['id']}.md"
        path.write_text(task["spec"], encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="sealed leaf -> Orca task specs")
    parser.add_argument("issue", type=int)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()

    repo = repo_name()
    payload = json.loads(gh(["api", f"repos/{repo}/issues/{args.issue}"]))
    labels = {item.get("name") for item in payload.get("labels", [])}
    try:
        plan = build_plan(
            routing.load_registry(ROOT),
            args.issue,
            payload.get("title", ""),
            payload.get("body", "") or "",
            labels,
        )
    except ValueError as exc:
        sys.exit(f"orca_plan: {exc}")

    if args.write:
        for path in write_plan(plan, args.write):
            print(path)
    elif args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(f"#{plan['issue']} {plan['title']}")
        print(f"path: {plan['path_id']} · risk: {plan['risk']} · tasks: {len(plan['tasks'])}")
        for task in plan["tasks"]:
            print(f"  - {task['id']} → {task['role']} (deps: {', '.join(task['deps']) or '-'})")
            for line in task["spec"].splitlines():
                print(f"      {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
