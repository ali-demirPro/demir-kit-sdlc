#!/usr/bin/env python3
"""Close one checkpoint in a single step.

Usage:
  python3 delivery/scripts/cp_close.py --issue 148 --cp CP-1 --evidence /tmp/e.yaml
  python3 delivery/scripts/cp_close.py --issue 148 --cp CP-1 --evidence /tmp/e.yaml --apply
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cycle  # noqa: E402
import doctor  # noqa: E402
import evidence as evidence_lib  # noqa: E402
import routing  # noqa: E402
import update as update_mod  # noqa: E402

SCHEMA = ROOT / "delivery" / "schemas" / "evidence.schema.json"
DEFAULT_GATE_LEVEL = "fast"
INDEX_DIR = ".kit"
INDEX_NAME = "evidence.jsonl"


def gh(args: list[str], stdin: str | None = None) -> str:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, input=stdin
    )
    if result.returncode != 0:
        raise SystemExit(f"cp_close: gh failed — {result.stderr.strip()}")
    return result.stdout


def repo_name() -> str:
    project = routing.project_root(ROOT)
    ecosystem = yaml.safe_load((project / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        raise SystemExit("cp_close: ecosystem.yaml tracker.repo yok")
    return repo


def issue_payload(repo: str, issue: int) -> dict:
    return json.loads(gh(["api", f"repos/{repo}/issues/{issue}"]))


def load_evidence(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```yaml\s+demir-kit-evidence\s*\n(.*?)```", text, re.S)
    raw = match.group(1) if match else text
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SystemExit(f"cp_close: evidence YAML geçersiz — {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("cp_close: evidence mapping olmalı")
    return data


def risk_of(body: str) -> str:
    seal = routing.seal_body(body)
    return str((seal.get("risk") or {}).get("level") or "low")


def validate_record(
    record: dict, issue: int, cp_id: str, risk: str, repo: str
) -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = doctor.validate_schema(record, schema)
    if record.get("cp_id") != cp_id:
        errors.append(f"cp_id '{record.get('cp_id')}' != '{cp_id}'")
    if record.get("issue") != issue:
        errors.append(f"issue {record.get('issue')} != {issue}")
    if record.get("status") != "pass":
        errors.append("status 'pass' değil")
    verification = record.get("verification")
    if isinstance(verification, dict):
        errors += evidence_lib.verify(
            verification,
            root=ROOT,
            repo=repo,
            risk=risk,
            implementer=str(record.get("agent") or ""),
        )
    elif record.get("status") == "pass":
        errors.append("verification bloğu yok")
    return errors


def gate_command(issue: int, cp_id: str, level: str = DEFAULT_GATE_LEVEL) -> str:
    prefix = routing.kit_prefix(ROOT)
    project = routing.project_root(ROOT)
    gate = project / prefix / "delivery" / "scripts" / "gate.sh"
    if gate.is_file():
        suffix = " --fast" if level == "fast" else ""
        return f"./{prefix}delivery/scripts/gate.sh --issue {issue} --checkpoint {cp_id}{suffix}"
    command = f"./{prefix}delivery/scripts/doctor.sh --issue {issue} --checkpoint {cp_id}"
    if prefix:
        command += " --product --root ."
    return command


def run_gate(command: str) -> tuple[int, str]:
    result = subprocess.run(
        command, shell=True, cwd=str(routing.project_root(ROOT)),
        capture_output=True, text=True,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, "\n".join(output.splitlines()[-40:])


def comment_body(record: dict) -> str:
    return (
        "```yaml\ndemir-kit-evidence\n"
        + yaml.safe_dump(record, sort_keys=False, allow_unicode=True)
        + "```\n"
    )


def post_comment(repo: str, issue: int, record: dict) -> str | None:
    body = comment_body(record)
    payload = json.dumps({"body": body})
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
        input=payload,
    )
    if result.returncode != 0:
        return None
    try:
        return str(json.loads(result.stdout).get("id") or "")
    except json.JSONDecodeError:
        return None


def delete_comment(repo: str, comment_id: str) -> bool:
    result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "DELETE",
            f"repos/{repo}/issues/comments/{comment_id}",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def verify_issue(issue: int, evidence: Path) -> tuple[int, str]:
    project = routing.project_root(ROOT)
    prefix = routing.kit_prefix(ROOT)
    script = project / prefix / "delivery" / "scripts" / "doctor.sh"
    command = [str(script), "--issue", str(issue), "--evidence", str(evidence)]
    if prefix:
        command += ["--product", "--root", "."]
    result = subprocess.run(
        command,
        cwd=str(project),
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, "\n".join(output.splitlines()[-20:])


def checkpoint(issue: int, cp_id: str) -> bool:
    result = update_mod.orca_checkpoint(
        "progress",
        f"{cp_id} kapandı (#{issue})",
        "sonraki CP",
        False,
    )
    return bool(result and result.get("ok"))


def index_row(record: dict, issue: int, cp_id: str) -> dict:
    """One evidence-index line: only the reviewers this evidence really names."""
    verification = record.get("verification")
    verification = verification if isinstance(verification, dict) else {}
    raw = verification.get("reviewers")
    raw = raw if isinstance(raw, list) else []
    reviewers = [
        str(item.get("id")).strip()
        for item in raw
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    reviews = record.get("reviews")
    reviews = reviews if isinstance(reviews, dict) else {}
    return {
        "ts": cycle.now(),
        "issue": int(issue),
        "cp": str(cp_id),
        "reviewers": reviewers,
        "risk": reviews.get("risk"),
        "gate_level": record.get("gate_level"),
        "commit": verification.get("commit"),
    }


def record_evidence_index(project: Path, record: dict, issue: int, cp_id: str) -> bool:
    """Append this CP's real reviewer ids to `.kit/evidence.jsonl`.

    The fleet audit counts review rounds from here. A placeholder id or a commit
    count is not evidence that somebody reviewed the diff.
    """
    path = Path(project) / INDEX_DIR / INDEX_NAME
    row = index_row(record, issue, cp_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        kept: list[str] = []
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    old = json.loads(line)
                except json.JSONDecodeError:
                    kept.append(line)
                    continue
                same = (
                    isinstance(old, dict)
                    and str(old.get("issue")) == str(int(issue))
                    and str(old.get("cp") or "") == str(cp_id)
                )
                if not same:
                    kept.append(line)
        kept.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    except OSError:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="close one checkpoint")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--cp", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="gate, post, verify, checkpoint")
    parser.add_argument("--gate-level", choices=["full", "fast"], default=DEFAULT_GATE_LEVEL)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo = repo_name()
    payload = issue_payload(repo, args.issue)
    risk = risk_of(payload.get("body") or "")
    record = load_evidence(args.evidence)
    errors = validate_record(record, args.issue, args.cp, risk, repo)
    if errors:
        for error in errors:
            print(f"cp_close: {error}", file=sys.stderr)
        return 1

    command = gate_command(args.issue, args.cp, args.gate_level)
    if "gate.sh" in command:
        record["gate_level"] = args.gate_level
    else:
        record.pop("gate_level", None)
    plan = {
        "issue": args.issue,
        "cp_id": args.cp,
        "risk": risk,
        "gate": command,
        "evidence_chars": len(yaml.safe_dump(record, allow_unicode=True)),
        "reviewers": len(record.get("reviewers") or [])
        if isinstance(record.get("verification"), dict)
        else 0,
        "apply": args.apply,
    }
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2) if args.json else "\n".join(
            [
                f"CP close planı — #{args.issue} {args.cp} (risk {risk})",
                f"gate: {command}",
                f"evidence: {plan['evidence_chars']} karakter",
                "yazmak için --apply",
            ]
        ))
        return 0

    code, output = run_gate(command)
    if code != 0:
        print(f"cp_close: gate düştü (exit {code})\n{output}", file=sys.stderr)
        return 1

    comment_id = post_comment(repo, args.issue, record)
    if not comment_id:
        print("cp_close: yorum yazılamadı", file=sys.stderr)
        return 1

    code, output = verify_issue(args.issue, args.evidence)
    if code != 0:
        if delete_comment(repo, comment_id):
            print(
                f"cp_close: evidence doctor'da düştü, yorum geri alındı\n{output}",
                file=sys.stderr,
            )
        else:
            print(
                f"cp_close: evidence doctor'da düştü; yorum SİLİNEMEDİ "
                f"(comment {comment_id}) — elle silinmeli\n{output}",
                file=sys.stderr,
            )
        return 1

    synced = checkpoint(args.issue, args.cp)
    if not synced:
        print("cp_close: Orca checkpoint yazılamadı (issue/PR yine de geçerli)", file=sys.stderr)
    indexed = record_evidence_index(
        cycle.project_root(ROOT), record, args.issue, args.cp
    )
    if not indexed:
        print("cp_close: kanıt indeksi yazılamadı (CP yine de kapandı)", file=sys.stderr)
    result = {
        **plan,
        "comment_id": comment_id,
        "checkpoint": synced,
        "indexed": indexed,
        "status": "pass",
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"CP kapandı — #{args.issue} {args.cp} · gate 0 · evidence yazıldı · "
            f"checkpoint {'yazıldı' if synced else 'yazılamadı'}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
