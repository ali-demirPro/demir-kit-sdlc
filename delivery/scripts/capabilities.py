#!/usr/bin/env python3
"""Capability registry and role-matrix tooling."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CAP_DIR = ROOT / "delivery" / "capabilities"
REGISTRY = CAP_DIR / "registry.yaml"
MATRIX = CAP_DIR / "role-matrix.yaml"

LEVELS = ["aware", "practitioner", "expert", "authority"]
RISKS = ["low", "medium", "high", "critical"]
CAP_RE = re.compile(r"^(platform|domain|distribution|quality)\.[a-z0-9_]+$")


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: YAML okunamadı — {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: kök mapping değil")
    return data


def register(role: str) -> int:
    if role not in LEVELS:
        raise ValueError(f"bilinmeyen seviye: {role}")
    return LEVELS.index(role)


def effective_level(
    level: str, risk: str, registry: dict, capability_level: str | None = None
) -> str:
    minimum = ((registry.get("risk_requirements") or {}).get(risk) or {}).get(
        "minimum", "aware"
    )
    floor = max(register(level), register(minimum))
    if capability_level:
        floor = max(floor, register(capability_level))
    return LEVELS[floor]


def validate_references(
    registry: dict,
    matrix: dict,
    agent_roles: set[str],
    pack_names: set[str],
    required_roles: set[str],
) -> list[str]:
    errors: list[str] = []

    levels = registry.get("levels")
    if not isinstance(levels, list) or set(levels) != set(LEVELS):
        errors.append("levels aware/practitioner/expert/authority olmalı")

    for risk in RISKS:
        spec = (registry.get("risk_requirements") or {}).get(risk)
        if not isinstance(spec, dict):
            errors.append(f"risk_requirements.{risk} yok")
            continue
        if spec.get("minimum") not in LEVELS:
            errors.append(f"risk_requirements.{risk}.minimum geçersiz")
        elif spec.get("minimum") == "authority":
            errors.append(
                f"risk_requirements.{risk}.minimum authority olamaz (agent)"
            )
        approvers = spec.get("approvers") or []
        if not isinstance(approvers, list) or not approvers:
            errors.append(f"risk_requirements.{risk}.approvers boş")
        for role in approvers:
            if role not in agent_roles:
                errors.append(f"risk_requirements.{risk}: bilinmeyen rol {role}")
        if spec.get("human_gate") not in {"none", "exhaustion", "leaf", "always"}:
            errors.append(f"risk_requirements.{risk}.human_gate geçersiz")
        if not isinstance(spec.get("human_count"), int):
            errors.append(f"risk_requirements.{risk}.human_count integer olmalı")

    capabilities = registry.get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        errors.append("capabilities boş")
        capabilities = {}

    for cap_id, cap in capabilities.items():
        if not CAP_RE.match(cap_id):
            errors.append(f"capability id geçersiz: {cap_id}")
        if not isinstance(cap, dict):
            errors.append(f"{cap_id}: obje değil")
            continue
        roles = cap.get("roles")
        if not isinstance(roles, dict) or not roles:
            errors.append(f"{cap_id}: roles boş")
            roles = {}
        for role, level in roles.items():
            if role not in agent_roles:
                errors.append(f"{cap_id}: bilinmeyen rol {role}")
            if level not in LEVELS:
                errors.append(f"{cap_id}.{role}: geçersiz seviye {level}")
            elif level == "authority":
                errors.append(f"{cap_id}.{role}: agent authority olamaz")
        if roles and not any(
            register(level) >= register("practitioner") for level in roles.values()
        ):
            errors.append(f"{cap_id}: en az bir practitioner rol gerekli")
        for pack in cap.get("packs") or []:
            if pack not in pack_names:
                errors.append(f"{cap_id}: bilinmeyen pack {pack}")
        match = cap.get("match")
        if not isinstance(match, dict) or not any(
            isinstance(value, list) and value
            for value in match.values()
        ):
            errors.append(f"{cap_id}: match sinyali boş")

    matrix_roles = matrix.get("roles")
    if not isinstance(matrix_roles, dict) or not matrix_roles:
        errors.append("role-matrix roles boş")
        matrix_roles = {}

    for role in required_roles:
        if role not in matrix_roles:
            errors.append(f"role-matrix eksik rol: {role}")

    for role, profile in matrix_roles.items():
        if role not in agent_roles:
            errors.append(f"role-matrix bilinmeyen rol: {role}")
        if not isinstance(profile, dict):
            errors.append(f"role-matrix.{role}: obje değil")
            continue
        if profile.get("default_level") not in LEVELS:
            errors.append(f"role-matrix.{role}.default_level geçersiz")
        elif profile.get("default_level") == "authority":
            errors.append(f"role-matrix.{role}.default_level authority olamaz")
        overrides = profile.get("capabilities")
        if not isinstance(overrides, dict) or not overrides:
            errors.append(f"role-matrix.{role}: capability override boş")
            overrides = {}
        for cap_id, level in overrides.items():
            if cap_id not in capabilities:
                errors.append(f"role-matrix.{role}: bilinmeyen capability {cap_id}")
            if level not in LEVELS:
                errors.append(f"role-matrix.{role}.{cap_id}: geçersiz seviye")
            elif level == "authority":
                errors.append(
                    f"role-matrix.{role}.{cap_id}: agent authority olamaz"
                )
        for key in ("focus", "evidence"):
            values = profile.get(key)
            if not isinstance(values, list) or not values:
                errors.append(f"role-matrix.{role}.{key} boş")

    return errors


def load() -> tuple[dict, dict]:
    return load_yaml(REGISTRY), load_yaml(MATRIX)


def short(cap_id: str) -> str:
    kind, name = cap_id.split(".", 1)
    return f"{kind[0]}.{name[:8]}"


def symbol(level: str) -> str:
    return {
        "aware": "A",
        "practitioner": "P",
        "expert": "E",
        "authority": "X",
    }[level]


def render_matrix(registry: dict, matrix: dict) -> str:
    capabilities = sorted((registry.get("capabilities") or {}).keys())
    header = "role".ljust(18) + " ".join(short(cap).rjust(8) for cap in capabilities)
    lines = [header]
    for role in sorted((matrix.get("roles") or {}).keys()):
        profile = matrix["roles"][role]
        default = profile.get("default_level", "aware")
        overrides = profile.get("capabilities") or {}
        cells = []
        for cap in capabilities:
            cells.append(symbol(overrides.get(cap, default)).rjust(8))
        lines.append(role.ljust(18) + " ".join(cells))
    return "\n".join(lines)


def render_role(registry: dict, matrix: dict, role: str, risk: str) -> str:
    profile = (matrix.get("roles") or {}).get(role)
    if not isinstance(profile, dict):
        raise ValueError(f"bilinmeyen rol: {role}")
    default = profile.get("default_level", "aware")
    overrides = profile.get("capabilities") or {}
    lines = [
        f"{role} ({profile.get('class', '?')}) — {profile.get('mission', '')}",
        f"default: {default} · risk: {risk}",
    ]
    for cap_id in sorted((registry.get("capabilities") or {}).keys()):
        capability = registry["capabilities"][cap_id]
        capability_roles = capability.get("roles") or {}
        if role not in capability_roles:
            continue
        level = overrides.get(cap_id, default)
        lines.append(
            f"  {cap_id.ljust(24)} {level.ljust(13)} -> "
            f"{effective_level(level, risk, registry, capability_roles[role])}"
        )
    lines.append("focus: " + ", ".join(profile.get("focus") or []))
    lines.append("evidence: " + ", ".join(profile.get("evidence") or []))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="capability registry")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--role")
    parser.add_argument("--capability")
    parser.add_argument("--risk", default="medium", choices=RISKS)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        registry, matrix = load()
    except ValueError as exc:
        sys.exit(f"capabilities: {exc}")

    if args.validate:
        registry_config = load_yaml(ROOT / "delivery" / "registry.yaml")
        roles = set(registry_config.get("role_order_default") or []) | {"orchestrator"}
        packs = {
            path.name
            for path in (ROOT / "delivery" / "packs").iterdir()
            if path.is_dir()
        }
        errors = validate_references(registry, matrix, roles, packs, roles)
        for message in errors:
            print(f"[fail] {message}")
        print(f"{len(errors)} hata")
        return 1 if errors else 0

    if args.json:
        data = {
            "registry": registry,
            "matrix": matrix,
        }
        if args.role:
            data["role"] = (matrix.get("roles") or {}).get(args.role)
        if args.capability:
            data["capability"] = (registry.get("capabilities") or {}).get(
                args.capability
            )
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.matrix:
        print(render_matrix(registry, matrix))
        return 0

    if args.role:
        try:
            print(render_role(registry, matrix, args.role, args.risk))
        except ValueError as exc:
            sys.exit(f"capabilities: {exc}")
        return 0

    if args.capability:
        cap = (registry.get("capabilities") or {}).get(args.capability)
        if not isinstance(cap, dict):
            sys.exit(f"capabilities: bilinmeyen capability {args.capability}")
        print(f"{args.capability} — {cap.get('label')}")
        print(f"kind: {cap.get('kind')} · risk: {cap.get('risk_floor')}")
        print(f"packs: {', '.join(cap.get('packs') or []) or '-'}")
        print(f"gates: {', '.join(cap.get('gates') or [])}")
        print(f"evidence: {', '.join(cap.get('evidence') or [])}")
        return 0

    for cap_id in sorted((registry.get("capabilities") or {}).keys()):
        cap = registry["capabilities"][cap_id]
        print(
            f"{cap_id.ljust(24)} {cap.get('kind','').ljust(12)} "
            f"{cap.get('risk_floor','').ljust(9)} {cap.get('label','')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
