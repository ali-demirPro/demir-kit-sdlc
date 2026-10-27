#!/usr/bin/env python3
"""Validate and enforce capability eval scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "delivery" / "agents"
MIN_ROWS = 10
RESULT_VALUES = {"pass", "fail", "skip"}


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def parse_eval(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0].lower() in {"id", "senaryo"}:
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) < 4:
            continue
        rows.append(
            {
                "id": cells[0],
                "scenario": cells[1],
                "expected": cells[2],
                "fail": cells[3],
            }
        )
    return rows


def check_eval_file(path: Path, minimum: int = MIN_ROWS) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"eval dosyası yok: {path}"]
    rows = parse_eval(path)
    if len(rows) < minimum:
        errors.append(f"{path}: en az {minimum} senaryo (şu an {len(rows)})")
    seen: set[str] = set()
    for row in rows:
        if not row["id"]:
            errors.append(f"{path}: boş senaryo ID")
        elif row["id"] in seen:
            errors.append(f"{path}: tekrarlı senaryo ID {row['id']}")
        seen.add(row["id"])
        for key in ("scenario", "expected", "fail"):
            if not row[key]:
                errors.append(f"{path}: {row['id']} için {key} boş")
    return errors


def agent_variants() -> list[dict]:
    records: list[dict] = []
    for path in sorted(AGENTS.rglob("agent.yaml")):
        role = str(path.parent.relative_to(AGENTS))
        agent = load_yaml(path)
        for cap_id, spec in (agent.get("variants") or {}).items():
            if not isinstance(spec, dict):
                continue
            records.append(
                {
                    "role": role,
                    "capability": cap_id,
                    "eval": spec.get("eval"),
                    "doc": spec.get("doc"),
                    "min_level": spec.get("min_level"),
                    "dir": path.parent,
                }
            )
    return records


def check_all() -> list[str]:
    errors: list[str] = []
    for record in agent_variants():
        eval_rel = str(record.get("eval") or "")
        errors.extend(
            check_eval_file(record["dir"] / eval_rel)
            if eval_rel
            else [f"{record['role']}.{record['capability']}: eval yok"]
        )
    return errors


def scenario_ids(path: Path) -> list[str]:
    return [row["id"] for row in parse_eval(path)]


def validate_results(payload: dict, expected: list[str], allow_skip: bool = False) -> list[str]:
    errors: list[str] = []
    results = payload.get("results")
    if not isinstance(results, list):
        return ["results liste değil"]
    seen: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            errors.append("result öğesi mapping değil")
            continue
        rid = str(item.get("id") or "")
        verdict = item.get("result")
        if rid not in expected:
            errors.append(f"bilinmeyen senaryo ID: {rid}")
        if rid in seen:
            errors.append(f"tekrarlı sonuç ID: {rid}")
        seen.add(rid)
        if verdict not in RESULT_VALUES:
            errors.append(f"{rid}: result pass/fail/skip olmalı")
        elif verdict == "fail":
            errors.append(f"{rid}: fail")
        elif verdict == "skip" and not allow_skip:
            errors.append(f"{rid}: skip")
    for rid in expected:
        if rid not in seen:
            errors.append(f"eksik sonuç: {rid}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="capability eval runner")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--role")
    parser.add_argument("--eval")
    parser.add_argument("--results", type=Path)
    parser.add_argument("--allow-skip", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.check:
        errors = check_all()
        for message in errors:
            print(f"[fail] {message}")
        print(f"{len(errors)} hata")
        return 1 if errors else 0

    if args.list:
        for record in agent_variants():
            path = record["dir"] / str(record.get("eval") or "")
            count = len(parse_eval(path)) if path.is_file() else 0
            print(
                f"{record['role'].ljust(20)} {record['capability'].ljust(24)} "
                f"{str(record.get('eval')).ljust(18)} {count}"
            )
        return 0

    if args.template:
        if not args.role or not args.eval:
            sys.exit("eval: --template için --role ve --eval gerekli")
        record = next(
            (
                item
                for item in agent_variants()
                if item["role"] == args.role and item["eval"] == args.eval
            ),
            None,
        )
        if not record:
            sys.exit(f"eval: {args.role} / {args.eval} bulunamadı")
        ids = scenario_ids(record["dir"] / args.eval)
        print(
            json.dumps(
                {
                    "role": args.role,
                    "eval": args.eval,
                    "results": [
                        {"id": rid, "result": "pass", "note": ""} for rid in ids
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.results:
        try:
            payload = json.loads(args.results.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            sys.exit(f"eval: {exc}")
        role = payload.get("role")
        eval_name = payload.get("eval")
        record = next(
            (
                item
                for item in agent_variants()
                if item["role"] == role and item["eval"] == eval_name
            ),
            None,
        )
        if not record:
            sys.exit(f"eval: {role} / {eval_name} bulunamadı")
        errors = validate_results(
            payload,
            scenario_ids(record["dir"] / eval_name),
            allow_skip=args.allow_skip,
        )
        for message in errors:
            print(f"[fail] {message}")
        print(f"{len(errors)} hata")
        return 1 if errors else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
