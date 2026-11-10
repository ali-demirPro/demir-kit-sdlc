#!/usr/bin/env python3
"""Lint a leaf seal before it becomes agent-approved.

Usage:
  python3 delivery/scripts/seal_lint.py --body /tmp/leaf.md
  python3 delivery/scripts/seal_lint.py --body /tmp/leaf.md --json --strict
"""

from __future__ import annotations

import re

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

VAGUE = {
    "iyi",
    "doğru",
    "uygun",
    "hızlı",
    "temiz",
    "düzgün",
    "kolay",
    "güzel",
    "sağlam",
    "yeterli",
    "makul",
    "optimize",
    "iyileştir",
    "geliştir",
    "kullanıcı dostu",
}

OBSERVABLE = (
    "`",
    "dosya",
    "yol",
    "komut",
    "test",
    "exit",
    ".py",
    ".md",
    "python3",
    "unittest",
    "pytest",
    "doctor",
    "bash",
    ".sh",
    "sayı",
    "adet",
    "etiket",
    "url",
    "snapshot",
    "döner",
    "yazar",
    "geçer",
    "çalışır",
    "görünür",
    "içerir",
    "var",
)

CASE_MARKERS = (
    ".py",
    "doctor",
    "komut",
    "pytest",
    "python3",
    "unittest",
    "bash",
    ".sh",
    ".ts",
    ".tsx",
    "orca plugin",
    "npm",
    "swift",
    "go test",
    "cargo",
    "exit 0",
    "./",
)

VAGUE_PATTERN = re.compile(
    r"(?<![a-zçğıöşü])(" + "|".join(sorted(VAGUE)) + r")(?![a-zçğıöşü])",
    re.I,
)


def seal_from_text(text: str) -> dict:
    match = re.search(r"```yaml\s+demir-kit\s*\n(.*?)```", text, re.S)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def has_observable(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\d", text):
        return True
    return any(marker in lowered for marker in OBSERVABLE)


def lint(seal: dict) -> list[dict]:
    findings: list[dict] = []
    acs = seal.get("acceptance_criteria") or []
    cases = []
    for plan_index, plan in enumerate(seal.get("tests_plan") or []):
        if not isinstance(plan, dict):
            continue
        for case_index, case in enumerate(plan.get("cases") or []):
            if isinstance(case, dict):
                cases.append((plan_index, case_index, plan.get("checkpoint_id"), case))
    cps = seal.get("checkpoints") or []
    cp_ids = {str(cp.get("id")) for cp in cps if isinstance(cp, dict)}
    ac_ids = {str(ac.get("id")) for ac in acs if isinstance(ac, dict)}

    for index, ac in enumerate(acs):
        if not isinstance(ac, dict):
            continue
        text = str(ac.get("text") or "")
        if not has_observable(text):
            findings.append(
                {
                    "severity": "warning",
                    "path": f"$.acceptance_criteria[{index}].text",
                    "message": "gözlenebilir sonuç yok",
                }
            )
        elif VAGUE_PATTERN.search(text):
            findings.append(
                {
                    "severity": "warning",
                    "path": f"$.acceptance_criteria[{index}].text",
                    "message": "belirsiz ifade var",
                }
            )

    seen: set[str] = set()
    for plan_index, case_index, cp_id, case in cases:
        base = f"$.tests_plan[{plan_index}].cases[{case_index}]"
        case_id = str(case.get("id") or "")
        if case_id in seen:
            findings.append(
                {
                    "severity": "error",
                    "path": f"{base}.id",
                    "message": f"tekrarlı case id: {case_id}",
                }
            )
        seen.add(case_id)
        ac_ref = str(case.get("ac") or "")
        if ac_ref and ac_ref not in ac_ids:
            findings.append(
                {
                    "severity": "error",
                    "path": f"{base}.ac",
                    "message": f"bilinmeyen AC: {ac_ref}",
                }
            )
        if cp_id and str(cp_id) not in cp_ids:
            findings.append(
                {
                    "severity": "error",
                    "path": base,
                    "message": f"bilinmeyen CP: {cp_id}",
                }
            )
        check = str(case.get("check") or "")
        text = str(case.get("text") or "")
        if check in {"unit", "gate"} and not any(
            marker in text.lower() for marker in CASE_MARKERS
        ):
            findings.append(
                {
                    "severity": "warning",
                    "path": f"{base}.text",
                    "message": f"{check} case'i çalıştırılabilir bir iz taşımıyor",
                }
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="lint a leaf seal")
    parser.add_argument("--body", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    seal = seal_from_text(args.body.read_text(encoding="utf-8"))
    if not seal:
        print("seal_lint: `demir-kit` bloğu yok", file=sys.stderr)
        return 1
    findings = lint(seal)
    errors = [item for item in findings if item["severity"] == "error"]
    warnings = [item for item in findings if item["severity"] == "warning"]
    if args.json:
        print(json.dumps({"findings": findings}, ensure_ascii=False, indent=2))
    else:
        for item in findings:
            print(f"[{item['severity']}] {item['path']}: {item['message']}")
        print(
            f"{len(errors)} hata · {len(warnings)} uyarı"
        )
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())


def validate_epic_record(
    body: str,
    labels: list[str] | set[str],
    child_labels: dict[int, list[str]] | None = None,
) -> list[str]:
    """Shape and child checks for an epic seal; empty when not an epic."""
    labels = set(labels)
    if "epic" not in labels:
        return []
    match = re.search(r"```yaml\s+demir-kit-epic\s*\n(.*?)```", body, re.S)
    if not match:
        if "```yaml demir-kit-epic" in body:
            return ["epic seal: YAML bloğu kapanmamış"]
        return ["epic seal: `demir-kit-epic` bloğu yok"]
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        return [f"epic seal: YAML geçersiz — {exc}"]
    if not isinstance(data, dict):
        return ["epic seal: kök mapping değil"]
    errors: list[str] = []
    children = data.get("children")
    if not isinstance(children, list) or not children:
        errors.append("epic seal: children boş")
        return errors
    for child in children:
        if not isinstance(child, int) or child < 1:
            errors.append(f"epic seal: geçersiz child {child!r}")
            continue
        if child_labels is None:
            continue
        if child not in child_labels:
            errors.append(f"epic seal: child #{child} yok")
            continue
        labels_c = child_labels.get(child)
        if labels_c is None:
            errors.append(f"epic seal: child #{child} okunamadı")
        elif "epic" in set(labels_c):
            errors.append(f"epic seal: child #{child} epic olamaz")
    return errors




def child_labels_for(repo, body: str, fetch) -> dict[int, list[str] | None] | None:
    """Labels of the epic's children, fetched once for seal validation."""
    import json

    if not repo:
        return None
    match = re.search(r"```yaml\s+demir-kit-epic\s*\n(.*?)```", body, re.S)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    labels: dict[int, list[str] | None] = {}
    for child in data.get("children") or []:
        if not isinstance(child, int):
            continue
        raw = fetch(f"repos/{repo}/issues/{child}")
        if not raw:
            labels[child] = None
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            labels[child] = None
            continue
        labels[child] = [item.get("name") for item in payload.get("labels", [])]
    return labels
