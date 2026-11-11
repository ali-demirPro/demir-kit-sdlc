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

from kitlib import comments as kitcomments
from kitlib import config as kitconfig
from kitlib import gh as kitgh
from kitlib import root as kitroot
from kitlib import yamlish

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import epic_worktree  # noqa: E402
import usage  # noqa: E402


def run(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        args, cwd=str(cwd) if cwd else None, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise SystemExit(f"closure: {' '.join(args[:2])} failed — {result.stderr.strip()}")
    return result.stdout


def gh(args: list[str]) -> str:
    """Run ``gh``; a failure keeps the closure prefix and exits."""
    try:
        return kitgh.capture(args)
    except kitgh.GhError as exc:
        raise SystemExit(
            f"closure: {' '.join(args[:2])} failed — {exc.stderr}"
        ) from exc


def repo_name() -> str:
    project = kitroot.project_root(ROOT)
    ecosystem = kitconfig.read_yaml(project / "ecosystem.yaml")
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        raise SystemExit("closure: ecosystem.yaml tracker.repo yok")
    return repo


def issue_payload(repo: str, number: int) -> dict:
    return json.loads(gh(kitgh.api_args(f"repos/{repo}/issues/{number}")))


def epic_children(payload: dict) -> list[int]:
    data = yamlish.parse_block(payload.get("body") or "", "demir-kit-epic")
    children = data.get("children") if isinstance(data, dict) else []
    return [int(item) for item in children or [] if isinstance(item, int)]


def leaf_seal(payload: dict) -> dict:
    return yamlish.parse_block(payload.get("body") or "", "demir-kit")


def label_events(repo: str, issue: int) -> list[dict]:
    return kitgh.timeline(repo, issue, request=run)


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def issue_comments(repo: str, issue: int) -> list[dict]:
    return kitgh.issue_comments(repo, issue, request=run)


def deferred_detail(repo: str, issue: int) -> str:
    reason = "deferred label"
    link = ""
    for comment in issue_comments(repo, issue):
        body = comment.get("body") or ""
        if "run transition:" not in body or "to: deferred" not in body:
            continue
        match = re.search(r"^reason:\s*(.+)$", body, re.M)
        if match:
            reason = match.group(1).strip()
        match = re.search(r"^link:\s*(.+)$", body, re.M)
        if match:
            link = match.group(1).strip()
    if link and link != "-":
        reason = f"{reason} ({link})"
    return reason


def lead_time_hours(
    children: list[int], events: dict[int, list[dict]]
) -> float | None:
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
        return None
    return round((max(done) - min(approved)).total_seconds() / 3600, 1)


def cp_count(seals: dict[int, dict]) -> int:
    return sum(len(seal.get("checkpoints") or []) for seal in seals.values())


def state_roots() -> list[Path]:
    roots = [kitroot.project_root(ROOT)]
    main = kitroot.git_common_root()
    if main and main not in roots:
        roots.append(main)
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
    # Newest first keeps the previous "latest run wins" behaviour; the shape
    # itself is resolved by the one shared normaliser.
    ordered = sorted(
        (item for item in runs if isinstance(item, dict)),
        key=lambda item: str(item.get("created_at") or ""),
        reverse=True,
    )
    run = epic_worktree.normalize_run({"result": {"runs": ordered}}, f"epic #{epic}")
    return run.get("id") or None


def worker_totals(run_id: str | None) -> dict:
    if not run_id:
        return {"unavailable": True, "reason": "run yok"}
    data = usage.run_usage(run_id)
    totals = data.get("totals") or {}
    if not totals.get("worker_count"):
        return {"unavailable": True, "reason": "0 worker"}
    if not totals.get("measured"):
        return {"unavailable": True, "reason": "kısmi ölçüm"}
    partial_count = int(totals.get("unavailable") or 0)
    return {
        **totals,
        "unavailable": False,
        "unavailable_count": partial_count,
        "partial": partial_count > 0,
    }


def snapshot_for(issue: int) -> tuple[dict, Path] | None:
    for root in state_roots():
        path = root / ".orchestration" / f"usage-{issue}.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data, root
    return None


def coordinator_totals(children: list[int]) -> dict:
    found = [item for item in (snapshot_for(c) for c in children) if item]
    if not found:
        return {"unavailable": True}
    snapshot, root = min(
        found, key=lambda item: str(item[0].get("created_at") or "")
    )
    try:
        current = usage.current_session(root)
    except (SystemExit, ValueError, json.JSONDecodeError):
        return {"unavailable": True}
    if str(current.get("id")) != str(snapshot.get("session_id")):
        return {"unavailable": True, "reason": "session mismatch"}
    try:
        info = usage.api_session_info(str(current.get("id")))
        delta = usage.compute_delta(snapshot, info)
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
    lead = lead_time_hours(children, events)
    metrics = {
        "leaf_count": len(children),
        "cp_count": cp_count(seals),
        "gate_retries": gate_retries,
        "reconcile_issues": reconcile_issues,
        "human_interventions": human_interventions,
    }
    if lead is not None:
        metrics["lead_time_hours"] = lead
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
        if workers.get("partial"):
            metrics["worker_partial"] = True
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


def render_closure(
    epic: int,
    metrics: dict,
    status: str = "pass",
    deferred: list[dict] | None = None,
) -> str:
    payload = {
        "demir_kit_version": "2",
        "epic": epic,
        "status": status,
        "gaps": [],
        "unnecessary": [],
        "deferred": deferred or [],
        "metrics": metrics,
        "ready_for_human_qa": status == "pass",
    }
    return (
        "```yaml\ndemir-kit-closure\n"
        + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        + "```\n"
    )


def validate_block(body: str, leaf_count: int) -> list[str]:
    raw = yamlish.block_text(body, "demir-kit-closure")
    if raw is None:
        return ["closure bloğu üretilemedi"]
    try:
        record = yamlish.load_text(raw) or {}
    except yaml.YAMLError as exc:
        return [f"closure YAML geçersiz — {exc}"]
    import doctor

    schema = json.loads(
        (ROOT / "delivery" / "schemas" / "closure.schema.json").read_text(
            encoding="utf-8"
        )
    )
    errors = doctor.validate_schema(record, schema, "closure")
    metrics = record.get("metrics") or {}
    if metrics.get("leaf_count") != leaf_count:
        errors.append(
            f"closure leaf_count {metrics.get('leaf_count')} != {leaf_count}"
        )
    if record.get("status") == "pass" and record.get("ready_for_human_qa") is not True:
        errors.append("closure status pass ama ready_for_human_qa true değil")
    return errors


def post_comment(repo: str, issue: int, body: str) -> str | None:
    return kitcomments.post(repo, issue, body)


def delete_comment(repo: str, comment_id: str) -> bool:
    return kitcomments.delete(repo, comment_id)


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
    child_payloads = {child: issue_payload(repo, child) for child in children}
    seals = {child: leaf_seal(child_payloads[child]) for child in children}
    labels = {
        child: {item.get("name") for item in child_payloads[child].get("labels") or []}
        for child in children
    }
    deferred = {child for child in children if "deferred" in labels[child]}
    missing = [
        child for child in children
        if child not in deferred and not seals[child].get("checkpoints")
    ]
    if missing:
        raise SystemExit(f"closure: seal/checkpoint yok — {missing}")
    not_done = [
        child for child in children
        if not (labels[child] & {"leaf-done", "deferred"})
    ]
    if not_done:
        raise SystemExit(f"closure: leaf-done/deferred olmayan child — {not_done}")
    events = {child: label_events(repo, child) for child in children}
    workers = worker_totals(run_id_for(args.issue))
    if workers.get("unavailable"):
        print(
            f"closure: worker metrikleri yok ({workers.get('reason', 'ölçüm yok')}); "
            "worker alanları yazılmadı",
            file=sys.stderr,
        )
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
    if "lead_time_hours" not in metrics:
        raise SystemExit("closure: lead time hesaplanamadı (etiket olayları eksik)")
    deferred_items = [
        {"issue": child, "reason": deferred_detail(repo, child)}
        for child in children
        if "deferred" in labels[child]
    ]
    body = render_closure(args.issue, metrics, deferred=deferred_items)
    errors = validate_block(body, len(children))
    if errors:
        for error in errors:
            print(f"closure: {error}", file=sys.stderr)
        return 1

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
