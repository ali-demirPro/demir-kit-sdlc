#!/usr/bin/env python3
"""Lint a leaf seal before it becomes agent-approved.

Usage:
  python3 delivery/scripts/seal_lint.py --body /tmp/leaf.md
  python3 delivery/scripts/seal_lint.py --body /tmp/leaf.md --json --strict
"""

from __future__ import annotations

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
    "/",
)

CASE_MARKERS = (
    ".py",
    "doctor",
    "pytest",
    "python3",
    "unittest",
    "bash",
    ".sh",
    "npm",
    "make",
    "swift",
    "go test",
    "cargo",
    "exit 0",
    "./",
    "/",
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
