#!/usr/bin/env python3
"""Read-only health-check prerequisite table.

The table in ``delivery/protocol/health-check.md`` is the single source:
every row names one check, its tool, and whether the tool is required. A
missing required tool makes the run ``ready: false``; a missing optional tool
is reported as ``not_run`` and never counted as a pass. The row status ``fail``
is reserved for a future check probe; today structural problems (unknown
control, unknown tool, wrong row count) exit non-zero instead. The script
writes nothing, starts no processes and makes no network calls.

Usage:
  python3 delivery/scripts/health_check.py
  python3 delivery/scripts/health_check.py --json
  python3 delivery/scripts/health_check.py --protocol /tmp/health-check.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "delivery" / "protocol" / "health-check.md"
EXPECTED_ROWS = 16
ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*([A-Za-z0-9._-]+)\s*\|\s*(true|false)\s*\|\s*$"
)
EXPECTED_CHECKS = (
    "ecosystem.yaml ve yüzey yolları",
    "behavior komutu çalıştırılabilir",
    "UI CP gates.ui ve ui_compare",
    "UI snapshot tanımı",
    "native selftest",
    "gh auth status",
    "orca status ve epic worktree",
    "orca worktree ps ve host list",
    "orca tab, computer ve emulator",
    "architecture baseline kaydı",
    "architecture boundaries.md",
    "discovery-approved ve brief",
    "pilot_mode MVO kuralları",
    "feasibility blocker kararı",
    "commercial baseline ve positioning",
    "monetization-brief.md",
)
TOOLS = {
    "python3": "python3",
    "bash": "bash",
    "git": "git",
    "gh": "gh",
    "orca": "orca",
}


def load_table(path: Path = PROTOCOL) -> list[dict]:
    """Parse the protocol table; any structural drift is an error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"health-check.md okunamadı: {exc}") from exc
    rows: list[dict] = []
    for line in text.splitlines():
        match = ROW_RE.match(line.strip())
        if not match:
            continue
        rows.append(
            {
                "id": int(match.group(1)),
                "check": match.group(2),
                "tool": match.group(3),
                "required": match.group(4) == "true",
            }
        )
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(
            f"health-check tablosu {EXPECTED_ROWS} satır olmalı, {len(rows)} bulundu"
        )
    if [row["id"] for row in rows] != list(range(1, EXPECTED_ROWS + 1)):
        raise ValueError("health-check tablosu 1..16 sırasını taşımıyor")
    for row in rows:
        if row["tool"] not in TOOLS:
            raise ValueError(
                f"bilinmeyen araç: {row['tool']} (satır {row['id']})"
            )
        if row["check"] not in EXPECTED_CHECKS:
            raise ValueError(
                f"bilinmeyen kontrol: {row['check']} (satır {row['id']})"
            )
    if {row["check"] for row in rows} != set(EXPECTED_CHECKS):
        raise ValueError("health-check tablosu 16 kontrolle birebir eşleşmiyor")
    return rows


def tool_path(tool: str, path_value: str | None = None) -> str | None:
    """Locate a tool on PATH without spawning it."""
    executable = TOOLS[tool]
    if path_value is None:
        return shutil.which(executable)
    return shutil.which(executable, path=path_value)


def run(path: Path = PROTOCOL, path_value: str | None = None) -> dict:
    rows = load_table(path)
    if path_value is None:
        path_value = os.environ.get("PATH", "")
    output: list[dict] = []
    blockers: list[str] = []
    warnings: list[str] = []
    for row in rows:
        found = tool_path(row["tool"], path_value)
        if found:
            status = "pass"
            reason = f"araç PATH'te: {found}"
        else:
            status = "not_run"
            reason = f"araç PATH'te yok: {TOOLS[row['tool']]}"
            target = blockers if row["required"] else warnings
            target.append(f"{row['id']}. {row['check']} — {reason}")
        output.append(
            {
                "id": row["id"],
                "check": row["check"],
                "tool": row["tool"],
                "required": row["required"],
                "status": status,
                "reason": reason,
            }
        )
    question = None
    if blockers:
        question = (
            "Gerekli araçlardan bazıları kurulu değil. Araçları şimdi mi "
            "kuralım, yoksa bu adımı sonraki tura mı bırakalım?"
        )
    return {
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "rows": output,
        "question": question,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="health-check prerequisite table")
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--path", help="PATH override (test için)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        data = run(args.protocol, args.path)
    except ValueError as exc:
        print(f"health_check: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if data["ready"] else 1
    print(f"ready: {str(data['ready']).lower()}")
    print("blockers:")
    for item in data["blockers"]:
        print(f"  - {item}")
    print("warnings:")
    for item in data["warnings"]:
        print(f"  - {item}")
    print("rows:")
    for row in data["rows"]:
        print(
            f"  - {row['id']}. [{row['status']}] {row['check']} "
            f"({row['tool']}, required={str(row['required']).lower()}) — "
            f"{row['reason']}"
        )
    if data["question"]:
        print(f"question: {data['question']}")
    return 0 if data["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
