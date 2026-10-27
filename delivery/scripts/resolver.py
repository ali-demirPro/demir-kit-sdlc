#!/usr/bin/env python3
"""Resolve project capabilities, roles and variant docs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "delivery" / "agents"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import routing  # noqa: E402

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
CORE_ROLES = {"analist", "developer", "tester", "devops", "documenter"}
CONDITIONAL_ROLES = {
    "marketing/stores",
    "marketing/landing",
    "growth/run",
    "security",
    "data",
    "release",
}


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def load_capabilities() -> dict:
    return load_yaml(ROOT / "delivery" / "capabilities" / "registry.yaml")


def load_matrix() -> dict:
    return load_yaml(ROOT / "delivery" / "capabilities" / "role-matrix.yaml")


def load_agent_variants() -> dict[str, dict]:
    variants: dict[str, dict] = {}
    for directory in AGENTS.rglob("agent.yaml"):
        role = str(directory.parent.relative_to(AGENTS))
        data = load_yaml(directory)
        if data:
            variants[role] = data
    return variants


def project_signals(ecosystem: dict) -> list[dict]:
    signals: list[dict] = []
    for product in (ecosystem.get("products") or {}).values():
        for name, spec in (product.get("surfaces") or {}).items():
            spec = spec if isinstance(spec, dict) else {}
            surfaces = [name]
            surfaces += [str(item) for item in spec.get("surfaces") or []]
            signals.append(
                {
                    "name": name,
                    "surfaces": surfaces,
                    "platforms": spec.get("platforms") or [],
                    "stacks": spec.get("stacks") or [],
                    "distribution": spec.get("distribution") or [],
                }
            )
    return signals


def seal_signals(seal: dict) -> list[dict]:
    factory = seal.get("factory") or {}
    return [
        {
            "name": str(surface),
            "surfaces": [str(surface)],
            "platforms": [],
            "stacks": factory.get("stacks") or [],
            "distribution": factory.get("distribution") or [],
        }
        for surface in seal.get("surfaces") or []
    ]


def _intersects(left, right) -> bool:
    return bool(
        {str(item).lower() for item in left or []}
        & {str(item).lower() for item in right or []}
    )


def _keyword_hit(text: str, keyword: str) -> bool:
    import re

    return (
        re.search(
            r"(?<![A-Za-z0-9])" + re.escape(keyword) + r"(?![A-Za-z0-9])", text
        )
        is not None
    )


def match_capabilities(registry: dict, signals: list[dict], text: str = "") -> dict:
    matched: dict[str, dict] = {}
    lowered = text.lower()
    for cap_id, capability in (registry.get("capabilities") or {}).items():
        match = capability.get("match") or {}
        kind = capability.get("kind")
        hit = False
        if kind == "distribution":
            # Distribution is explicit; a surface alone does not imply a store.
            hit = any(
                _intersects(match.get("distribution"), signal.get("distribution"))
                for signal in signals
            )
        elif kind == "platform":
            # Platform must be identified by platform or surface, not by a shared
            # language stack (python/node) or prose.
            hit = any(
                _intersects(match.get("platforms"), signal.get("platforms"))
                or _intersects(match.get("surfaces"), signal.get("surfaces"))
                for signal in signals
            )
        else:
            for signal in signals:
                for key in ("platforms", "stacks", "surfaces", "distribution"):
                    if _intersects(match.get(key), signal.get(key)):
                        hit = True
                        break
                if hit:
                    break
            if not hit:
                hit = any(
                    _keyword_hit(lowered, str(keyword).lower())
                    for keyword in match.get("keywords") or []
                )
        if hit:
            matched[cap_id] = capability
    return matched


def resolve(
    registry: dict,
    matrix: dict,
    variants: dict[str, dict],
    path_id: str,
    signals: list[dict],
    text: str = "",
    delivery_registry: dict | None = None,
) -> dict:
    delivery = delivery_registry or load_yaml(ROOT / "delivery" / "registry.yaml")
    path_agents = routing.resolve_agents(delivery, path_id)
    capabilities = match_capabilities(registry, signals, text)
    capability_roles: set[str] = set()
    for capability in capabilities.values():
        capability_roles.update((capability.get("roles") or {}).keys())
    path_active = set(path_agents["active"])
    base_roles = (path_active - CONDITIONAL_ROLES) | capability_roles
    active_roles = base_roles
    on_demand_roles = [
        role for role in path_agents["on_demand"] if role not in active_roles
    ]
    all_roles = set(delivery.get("role_order_default") or []) | {"orchestrator"}

    active_variants: list[dict] = []
    variant_gaps: list[dict] = []
    for cap_id, capability in capabilities.items():
        for role in (capability.get("roles") or {}).keys():
            if role not in active_roles:
                continue
            spec = (variants.get(role) or {}).get("variants", {}).get(cap_id)
            if spec:
                active_variants.append(
                    {
                        "role": role,
                        "capability": cap_id,
                        "doc": spec.get("doc"),
                        "eval": spec.get("eval"),
                        "min_level": spec.get("min_level"),
                    }
                )
            elif role in variants:
                variant_gaps.append(
                    {
                        "role": role,
                        "capability": cap_id,
                        "reason": "rol aktif ama variant tanımlı değil",
                    }
                )

    inactive_variants: list[dict] = []
    if capabilities:
        for role, agent in variants.items():
            if role not in active_roles:
                continue
            for cap_id in (agent.get("variants") or {}).keys():
                capability = (registry.get("capabilities") or {}).get(cap_id) or {}
                if (
                    cap_id not in capabilities
                    and capability.get("kind") == "platform"
                ):
                    inactive_variants.append(
                        {
                            "role": role,
                            "capability": cap_id,
                            "reason": "platform capability pasif",
                        }
                    )

    docs: list[str] = []
    for role in sorted(active_roles):
        for doc in routing.role_docs(role):
            if doc not in docs:
                docs.append(doc)
    for item in active_variants:
        doc = f"delivery/agents/{item['role']}/{item['doc']}"
        if doc not in docs:
            docs.append(doc)

    risk_floor = "low"
    for capability in capabilities.values():
        level = capability.get("risk_floor") or "low"
        if RISK_ORDER.get(level, 0) > RISK_ORDER.get(risk_floor, 0):
            risk_floor = level

    return {
        "path_id": path_id,
        "capabilities": sorted(capabilities),
        "active_roles": sorted(active_roles),
        "on_demand_roles": on_demand_roles,
        "inactive_roles": sorted(all_roles - active_roles - set(on_demand_roles)),
        "active_variants": active_variants,
        "inactive_variants": inactive_variants,
        "variant_gaps": variant_gaps,
        "risk_floor": risk_floor,
        "docs": docs,
        "status": "ready" if not variant_gaps else "gaps",
        "matrix": matrix,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="resolve project capabilities")
    parser.add_argument("--path", default="full_product")
    parser.add_argument("--surface", action="append", default=[])
    parser.add_argument("--platform", action="append", default=[])
    parser.add_argument("--stack", action="append", default=[])
    parser.add_argument("--distribution", action="append", default=[])
    parser.add_argument("--text", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    signals = [
        {
            "name": surface,
            "surfaces": [surface],
            "platforms": args.platform,
            "stacks": args.stack,
            "distribution": args.distribution,
        }
        for surface in args.surface
    ] or [
        {
            "name": "cli",
            "surfaces": [],
            "platforms": args.platform,
            "stacks": args.stack,
            "distribution": args.distribution,
        }
    ]
    data = resolve(
        load_capabilities(),
        load_matrix(),
        load_agent_variants(),
        args.path,
        signals,
        args.text,
    )
    data.pop("matrix", None)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("capabilities: " + (", ".join(data["capabilities"]) or "-"))
        print("active roles: " + ", ".join(data["active_roles"]))
        print("active variants: " + str(len(data["active_variants"])))
        print("gaps: " + str(len(data["variant_gaps"])))
        print("docs:")
        for doc in data["docs"]:
            print(f"  - {doc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
