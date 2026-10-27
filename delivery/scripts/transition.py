#!/usr/bin/env python3
"""Single writer for demir-kit state transitions (T1-T9)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import approvals

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent

TARGETS = {
    "scope-confirmed",
    "agent-approved",
    "executing",
    "blocked",
    "deferred",
    "leaf-done",
    "epic-reconcile",
    "epic-done",
}

ADD = {
    "scope-confirmed": ["scope-confirmed"],
    "agent-approved": ["agent-approved"],
    "executing": ["executing"],
    "blocked": ["blocked"],
    "deferred": ["deferred"],
    "leaf-done": ["leaf-done"],
    "epic-reconcile": ["epic-reconcile"],
    "epic-done": ["epic-done"],
}

REMOVE = {
    "scope-confirmed": ["intake"],
    "agent-approved": ["intake"],
    "executing": ["blocked"],
    "blocked": [],
    "deferred": ["executing"],
    "leaf-done": ["executing", "human-qa"],
    "epic-reconcile": ["epic-done"],
    "epic-done": ["epic-reconcile", "human-qa"],
}


def gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"transition: gh failed — {result.stderr.strip()}")
    return result.stdout


def fetch_issue(number: int) -> dict:
    raw = gh(
        [
            "issue",
            "view",
            str(number),
            "--json",
            "number,title,state,body,labels,comments,url",
        ]
    )
    data = json.loads(raw)
    if not isinstance(data, dict):
        sys.exit(f"transition: issue #{number} okunamadı")
    return data


def labels_of(issue: dict) -> set[str]:
    return {item.get("name") for item in issue.get("labels") or []}


def is_epic(issue: dict) -> bool:
    return bool(re.search(r"```yaml\s+demir-kit-epic\s*\n", issue.get("body") or ""))


def parse_seal(body: str) -> dict:
    match = re.search(r"```yaml\s+demir-kit\s*\n(.*?)```", body, re.S)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def epic_children(issue: dict) -> list[int]:
    match = re.search(r"```yaml\s+demir-kit-epic\s*\n(.*?)```", issue.get("body") or "", re.S)
    if not match:
        return []
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return []
    children = data.get("children") if isinstance(data, dict) else []
    return [int(item) for item in children or [] if isinstance(item, int)]


def closure_record(issue: dict) -> dict | None:
    text = "\n".join(
        [issue.get("body") or ""]
        + [item.get("body") or "" for item in issue.get("comments") or []]
    )
    blocks = re.findall(r"```yaml\s+demir-kit-closure\s*\n(.*?)```", text, re.S)
    if not blocks:
        return None
    try:
        data = yaml.safe_load(blocks[-1]) or {}
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def current_state(issue: dict, epic: bool) -> str:
    labels = labels_of(issue)
    if epic:
        for name, state in (
            ("epic-done", "epic-done"),
            ("epic-reconcile", "epic-reconcile"),
            ("scope-confirmed", "scope-confirmed"),
        ):
            if name in labels:
                return state
        return "intake"
    for name, state in (
        ("leaf-done", "leaf-done"),
        ("deferred", "deferred"),
        ("blocked", "blocked"),
        ("executing", "executing"),
        ("agent-approved", "agent-approved"),
        ("scope-confirmed", "scope-confirmed"),
    ):
        if name in labels:
            return state
    return "intake"


def doctor_ok(number: int, target: str, removes: list[str]) -> tuple[bool, str]:
    project = Path.cwd().resolve()
    command = [
        sys.executable,
        str(SCRIPTS / "doctor.py"),
        "--issue",
        str(number),
        "--assume-label",
        target,
    ]
    if project != ROOT.resolve() and (project / "kit.config.yaml").is_file():
        command += ["--product", "--root", str(project)]
    for label in removes:
        command += ["--drop-label", label]
    result = subprocess.run(command, cwd=project, capture_output=True, text=True)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def validate(issue: dict, target: str, args) -> tuple[bool, str]:
    epic = is_epic(issue)
    state = current_state(issue, epic)
    if target == "scope-confirmed":
        if not epic:
            return False, "scope-confirmed yalnız epic için"
        if state != "intake":
            return False, f"scope-confirmed geçişi intake'ten olmalı (şu an {state})"
    elif target == "agent-approved":
        if epic:
            return False, "agent-approved yalnız leaf için"
        if state not in {"intake", "scope-confirmed"}:
            return False, f"agent-approved geçişi intake/scope-confirmed'tan olmalı (şu an {state})"
        seal = parse_seal(issue.get("body") or "")
        if not seal:
            return False, "leaf seal (`demir-kit` bloğu) yok"
        parent = seal.get("epic")
        if parent:
            try:
                parent_issue = fetch_issue(int(parent))
            except (SystemExit, ValueError):
                return False, f"parent epic #{parent} okunamadı"
            if "scope-confirmed" not in labels_of(parent_issue):
                return False, f"parent epic #{parent} scope-confirmed değil"
    elif target == "executing":
        if epic:
            return False, "executing yalnız leaf için"
        if state not in {"agent-approved", "blocked"}:
            return False, f"executing geçişi agent-approved/blocked'dan olmalı (şu an {state})"
    elif target == "blocked":
        if epic:
            return False, "blocked yalnız leaf için"
        if state != "executing":
            return False, f"blocked geçişi executing'ten olmalı (şu an {state})"
        if not (args.reason or "").strip():
            return False, "blocked için --reason gerekli"
    elif target == "deferred":
        if state not in {"agent-approved", "executing"}:
            return False, f"deferred geçişi agent-approved/executing'ten olmalı (şu an {state})"
        if not (args.reason or args.issue_link):
            return False, "deferred için --reason veya --issue-link gerekli"
    elif target == "leaf-done":
        if epic:
            return False, "leaf-done yalnız leaf için"
        if state != "executing":
            return False, f"leaf-done geçişi executing'ten olmalı (şu an {state})"
    elif target == "epic-reconcile":
        if not epic:
            return False, "epic-reconcile yalnız epic için"
        closure = closure_record(issue)
        if not closure:
            return False, "epic-reconcile için closure bloğu yok"
        if closure.get("status") == "pass" and not closure.get("gaps"):
            return False, "epic-reconcile için closure fail veya gap gerekli"
    elif target == "epic-done":
        if not epic:
            return False, "epic-done yalnız epic için"
        closure = closure_record(issue)
        if not closure:
            return False, "epic-done için closure bloğu yok"
        if closure.get("status") != "pass":
            return False, "epic-done için closure status pass değil"
        if closure.get("ready_for_human_qa") is not True:
            return False, "epic-done için ready_for_human_qa true değil"
        children = epic_children(issue)
        metrics = closure.get("metrics") or {}
        if metrics.get("leaf_count") != len(children):
            return False, (
                "closure metrics.leaf_count child sayısıyla eşleşmiyor "
                f"({metrics.get('leaf_count')} != {len(children)})"
            )
        for child in children:
            try:
                child_issue = fetch_issue(child)
            except (SystemExit, ValueError):
                return False, f"child #{child} okunamadı"
            labels = labels_of(child_issue)
            if not labels & {"leaf-done", "deferred"}:
                return False, f"child #{child} leaf-done/deferred değil"
        acceptance = approvals.human_acceptance(
            issue.get("comments") or [], issue.get("number") or 0
        )
        if not acceptance:
            return False, (
                "epic-done için insan authored demir-kit-accept comment'i gerekli"
            )
        if args.accept and str(args.accept) != acceptance["by"]:
            return False, f"--accept '{args.accept}' insan onayıyla eşleşmiyor"
    return True, ""


def claim_issue(number: int) -> int:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "next-leaf.py"),
            "--claim",
            "--issue",
            str(number),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode
    return 0


def apply_delta(number: int, current: set[str], target: str) -> tuple[list[str], list[str]]:
    added = [label for label in ADD[target] if label not in current]
    removed = [label for label in REMOVE[target] if label in current]
    if added:
        gh(["issue", "edit", str(number), "--add-label", ",".join(added)])
    if removed:
        gh(["issue", "edit", str(number), "--remove-label", ",".join(removed)])
    return added, removed


def post_comment(number: int, body: str) -> None:
    gh(["issue", "comment", str(number), "--body", body])


def main() -> int:
    parser = argparse.ArgumentParser(description="demir-kit state transition")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--to", required=True, choices=sorted(TARGETS))
    parser.add_argument("--by", default="coordinator")
    parser.add_argument("--reason", default="")
    parser.add_argument("--issue-link", default="")
    parser.add_argument(
        "--accept", default="", help="epic-done insan login doğrulaması (opsiyonel)"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    issue = fetch_issue(args.issue)
    epic = is_epic(issue)
    state = current_state(issue, epic)
    if args.to in labels_of(issue) and not (
        args.to == "executing" and "blocked" in labels_of(issue)
    ):
        result = {
            "issue": args.issue,
            "from": state,
            "to": args.to,
            "applied": False,
            "reason": "already in target state",
        }
        print(json.dumps(result, ensure_ascii=False) if args.json else f"#{args.issue}: no-op ({args.to})")
        return 0

    ok, message = validate(issue, args.to, args)
    if not ok:
        sys.exit(f"transition: {message}")

    removes = [label for label in REMOVE[args.to] if label in labels_of(issue)]
    doctor, output = doctor_ok(args.issue, args.to, removes)
    if not doctor:
        sys.exit(f"transition: doctor preflight failed\n{output}")

    plan = {
        "issue": args.issue,
        "from": state,
        "to": args.to,
        "add": [label for label in ADD[args.to] if label not in labels_of(issue)],
        "remove": removes,
        "by": args.by,
        "dry_run": args.dry_run,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False) if args.json else f"#{args.issue}: {state} -> {args.to} (dry-run)")
        return 0

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    transition_comment = (
        f"run transition: `{run_id}`\n"
        f"from: {state}\n"
        f"to: {args.to}\n"
        f"by: {args.by}\n"
        f"reason: {args.reason or '-'}\n"
        f"link: {args.issue_link or '-'}"
    )

    if args.to == "executing" and state == "agent-approved":
        # Claim writes its own durable `run claim` record; the transition audit
        # follows it so a comment failure cannot orphan a label.
        if claim_issue(args.issue) != 0:
            return 1
        post_comment(args.issue, transition_comment)
        applied = {"add": ["executing"], "remove": []}
    else:
        # Audit trail before labels: a failed comment must not leave a silent
        # state change that a re-run would treat as a no-op.
        post_comment(args.issue, transition_comment)
        added, removed = apply_delta(args.issue, labels_of(issue), args.to)
        applied = {"add": added, "remove": removed}

    result = {
        "issue": args.issue,
        "from": state,
        "to": args.to,
        "applied": True,
        "add": applied["add"],
        "remove": applied["remove"],
        "run_id": run_id,
    }
    print(json.dumps(result, ensure_ascii=False) if args.json else f"#{args.issue}: {state} -> {args.to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
