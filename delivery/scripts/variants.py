#!/usr/bin/env python3
"""Validate role capability → variant maps."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "delivery" / "agents"
LEVELS = ["aware", "practitioner", "expert", "authority"]


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: YAML okunamadı — {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: kök mapping değil")
    return data


def load_agent(role: str) -> dict:
    return load_yaml(AGENTS / role / "agent.yaml")


def validate_agent(
    role: str,
    agent: dict,
    capabilities: dict,
    roles: set[str],
    root: Path = ROOT,
    matrix: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    agent_dir = root / "delivery" / "agents" / role

    if agent.get("id") != role:
        errors.append(f"{role}: id '{agent.get('id')}' rol adıyla eşleşmiyor")

    for doc in agent.get("base_docs") or []:
        if not (agent_dir / str(doc)).is_file():
            errors.append(f"{role}: base doc yok — {doc}")

    required = agent.get("capabilities_required") or []
    if not isinstance(required, list) or not required:
        errors.append(f"{role}: capabilities_required boş")
        required = []
    for cap_id in required:
        if cap_id not in capabilities:
            errors.append(f"{role}: bilinmeyen capability — {cap_id}")

    variants = agent.get("variants")
    if not isinstance(variants, dict) or not variants:
        errors.append(f"{role}: variants boş")
        variants = {}
    if set(variants) != set(required):
        missing = set(required) - set(variants)
        extra = set(variants) - set(required)
        if missing:
            errors.append(f"{role}: variant eksik — {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{role}: fazla variant — {', '.join(sorted(extra))}")

    for cap_id, spec in variants.items():
        if not isinstance(spec, dict):
            errors.append(f"{role}.{cap_id}: variant mapping değil")
            continue
        doc = str(spec.get("doc") or "")
        eval_doc = str(spec.get("eval") or "")
        if not doc.startswith("variants/") or not doc.endswith(".md"):
            errors.append(f"{role}.{cap_id}: doc yolu variants/*.md olmalı")
        elif not (agent_dir / doc).is_file():
            errors.append(f"{role}.{cap_id}: variant doc yok — {doc}")
        if not eval_doc.startswith("evals/") or not eval_doc.endswith(".md"):
            errors.append(f"{role}.{cap_id}: eval yolu evals/*.md olmalı")
        elif not (agent_dir / eval_doc).is_file():
            errors.append(f"{role}.{cap_id}: eval doc yok — {eval_doc}")
        level = spec.get("min_level")
        if level not in LEVELS:
            errors.append(f"{role}.{cap_id}: min_level geçersiz — {level}")
        elif level == "authority":
            errors.append(f"{role}.{cap_id}: min_level authority olamaz")
        elif matrix:
            profile = (matrix.get("roles") or {}).get(role) or {}
            expected = (profile.get("capabilities") or {}).get(
                cap_id, profile.get("default_level", "aware")
            )
            if LEVELS.index(level) < LEVELS.index(expected):
                errors.append(
                    f"{role}.{cap_id}: min_level {level} rol matrisi "
                    f"seviyesi {expected} altında"
                )

    for target in agent.get("handoffs") or []:
        if target not in roles:
            errors.append(f"{role}: bilinmeyen handoff — {target}")

    if not agent.get("escalation"):
        errors.append(f"{role}: escalation boş")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="agent variant validation")
    parser.add_argument("--role", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    capabilities = load_yaml(ROOT / "delivery" / "capabilities" / "registry.yaml")
    cap_map = capabilities.get("capabilities") or {}
    matrix = load_yaml(ROOT / "delivery" / "capabilities" / "role-matrix.yaml")
    registry = load_yaml(ROOT / "delivery" / "registry.yaml")
    roles = set(registry.get("role_order_default") or []) | {"orchestrator"}

    targets = args.role or [
        path.name
        for path in AGENTS.iterdir()
        if path.is_dir() and (path / "agent.yaml").is_file()
    ]
    results: dict[str, list[str]] = {}
    for role in targets:
        try:
            agent = load_agent(role)
        except ValueError as exc:
            results[role] = [str(exc)]
            continue
        results[role] = validate_agent(role, agent, cap_map, roles, matrix=matrix)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for role, errors in results.items():
            print(f"{role}: {'OK' if not errors else str(len(errors)) + ' hata'}")
            for message in errors:
                print(f"  [fail] {message}")
    return 1 if any(results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
