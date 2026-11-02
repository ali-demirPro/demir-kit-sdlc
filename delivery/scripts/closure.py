#!/usr/bin/env python3
"""Build (and optionally post) an epic closure block from real data.

Usage:
  python3 delivery/scripts/closure.py --issue 154
  python3 delivery/scripts/closure.py --issue 154 --post
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import routing  # noqa: E402
import usage  # noqa: E402


def run(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        args, cwd=str(cwd) if cwd else None, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise SystemExit(f"closure: {' '.join(args[:2])} failed — {result.stderr.strip()}")
    return result.stdout


def repo_name() -> str:
    project = routing.project_root(ROOT)
    ecosystem = yaml.safe_load((project / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        raise SystemExit("closure: ecosystem.yaml tracker.repo yok")
    return repo


def issue_payload(repo: str, number: int) -> dict:
    return json.loads(run(["gh", "api", f"repos/{repo}/issues/{number}"]))


def epic_children(payload: dict) -> list[int]:
    match = re.search(r"```yaml\s+demir-kit-epic\s*\n(.*?)```", payload.get("body") or "", re.S)
    if not match:
        return []
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return []
    children = data.get("children") if isinstance(data, dict) else []
    return [int(item) for item in children or [] if isinstance(item, int)]


def leaf_seal(payload: dict) -> dict:
    match = re.search(r"```yaml\s+demir-kit\s*\n(.*?)```", payload.get("body") or "", re.S)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def label_events(repo: str, issue: int) -> list[dict]:
    raw = run(
        [
            "gh",
            "api",
            f"repos/{repo}/issues/{issue}/timeline?per_page=100",
        ]
    )
    try:
        events = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return events if isinstance(events, list) else []


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def lead_time_hours(children: list[int], events: dict[int, list[dict]]) -> float:
    approved = []
    done = []
    for child in children:
        for event in events.get(child, []):
            if event.get("event") != "labeled":
                continue
            label = (event.get("label") or {}).get("name")
            moment = parse_time(event.get("created_at"))
            if not moment:
                continue
            if label == "agent-approved":
                approved.append(moment)
            elif label == "leaf-done":
                done.append(moment)
    if not approved or not done:
        return 0.0
    return round((max(done) - min(approved)).total_seconds() / 3600, 1)


def cp_count(seals: dict[int, dict]) -> int:
    return sum(len(seal.get("checkpoints") or []) for seal in seals.values())


def state_roots() -> list[Path]:
    roots = [routing.project_root(ROOT)]
    try:
        common = run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"])
        main = Path(common.strip()).parent
        if main not in roots:
            roots.append(main)
    except SystemExit:
        pass
    return roots


def run_id_for(epic: int) -> str | None:
    for root in state_roots():
        path = root / ".orchestration" / f"epic-{epic}.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        run_id = str(data.get("run_id") or "")
        if run_id:
            return run_id
    runs = usage.orca_result(["orchestration", "run-list", "--json"]).get("runs") or []
    for item in runs:
        if str(item.get("objective")) == f"epic #{epic}":
            return str(item.get("id") or "") or None
    return None


def worker_totals(run_id: str | None) -> dict:
    if not run_id:
        return {"unavailable": True}
    data = usage.run_usage(run_id)
    return {"unavailable": False, **data["totals"]}


def snapshot_for(issue: int) -> dict | None:
    for root in state_roots():
        path = root / ".orchestration" / f"usage-{issue}.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def coordinator_totals(children: list[int]) -> dict:
    snapshots = [snap for snap in (snapshot_for(c) for c in children) if snap]
    if not snapshots:
        return {"unavailable": True}
    snapshot = min(snapshots, key=lambda item: str(item.get("created_at") or ""))
    try:
        current = usage.api_session_info(str(snapshot.get("session_id")))
        delta = usage.compute_delta(snapshot, current)
    except (SystemExit, ValueError, json.JSONDecodeError):
        return {"unavailable": True}
    tokens = delta.get("tokens") or {}
    return {
        "unavailable": False,
        "session_id": delta.get("session_id"),
        "tokens_in": tokens.get("input", 0),
        "tokens_out": tokens.get("output", 0),
        "cache_read": tokens.get("cache_read", 0),
        "cost_usd": delta.get("cost", 0),
    }


def build_metrics(
    children: list[int],
    seals: dict[int, dict],
    events: dict[int, list[dict]],
    workers: dict,
    coordinator: dict,
    gate_retries: int,
    reconcile_issues: int,
    human_interventions: int,
) -> dict:
    metrics = {
        "leaf_count": len(children),
        "cp_count": cp_count(seals),
        "gate_retries": gate_retries,
        "reconcile_issues": reconcile_issues,
        "human_interventions": human_interventions,
        "lead_time_hours": lead_time_hours(children, events),
    }
    if not workers.get("unavailable"):
        metrics.update(
            {
                "worker_count": workers.get("worker_count", 0),
                "tokens_in": workers.get("tokens_in", 0),
                "tokens_out": workers.get("tokens_out", 0),
                "cache_read": workers.get("cache_read", 0),
                "context_peak": workers.get("context_peak", 0),
                "cost_usd": workers.get("cost_usd") or 0,
            }
        )
    if not coordinator.get("unavailable"):
        metrics.update(
            {
                "coordinator_tokens_in": coordinator.get("tokens_in", 0),
                "coordinator_tokens_out": coordinator.get("tokens_out", 0),
                "coordinator_cache_read": coordinator.get("cache_read", 0),
                "coordinator_cost_usd": coordinator.get("cost_usd", 0),
            }
        )
    return metrics


def render_closure(epic: int, metrics: dict, status: str = "pass") -> str:
    payload = {
        "demir_kit_version": "2",
        "epic": epic,
        "status": status,
        "gaps": [],
        "unnecessary": [],
        "deferred": [],
        "metrics": metrics,
        "ready_for_human_qa": status == "pass",
    }
    return (
        "```yaml\ndemir-kit-closure\n"
        + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        + "```\n"
    )


def post_comment(repo: str, issue: int, body: str) -> str | None:
    result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{repo}/issues/{issue}/comments",
            "--input",
            "-",
        ],
        capture_output=True,
        text=True,
        input=json.dumps({"body": body}),
    )
    if result.returncode != 0:
        return None
    try:
        return str(json.loads(result.stdout).get("id") or "")
    except json.JSONDecodeError:
        return None


def delete_comment(repo: str, comment_id: str) -> bool:
    result = subprocess.run(
        ["gh", "api", "-X", "DELETE", f"repos/{repo}/issues/comments/{comment_id}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def verify_close(issue: int) -> tuple[int, str]:
    script = ROOT / "delivery" / "scripts" / "doctor.sh"
    result = subprocess.run(
        [str(script), "--issue", str(issue)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, "\n".join(output.splitlines()[-20:])


def main() -> int:
    parser = argparse.ArgumentParser(description="epic closure from real data")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--gate-retries", type=int, default=0)
    parser.add_argument("--reconcile-issues", type=int, default=0)
    parser.add_argument("--human-interventions", type=int, default=0)
    parser.add_argument("--post", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo = repo_name()
    payload = issue_payload(repo, args.issue)
    children = epic_children(payload)
    if not children:
        raise SystemExit("closure: epic children yok")
    seals = {child: leaf_seal(issue_payload(repo, child)) for child in children}
    events = {child: label_events(repo, child) for child in children}
    workers = worker_totals(run_id_for(args.issue))
    coordinator = coordinator_totals(children)
    metrics = build_metrics(
        children,
        seals,
        events,
        workers,
        coordinator,
        args.gate_retries,
        args.reconcile_issues,
        args.human_interventions,
    )
    body = render_closure(args.issue, metrics)

    if not args.post:
        if args.json:
            print(json.dumps({"issue": args.issue, "metrics": metrics, "body": body},
                             ensure_ascii=False, indent=2))
        else:
            print(body)
        return 0

    comment_id = post_comment(repo, args.issue, body)
    if not comment_id:
        print("closure: yorum yazılamadı", file=sys.stderr)
        return 1
    code, output = verify_close(args.issue)
    if code != 0:
        if delete_comment(repo, comment_id):
            print(f"closure: doctor düştü, yorum geri alındı\n{output}", file=sys.stderr)
        else:
            print(
                f"closure: doctor düştü; yorum SİLİNEMEDİ (comment {comment_id})"
                f"\n{output}",
                file=sys.stderr,
            )
        return 1
    print(f"Closure yazıldı — #{args.issue} · leaf {metrics['leaf_count']} · "
          f"worker {metrics.get('worker_count', '?')} · maliyet "
          f"${metrics.get('cost_usd', 0):.4f} + koordinatör "
          f"${metrics.get('coordinator_cost_usd', 0):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
