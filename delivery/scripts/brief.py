#!/usr/bin/env python3
"""Show how a leaf maps to delivery agents.

Usage:
  python3 delivery/scripts/brief.py 13
  python3 delivery/scripts/brief.py 13 --json
  python3 delivery/scripts/brief.py 13 --post
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
        sys.exit(f"brief: gh failed — {result.stderr.strip()}")
    return result.stdout


def repo_name() -> str:
    project = routing.project_root(ROOT)
    ecosystem = yaml.safe_load((project / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        sys.exit("brief: ecosystem.yaml tracker.repo yok")
    return repo


def build_brief(registry: dict, number: int, title: str, body: str, labels: set[str]) -> dict:
    seal = routing.seal_body(body)
    epic = routing.is_epic(body) or ("scope-confirmed" in labels and not seal)
    path_id, signal = routing.detect_path(registry, title, body, seal)
    agents = routing.resolve_agents(registry, path_id, signal)
    risk = (seal.get("risk") or {}).get("level", "n/a")
    docs_roles = agents["active"] + agents["on_demand"]
    docs: list[str] = []
    for role in docs_roles:
        docs.extend(routing.role_docs(role))

    return {
        "issue": number,
        "title": title,
        "state": "epic" if epic else "leaf",
        "path_id": path_id,
        "signal": signal.get("id") if signal else None,
        "agents": agents,
        "inactive": routing.inactive_agents(registry, agents),
        "risk": risk,
        "next_action": routing.next_action(labels, epic),
        "human_gates": routing.human_gates(risk, epic),
        "docs": docs,
    }


def render(data: dict) -> str:
    lines = [
        f"#{data['issue']} {data['title']}",
        f"state: {data['state']}",
        f"path: {data['path_id']}"
        + (f" (signal: {data['signal']})" if data["signal"] else ""),
        "active: " + ", ".join(data["agents"]["active"]),
        "on_demand: " + (", ".join(data["agents"]["on_demand"]) or "-"),
        "optional: " + (", ".join(data["agents"]["optional"]) or "-"),
        "inactive:",
    ]
    for item in data["inactive"]:
        lines.append(f"  - {item['id']}: {item['reason']}")
    lines += [
        f"next: {data['next_action']}",
        "human gates:",
    ]
    lines += [f"  - {gate}" for gate in data["human_gates"]]
    lines.append("docs:")
    lines += [f"  - {doc}" for doc in data["docs"]]
    return "\n".join(lines)


def comment_body(data: dict) -> str:
    payload = {
        "delivery_path": {
            "path_id": data["path_id"],
            "signal": data["signal"],
            "active_agents": data["agents"]["active"],
            "optional_agents": data["agents"]["optional"],
            "on_demand": data["agents"]["on_demand"],
            "inactive": data["inactive"],
            "next_action": data["next_action"],
            "human_gates": data["human_gates"],
        }
    }
    return (
        "## delivery_path\n\n"
        f"```yaml\n{yaml.safe_dump(payload, sort_keys=False)}```\n"
    )


def has_delivery_path(comments: list[dict]) -> bool:
    return any("## delivery_path" in (item.get("body") or "") for item in comments)


def existing_delivery_path(repo: str, issue: int, fetch=None) -> bool:
    fetch = fetch or gh
    page = 1
    while True:
        data = json.loads(
            fetch(
                [
                    "api",
                    f"repos/{repo}/issues/{issue}/comments?per_page=100&page={page}",
                ]
            )
        )
        if has_delivery_path(data):
            return True
        if len(data) < 100:
            return False
        page += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="delivery agent brief")
    parser.add_argument("issue", type=int)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--post", action="store_true")
    args = parser.parse_args()

    repo = repo_name()
    issue = json.loads(gh(["api", f"repos/{repo}/issues/{args.issue}"]))
    labels = {item.get("name") for item in issue.get("labels", [])}
    data = build_brief(
        routing.load_registry(ROOT),
        args.issue,
        issue.get("title", ""),
        issue.get("body", "") or "",
        labels,
    )

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render(data))

    if args.post:
        if existing_delivery_path(repo, args.issue):
            print("brief: delivery_path comment already exists", file=sys.stderr)
        else:
            body = comment_body(data)
            subprocess.run(
                [
                    "gh",
                    "api",
                    "-X",
                    "POST",
                    f"repos/{repo}/issues/{args.issue}/comments",
                    "--input",
                    "-",
                ],
                input=json.dumps({"body": body}),
                text=True,
                check=True,
                capture_output=True,
            )
            print("brief: delivery_path comment posted", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
