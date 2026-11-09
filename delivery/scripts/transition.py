#!/usr/bin/env python3
"""Single writer for demir-kit state transitions (T1-T9)."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

import approvals
import cycle
import epic_worktree
import routing

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
GATE_TIMEOUT_MS = 900_000

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


def orca_run(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["orca", *args], capture_output=True, text=True
        )
    except FileNotFoundError:
        return False, "orca CLI yok"
    return result.returncode == 0, (result.stderr.strip() or result.stdout.strip())


def orca_status_for(target: str) -> str:
    return {
        "scope-confirmed": "todo",
        "agent-approved": "todo",
        "executing": "in-progress",
        "blocked": "in-progress",
        "deferred": "todo",
        "leaf-done": "in-review",
        "epic-reconcile": "in-review",
        "epic-done": "completed",
    }.get(target, "in-progress")


def sync_orca(number: int, target: str, epic: int | None) -> None:
    """Mirror a state transition into the epic worktree metadata."""
    epic_number = epic or number
    state = epic_worktree.load_state(Path.cwd(), epic_number)
    if not state or state.get("mode") == "degrade":
        return
    name = f"epic-{epic_number}"
    args = [
        "worktree",
        "set",
        "--worktree",
        f"name:{name}",
        "--comment",
        f"#{number} → {target}",
        "--workspace-status",
        orca_status_for(target),
        "--json",
    ]
    if target == "agent-approved":
        args.insert(-1, "--unread")
    elif target == "leaf-done":
        args.insert(-1, "--read")
    ok, message = orca_run(args)
    if not ok:
        print(f"transition: Orca durumu yazılamadı — {message}", file=sys.stderr)


def epic_pr_merged(epic: int) -> tuple[bool, str]:
    """A merged epic PR is the only path into main."""
    state = epic_worktree.load_state(Path.cwd(), epic)
    if not state:
        return True, ""
    branch = str(state.get("branch") or "")
    if branch.startswith("refs/heads/"):
        branch = branch[11:]
    if not branch:
        return True, ""
    try:
        raw = gh(
            [
                "pr",
                "list",
                "--head",
                branch,
                "--state",
                "merged",
                "--json",
                "number,url",
            ]
        )
    except SystemExit:
        return False, f"epic PR durumu okunamadı ({branch})"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False, f"epic PR durumu okunamadı ({branch})"
    if not data:
        return False, (
            f"epic branch '{branch}' için merge edilmiş PR yok; "
            "önce tek epic PR'ını aç ve merge et"
        )
    return True, ""


def cycle_row(
    issue: int,
    stage: str,
    actor: str,
    reason: str = "",
    epic: int | None = None,
) -> dict:
    """One cycle-log row for a state transition."""
    return cycle.make_row(issue, stage, actor=actor, reason=reason, epic=epic)


def last_checkpoint(issue: dict) -> str | None:
    seal = parse_seal(issue.get("body") or "")
    checkpoints = seal.get("checkpoints") or []
    if not checkpoints:
        return None
    last = checkpoints[-1]
    return str((last or {}).get("id") or "") or None


CHECKPOINT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def leaf_gate_command(project: Path, issue: int, checkpoint: str) -> list[str]:
    """Full gate as an argv list; the checkpoint id never reaches a shell."""
    if not CHECKPOINT_RE.fullmatch(str(checkpoint or "")):
        raise ValueError(f"geçersiz checkpoint kimliği: {checkpoint!r}")
    prefix = routing.kit_prefix(ROOT, project)
    return [
        f"./{prefix}delivery/scripts/gate.sh",
        "--issue",
        str(issue),
        "--checkpoint",
        str(checkpoint),
    ]


def leaf_gate_degrade_note(issue: int) -> str:
    return (
        f"run degrade: issue #{issue}\n"
        "reason: DEMIR_KIT_LEAF_GATE=off — leaf kapısı koşulmadı"
    )


def leaf_gate_enabled() -> bool:
    return os.environ.get("DEMIR_KIT_LEAF_GATE", "on") != "off"


def branch_name(project: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(project),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def push_needed(branch: str) -> bool:
    return bool(branch) and branch not in {"HEAD", "main", "master"}


def push_branch(project: Path) -> tuple[str, str]:
    """Push the epic branch so evidence commits exist on origin.

    Returns ``pushed``, ``skipped`` (main/detached: caller must record a reason)
    or ``failed``. A dirty tree never pushes: the evidence commit would not
    describe what was tested.
    """
    branch = branch_name(project)
    if not push_needed(branch):
        return "skipped", f"dal {branch or 'ayrık HEAD'} push edilmez"
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project),
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return "failed", str(exc)
    if status.returncode != 0:
        return "failed", "çalışma ağacı durumu okunamadı"
    if status.stdout.strip():
        return "failed", "çalışma ağacı kirli; commit veya stash et"
    try:
        result = subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "failed", str(exc)
    return (
        ("pushed" if result.returncode == 0 else "failed"),
        (result.stderr or result.stdout).strip(),
    )


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
        checkpoint = last_checkpoint(issue)
        if checkpoint and not CHECKPOINT_RE.fullmatch(checkpoint):
            return False, f"geçersiz checkpoint kimliği: {checkpoint!r}"
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
        state = epic_worktree.load_state(Path.cwd(), int(issue.get("number") or 0))
        if state.get("path") and Path(str(state["path"])).is_dir():
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(state["path"]),
                capture_output=True,
                text=True,
            )
            if status.returncode != 0:
                return False, "epic worktree durumu okunamadı"
            if status.stdout.strip():
                return False, "epic worktree temiz değil; commit veya stash et"
        merged, message = epic_pr_merged(int(issue.get("number") or 0))
        if not merged:
            return False, message
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


def terminal_handle(payload: object) -> str:
    """Extract the runtime-issued terminal handle from an Orca envelope."""
    if not isinstance(payload, dict):
        return ""
    result = payload.get("result")
    result = result if isinstance(result, dict) else {}
    terminal = result.get("terminal")
    terminal = terminal if isinstance(terminal, dict) else {}
    for value in (
        terminal.get("handle"),
        result.get("handle"),
        result.get("terminalId"),
    ):
        if value:
            return str(value)
    return ""


def run_gate_in_orca(
    project: Path,
    command: list[str],
    timeout_ms: int = GATE_TIMEOUT_MS,
    root: Path | None = None,
) -> tuple[int | None, str]:
    """Run the gate in an Orca terminal and read the exit code from a file.

    Returns ``(None, "")`` only when Orca cannot create the terminal, so the
    caller may fall back to a direct run. A created terminal that never writes
    its result file is a gate failure, not a fallback.
    """
    if not shutil.which("orca"):
        return None, ""
    directory = Path(root) if root else Path(
        tempfile.mkdtemp(prefix="demir-kit-gate-")
    )
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / "gate.log"
    code_file = directory / "gate.exit"
    for path in (log, code_file):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    shell = (
        f"{shlex.join(command)} > {shlex.quote(str(log))} 2>&1; "
        f"printf '%s' $? > {shlex.quote(str(code_file))}"
    )
    try:
        created = subprocess.run(
            [
                "orca",
                "terminal",
                "create",
                "--worktree",
                f"path:{project}",
                "--title",
                "demir-kit gate",
                "--command",
                shell,
                "--json",
            ],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    if created.returncode != 0:
        return None, ""
    try:
        payload = json.loads(created.stdout)
    except json.JSONDecodeError:
        return None, ""
    handle = terminal_handle(payload)
    if not handle:
        return None, ""
    try:
        subprocess.run(
            [
                "orca",
                "terminal",
                "wait",
                "--terminal",
                handle,
                "--for",
                "exit",
                "--timeout-ms",
                str(timeout_ms),
                "--json",
            ],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000 + 60,
        )
    except subprocess.TimeoutExpired:
        return 124, "terminal wait timeout"
    except OSError as exc:
        return 127, str(exc)
    try:
        output = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        output = ""
    try:
        code = int(code_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 1, (output or "gate sonucu dosyadan okunamadı")[-4000:]
    return code, output[-4000:]


def close_leaf_gate(issue: dict, args) -> None:
    """Full leaf gate before leaf-done, or an explicit, recorded degrade."""
    if args.no_gate:
        if not (args.reason or "").strip():
            sys.exit("transition: --no-gate için --reason gerekli")
        post_comment(
            args.issue,
            f"run degrade: issue #{args.issue}\nreason: {args.reason}",
        )
        return
    if not leaf_gate_enabled():
        post_comment(args.issue, leaf_gate_degrade_note(args.issue))
        return
    checkpoint = last_checkpoint(issue)
    if not checkpoint:
        sys.exit("transition: leaf-done için checkpoint bulunamadı")
    try:
        command = leaf_gate_command(Path.cwd(), args.issue, checkpoint)
    except ValueError as exc:
        sys.exit(f"transition: {exc}")
    print(f"gate: {' '.join(command)}", flush=True)
    code, output = run_gate_in_orca(Path.cwd(), command)
    if code is None:
        try:
            result = subprocess.run(
                command, cwd=str(Path.cwd()), capture_output=True, text=True
            )
        except OSError as exc:
            sys.exit(f"transition: leaf kapısı koşulamadı — {exc}")
        code, output = result.returncode, result.stdout + result.stderr
    if code != 0:
        sys.exit(
            "transition: leaf tam kapısı düştü — " + (output or "").strip()[-400:]
        )
    print("gate: exit 0", flush=True)


def check_push(args) -> None:
    if args.no_push:
        if not (args.reason or "").strip():
            sys.exit("transition: --no-push için --reason gerekli")
        post_comment(
            args.issue,
            f"run degrade: issue #{args.issue}\nreason: {args.reason}",
        )
        return
    status, message = push_branch(Path.cwd())
    if status == "pushed":
        return
    if status == "skipped":
        if not (args.reason or "").strip():
            sys.exit(
                "transition: push atlandı — --no-push --reason gerekli "
                f"({message})"
            )
        post_comment(
            args.issue,
            f"run degrade: issue #{args.issue}\n"
            f"reason: push atlandı — {message}; {args.reason}",
        )
        return
    sys.exit(f"transition: epic dalı push edilemedi — {message}")


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
    parser.add_argument(
        "--keep-worktree",
        action="store_true",
        help="epic-done sonrası worktree'yi silme",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="geçiş sonrası report.py --post çalıştır",
    )
    parser.add_argument("--gate", help="onayla birlikte çözülecek Orca gate id")
    parser.add_argument("--resolution", default="approved", help="gate çözümü")
    parser.add_argument("--no-orca", action="store_true", help="Orca metadata yazma")
    parser.add_argument(
        "--write-cycle", action="store_true", help="dry-run olsa da cycle satırını yaz"
    )
    parser.add_argument("--no-cycle", action="store_true", help="cycle satırı yazma")
    parser.add_argument(
        "--no-gate",
        action="store_true",
        help="leaf-done'da tam kapıyı koşma (--reason ile degrade kaydı)",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="leaf-done'da dalı push etme (--reason ile degrade kaydı)",
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
    seal = parse_seal(issue.get("body") or "")
    row = cycle_row(
        args.issue,
        args.to,
        args.by,
        args.reason,
        None if epic else seal.get("epic"),
    )
    plan["cycle"] = row
    if args.dry_run:
        if args.write_cycle and not args.no_cycle:
            cycle.record(cycle.project_root(ROOT), row)
        print(json.dumps(plan, ensure_ascii=False) if args.json else f"#{args.issue}: {state} -> {args.to} (dry-run)")
        return 0

    if args.to == "leaf-done":
        close_leaf_gate(issue, args)
        check_push(args)

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

    if not args.no_cycle:
        cycle.close_wait(cycle.project_root(ROOT), args.issue, ts=row.get("ts"))
        cycle.record(cycle.project_root(ROOT), row)


    if not args.no_orca:
        seal = parse_seal(issue.get("body") or "")
        sync_orca(
            args.issue,
            args.to,
            None if epic else seal.get("epic"),
        )

    if args.gate:
        ok, message = orca_run(
            [
                "orchestration",
                "gate-resolve",
                "--id",
                str(args.gate),
                "--resolution",
                str(args.resolution),
                "--json",
            ]
        )
        if not ok:
            print(f"transition: gate çözülemedi — {message}", file=sys.stderr)

    if args.report:
        subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "report.py"),
                "--issue",
                str(args.issue),
                "--post",
            ],
            cwd=Path.cwd(),
            check=False,
        )

    if args.to == "epic-done" and not args.keep_worktree:
        state = epic_worktree.load_state(Path.cwd(), args.issue)
        if state:
            worktree_path = Path(str(state.get("path") or "")).resolve()
            if Path.cwd().resolve() == worktree_path:
                print(
                    "transition: worktree'yi silmek için ana checkout'tan çalıştır "
                    "veya --keep-worktree kullan",
                    file=sys.stderr,
                )
            else:
                try:
                    epic_worktree.remove(args.issue, Path.cwd())
                except epic_worktree.WorktreeError as exc:
                    print(f"transition: worktree silinemedi — {exc}", file=sys.stderr)

    result = {
        "issue": args.issue,
        "from": state,
        "to": args.to,
        "applied": True,
        "add": applied["add"],
        "remove": applied["remove"],
        "run_id": run_id,
        "cycle": row,
    }
    print(json.dumps(result, ensure_ascii=False) if args.json else f"#{args.issue}: {state} -> {args.to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
