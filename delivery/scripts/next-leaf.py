#!/usr/bin/env python3
"""Dependency-aware leaf queue with lease-based claiming."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kitlib import comments as kitcomments
from kitlib import gh as kitgh
from kitlib import yamlish

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))
import budget  # noqa: E402
import cycle  # noqa: E402
import epic_worktree  # noqa: E402
import process_gate  # noqa: E402
import routing  # noqa: E402
import usage  # noqa: E402

SKIP_LABELS = {"executing", "blocked", "deferred", "leaf-done", "epic-done"}
CLAIM_PREFIX = "run claim:"
RELEASE_PREFIX = "run release:"
EVIDENCE_TAG = "demir-kit-evidence"
LEASE_HOURS = 2


def gh(args: list[str]) -> str:
    try:
        return kitgh.capture(args)
    except kitgh.GhError as exc:
        sys.exit(f"next-leaf: gh failed — {exc.stderr}")


def gh_optional(args: list[str]) -> str:
    return kitgh.capture(args, optional=True)


def parse_seal(body: str) -> dict:
    return yamlish.parse_block(body, "demir-kit")


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def comment_id(comment: dict) -> int:
    """Accept REST comments (int id) and GraphQL/node payloads (URL suffix)."""
    try:
        return kitcomments.comment_id(comment)
    except ValueError as exc:
        sys.exit(f"next-leaf: {exc}")


def comment_body(comment: dict) -> str:
    return kitcomments.body(comment)


def run_id_from(comment: dict) -> str | None:
    match = re.search(r"run claim:\s*`?([^\s`]+)`?", comment_body(comment))
    return match.group(1) if match else None


def lease_until_from(comment: dict) -> datetime | None:
    match = re.search(r"lease_until:\s*`?([^\s`]+)`?", comment_body(comment))
    return parse_time(match.group(1)) if match else None


def fetch_comments(repo: str, number: int, page_size: int = 100) -> list[dict]:
    return kitgh.issue_comments(repo, number, page_size, request=gh)


def fetch_issue(number: int) -> dict:
    raw = gh(
        kitgh.issue_view_args(
            number, "number,title,state,body,labels,assignees,url"
        )
    )
    data = json.loads(raw)
    if not isinstance(data, dict):
        sys.exit(f"next-leaf: issue #{number} okunamadı")
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/\d+", data.get("url") or "")
    if not match:
        sys.exit(f"next-leaf: issue #{number} repo adresi okunamadı")
    data["comments"] = fetch_comments(
        f"{match.group(1)}/{match.group(2)}", number
    )
    return data


def lease_state(issue: dict, at: datetime | None = None) -> dict:
    """Return the active lease after the latest release, if any."""
    at = at or now()
    comments = sorted(issue.get("comments") or [], key=comment_id)
    releases = [item for item in comments if RELEASE_PREFIX in comment_body(item)]
    cutoff = max((comment_id(item) for item in releases), default=0)
    claims = [
        item
        for item in comments
        if CLAIM_PREFIX in comment_body(item) and comment_id(item) > cutoff
    ]
    if not claims:
        return {"active": None, "expired": False, "evidence_after": []}

    active = min(claims, key=comment_id)
    created = (
        parse_time(active.get("createdAt") or active.get("created_at")) or at
    )
    expires = lease_until_from(active) or created + timedelta(hours=LEASE_HOURS)
    evidence_after = [
        item
        for item in comments
        if comment_id(item) > comment_id(active) and EVIDENCE_TAG in comment_body(item)
    ]
    return {
        "active": active,
        "run_id": run_id_from(active),
        "expires_at": expires,
        "expired": at >= expires,
        "evidence_after": evidence_after,
    }


def claim_winner(issue: dict) -> int | None:
    """Concurrent claims are ordered by comment id; the lowest id wins."""
    comments = sorted(issue.get("comments") or [], key=comment_id)
    releases = [item for item in comments if RELEASE_PREFIX in comment_body(item)]
    cutoff = max((comment_id(item) for item in releases), default=0)
    claims = [
        item
        for item in comments
        if CLAIM_PREFIX in comment_body(item) and comment_id(item) > cutoff
    ]
    return min((comment_id(item) for item in claims), default=None)


def write_snapshot(number: int) -> None:
    snapshot = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "usage.py"),
            "--snapshot",
            "--issue",
            str(number),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )
    if snapshot.returncode != 0:
        print(
            f"next-leaf: usage snapshot skipped — {snapshot.stderr.strip()}",
            file=sys.stderr,
        )


def claim_context() -> tuple[int, str]:
    """Context check for the current session before a claim.

    Calls ``usage.py --check --context <token>``; an unmeasurable context is
    reported on stderr and never blocks the claim. A measured 300k+ exceed
    returns exit 1 with the hard-limit message.
    """
    try:
        tokens = usage.current_context_tokens()
    except Exception:
        tokens = None
    if tokens is None:
        print("next-leaf: bağlam ölçülemedi — kontrol atlandı", file=sys.stderr)
        return 0, ""
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "usage.py"),
            "--check",
            "--context",
            str(tokens),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, (result.stdout or "").strip()


def prepare_worktree(number: int, epic: int | None) -> int:
    """Ensure the epic worktree and print the exact next commands."""
    if not epic:
        return 0
    project = Path.cwd()
    if not epic_worktree.epic_worktree_enabled(project):
        return 0
    try:
        record = epic_worktree.ensure(int(epic), project)
    except epic_worktree.WorktreeError as exc:
        print(f"next-leaf: epic worktree hazır değil — {exc}", file=sys.stderr)
        return 1
    path = record.get("path") or ""
    print(
        f"[worktree] {record.get('name')}: {path} · branch {record.get('branch')}",
        file=sys.stderr,
    )
    if record.get("run_warning"):
        print(f"next-leaf: {record['run_warning']}", file=sys.stderr)
    if record.get("run_error"):
        print(f"next-leaf: {record['run_error']}", file=sys.stderr)
        return 1
    if record.get("mode") == "degrade":
        print(
            "[worktree] degrade: Orca yok. Guard öncesi "
            f"`guard.sh --issue {number} --degrade --reason \"...\"` ile kaydet.",
            file=sys.stderr,
        )
    limits = budget.load(epic_worktree.project_root())
    if any(limits.values()):
        print(
            f"[budget] ağır iş {limits['heavy_workers'] or 'sınırsız'} · "
            f"reviewer {limits['reviewers'] or 'sınırsız'}",
            file=sys.stderr,
        )
    try:
        here = Path.cwd().resolve()
        there = Path(path).resolve()
    except OSError:
        here = there = Path(".")
    if path and here != there:
        print(
            "[uyarı] ana dizindesin; kaynak değişikliği epic worktree'sinde yapılır",
            file=sys.stderr,
        )
    print(f"[next] cd {path}", file=sys.stderr)
    print(
        "[next] orca orchestration task-create --spec <CP spec> "
        f"--task-title <CP> --deps '[]' --json",
        file=sys.stderr,
    )
    print(
        "[next] orca orchestration worker-start --task <task_id> "
        f"--worktree {path} --agent opencode2 --json",
        file=sys.stderr,
    )
    print(
        f"[next] source edits only in {path}; guard.sh --issue {number}",
        file=sys.stderr,
    )
    return 0


def claim(number: int, epic: int | None, risk: str) -> int:
    issue = fetch_issue(number)
    if issue.get("state") != "OPEN":
        sys.exit(f"next-leaf: #{number} açık değil")

    lease = lease_state(issue)
    if lease.get("active"):
        if not lease["expired"]:
            sys.exit(f"next-leaf: #{number} zaten claim edilmiş (lease aktif)")
        sys.exit(
            f"next-leaf: #{number} lease'i bayat; "
            f"`next-leaf --release --issue {number}` çalıştır"
        )

    context_code, context_message = claim_context()
    if context_code != 0:
        body = (
            "run blocked: bağlam sınırı\n\n"
            f"{context_message}\n\n"
            "Claim yapılmadı; yeni oturum açıp tekrar deneyin."
        )
        gh(kitgh.issue_edit_args(number, "--add-label", "blocked"))
        gh(kitgh.issue_comment_args(number, body))
        print(
            f"next-leaf: #{number} bağlam sınırında — claim yapılmadı: "
            f"{context_message}",
            file=sys.stderr,
        )
        return 1
    if context_message:
        print(context_message, file=sys.stderr)

    run_id = now().strftime("run-%Y%m%dT%H%M%S%fZ")
    expires = now() + timedelta(hours=LEASE_HOURS)
    body = (
        f"run claim: `{run_id}`\n"
        f"lease_until: `{expires.isoformat()}`\n\n"
        f"Epic: #{epic} · risk: {risk}"
    )
    gh(kitgh.issue_comment_args(number, body))
    gh(kitgh.issue_edit_args(number, "--add-label", "executing"))
    gh_optional(kitgh.issue_edit_args(number, "--add-assignee", "@me"))

    refreshed = fetch_issue(number)
    winner = claim_winner(refreshed)
    ours = next(
        (
            comment_id(item)
            for item in refreshed.get("comments") or []
            if run_id in comment_body(item)
        ),
        None,
    )
    if ours is None or winner != ours:
        gh_optional(kitgh.issue_edit_args(number, "--remove-assignee", "@me"))
        print(f"claim lost: #{number} ({run_id})", file=sys.stderr)
        return 1

    write_snapshot(number)
    try:
        cycle.record(
            cycle.project_root(ROOT),
            cycle.make_row(number, "executing", actor="claim", reason=run_id,
                           epic=epic),
        )
    except Exception:
        pass
    print(f"claimed #{number} ({run_id})", file=sys.stderr)
    return 0


def release(number: int, force: bool, reason: str) -> int:
    issue = fetch_issue(number)
    lease = lease_state(issue)
    active = lease.get("active")

    if active and not lease["expired"] and not force:
        sys.exit(
            f"next-leaf: #{number} lease aktif; "
            "`--force --reason \"...\"` olmadan bırakılmaz"
        )
    if active and lease["evidence_after"] and not force:
        sys.exit(
            f"next-leaf: #{number} lease'den sonra evidence var; "
            "`--force --reason \"...\"` olmadan bırakılmaz"
        )

    run_id = lease.get("run_id") or "none"
    gh_optional(kitgh.issue_edit_args(number, "--remove-label", "executing"))
    for assignee in issue.get("assignees") or []:
        login = assignee.get("login")
        if login:
            gh_optional(kitgh.issue_edit_args(number, "--remove-assignee", login))
    gh(
        kitgh.issue_comment_args(
            number, f"run release: `{run_id}`\nreason: {reason}"
        )
    )
    print("\n".join(routing.render_config(routing.control_config(ROOT))))
    print(f"released #{number} ({run_id})")
    return 0


DEFAULT_MAX_PARALLEL = 2


def seal_paths(seal: dict) -> set[str]:
    reference = seal.get("reference") or {}
    return {str(path) for path in reference.get("paths") or [] if str(path)}


def conflicts(seal: dict, active: list[dict]) -> bool:
    """Same file touched by an executing leaf blocks a second claim."""
    mine = seal_paths(seal)
    if not mine:
        return False
    return any(mine & seal_paths(other) for other in active)


def select_eligible(
    open_issues: list[dict],
    all_issues: list[dict],
    max_parallel: int = DEFAULT_MAX_PARALLEL,
    only: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """Leaves that may be claimed now.

    ``only`` evaluates one explicitly requested leaf against the leaves that are
    already executing. Without it the epic budget also caps how many candidates
    are offered at once; an explicit request must not depend on the order GitHub
    happens to return.
    """
    done: set[int] = set()
    for item in all_issues:
        labels = {label["name"] for label in item.get("labels", [])}
        if item["state"] == "CLOSED" or labels & {"leaf-done", "epic-done", "deferred"}:
            done.add(item["number"])

    active: dict[int, list[dict]] = {}
    for issue in open_issues:
        labels = {label["name"] for label in issue["labels"]}
        if "executing" not in labels:
            continue
        seal = parse_seal(issue.get("body", ""))
        epic = seal.get("epic")
        if epic:
            active.setdefault(int(epic), []).append(seal)

    eligible: list[dict] = []
    skipped: list[dict] = []
    for issue in open_issues:
        if only is not None and int(issue["number"]) != int(only):
            continue
        labels = {label["name"] for label in issue["labels"]}
        if "agent-approved" not in labels or labels & SKIP_LABELS:
            continue
        seal = parse_seal(issue.get("body", ""))
        if not seal:
            continue
        deps = [
            dep
            for dep in seal.get("dependencies") or []
            if isinstance(dep, dict) and dep.get("kind", "blocks") == "blocks"
        ]
        if any(dep.get("issue") not in done for dep in deps):
            skipped.append({"number": issue["number"], "reason": "bağımlılık bekliyor"})
            continue
        epic = seal.get("epic")
        if epic:
            running = active.get(int(epic), [])
            if len(running) >= max_parallel:
                skipped.append(
                    {"number": issue["number"], "reason": f"epic bütçesi dolu ({max_parallel})"}
                )
                continue
            if conflicts(seal, running):
                shared = sorted(
                    mine
                    for mine in seal_paths(seal)
                    if any(mine in seal_paths(other) for other in running)
                )
                skipped.append(
                    {
                        "number": issue["number"],
                        "reason": "dosya kesişimi: " + ", ".join(shared),
                    }
                )
                continue
        eligible.append(
            {
                "number": issue["number"],
                "title": issue["title"],
                "epic": epic,
                "risk": (seal.get("risk") or {}).get("level", "low"),
                "createdAt": issue["createdAt"],
            }
        )
        if epic and only is None:
            active.setdefault(int(epic), []).append(seal)
    eligible.sort(key=lambda item: (str(item["createdAt"]), int(item["number"])))
    return eligible, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="pick the next executable leaf")
    parser.add_argument("--list", action="store_true", help="all eligible leaves")
    parser.add_argument("--claim", action="store_true", help="claim the first leaf")
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=DEFAULT_MAX_PARALLEL,
        help="aynı epic'te eşzamanlı leaf üst sınırı",
    )
    parser.add_argument("--release", action="store_true", help="release a lease")
    parser.add_argument("--issue", type=int, help="claim/release için issue")
    parser.add_argument("--force", action="store_true", help="force a release")
    parser.add_argument("--reason", default="stale claim", help="release reason")
    parser.add_argument("--json", action="store_true", help="machine output")
    args = parser.parse_args()
    if args.max_parallel < 1:
        parser.error("--max-parallel en az 1 olmalı")

    if args.release:
        if not args.issue:
            sys.exit("next-leaf: --release requires --issue N")
        return release(args.issue, args.force, args.reason)

    open_issues = json.loads(
        gh(
            kitgh.issue_list_args(
                "open", 200, "number,title,body,labels,createdAt"
            )
        )
    )
    all_issues = json.loads(
        gh(
            kitgh.issue_list_args("all", 1000, "number,state,labels")
        )
    )
    eligible, skipped = select_eligible(
        open_issues, all_issues, args.max_parallel, only=args.issue
    )
    if args.issue is not None:
        chosen = [item for item in eligible if int(item["number"]) == args.issue]
        if not chosen:
            reason = next(
                (item["reason"] for item in skipped if int(item["number"]) == args.issue),
                "leaf uygun değil (agent-approved/dependency/bütçe)",
            )
            print(f"next-leaf: #{args.issue} claim edilemez — {reason}", file=sys.stderr)
            return 1
        eligible = chosen

    root = epic_worktree.project_root()
    try:
        dirty = process_gate.dirty_sources(root)
    except RuntimeError:
        print("BLOCKED: kaynak durumu okunamadı (git); fail-closed", file=sys.stderr)
        return 1
    if not eligible:
        if dirty:
            print(
                "BLOCKED: unsealed work — kaynak dosyalari kirli ama "
                "agent-approved leaf yok:",
                file=sys.stderr,
            )
            for path in dirty[:10]:
                print(f"  - {path}", file=sys.stderr)
            print(
                "  Once epic + leaf muhurle veya degisiklikleri epic "
                "worktree'sine tasi.",
                file=sys.stderr,
            )
            return 1
        if args.json:
            print(
                json.dumps(
                    {
                        "eligible": [],
                        "skipped": skipped,
                        "budget": budget.load(epic_worktree.project_root()),
                        "config": routing.control_config(ROOT),
                    },
                    indent=2,
                )
            )
        else:
            print("\n".join(routing.render_config(routing.control_config(ROOT))))
            print("no work")
            for item in skipped:
                print(f"  - #{item['number']}: {item['reason']}", file=sys.stderr)
        return 0
    if dirty:
        print(
            f"uyari: kirli kaynak dosyalari ({len(dirty)}); claim edilen "
            "epic worktree'sine tasi",
            file=sys.stderr,
        )

    if args.json and not args.claim:
        print(
            json.dumps(
                {
                    "eligible": eligible,
                    "skipped": skipped,
                    "budget": budget.load(epic_worktree.project_root()),
                    "config": routing.control_config(ROOT),
                },
                indent=2,
            )
        )
        return 0

    if args.list and not args.claim:
        print("\n".join(routing.render_config(routing.control_config(ROOT))))
        for item in eligible:
            print(f"#{item['number']}  {item['title']}  [{item['risk']}]")
        for item in skipped:
            print(f"  - #{item['number']}: {item['reason']}", file=sys.stderr)
        return 0

    if args.claim:
        target = None
        if args.issue:
            target = next(
                (item for item in eligible if item["number"] == args.issue), None
            )
            if not target:
                sys.exit(f"next-leaf: #{args.issue} uygun değil")
        else:
            target = eligible[0]
        status = claim(target["number"], target["epic"], target["risk"])
        if status == 0:
            if prepare_worktree(target["number"], target["epic"]) != 0:
                release(
                    target["number"],
                    True,
                    "epic worktree/run hazır değil; claim geri alındı",
                )
                return 1
            print("\n".join(routing.render_config(routing.control_config(ROOT))))
            print(target["number"])
        return status

    print("\n".join(routing.render_config(routing.control_config(ROOT))))
    print(eligible[0]["number"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
