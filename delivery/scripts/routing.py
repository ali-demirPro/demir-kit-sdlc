"""Path routing shared by the delivery brief and doctor."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

DEFAULT_PATH = "ui_feature"
NARROW_ORDER = (
    "store_release",
    "landing_only",
    "experiment",
    "ui_feature",
    "pure_technical",
    "full_product",
)
ENTRY_PATHS = {
    "chore": "pure_technical",
    "bugfix": "pure_technical",
    "feature": "ui_feature",
    "architecture_baseline": "full_product",
    "commercial_baseline": "full_product",
}
INACTIVE_REASONS = {
    "designer": "UI/UX kapsamda değil",
    "marketing/stores": "dağıtım kapsamda değil",
    "marketing/landing": "landing/SEO kapsamda değil",
    "growth/run": "experiment/rollout kapsamda değil",
    "devops": "altyapı/CI kapsamda değil",
    "architect": "boundary riski yok",
}


def load_registry(root: Path) -> dict:
    path = root / "delivery" / "registry.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def seal_body(body: str) -> dict:
    match = re.search(r"```yaml\s+demir-kit\s*\n(.*?)```", body, re.S)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def is_epic(body: str) -> bool:
    return bool(re.search(r"```yaml\s+demir-kit-epic\s*\n", body))


def all_agents(registry: dict) -> list[str]:
    return _dedupe(registry.get("role_order_default") or [])


def _intersects(left, right) -> bool:
    return bool(
        {str(item).lower() for item in left or []}
        & {str(item).lower() for item in right or []}
    )


def _keyword_hit(text: str, keyword: str) -> bool:
    return (
        re.search(
            r"(?<![A-Za-z0-9])" + re.escape(keyword) + r"(?![A-Za-z0-9])", text
        )
        is not None
    )


def detect_signal(registry: dict, seal: dict):
    factory = seal.get("factory") or {}
    surfaces = seal.get("surfaces") or []
    stacks = factory.get("stacks") or []
    distribution = factory.get("distribution") or []

    for signal in registry.get("signals") or []:
        if not isinstance(signal, dict):
            continue
        match = signal.get("match") or {}
        matched = False
        if match.get("surfaces") and surfaces:
            if not _intersects(surfaces, match["surfaces"]):
                continue
            matched = True
        if match.get("stacks") and stacks:
            if not _intersects(stacks, match["stacks"]):
                continue
            matched = True
        if match.get("distribution") and distribution:
            if not _intersects(distribution, match["distribution"]):
                continue
            matched = True
        if matched:
            return signal
    return None


def strip_seal(body: str) -> str:
    return re.sub(r"```yaml\s+demir-kit(?:-epic)?\s*\n.*?```", "", body, flags=re.S)


def detect_path(registry: dict, title: str, body: str, seal: dict | None = None):
    seal = seal_body(body) if seal is None else seal
    paths = registry.get("paths") or {}
    signal = detect_signal(registry, seal)
    if signal and signal.get("default_path") in paths:
        return signal["default_path"], signal

    text = f"{title}\n{strip_seal(body)}".lower()
    scores: dict[str, int] = {}
    for name, spec in paths.items():
        if not isinstance(spec, dict):
            continue
        keywords = [str(item).lower() for item in spec.get("keywords") or []]
        scores[name] = sum(1 for keyword in keywords if _keyword_hit(text, keyword))

    best = max(scores.values()) if scores else 0
    if best > 0:
        candidates = [name for name, score in scores.items() if score == best]
        for name in NARROW_ORDER:
            if name in candidates:
                return name, None
        return sorted(candidates)[0], None

    entry_kind = (seal.get("entry") or {}).get("kind")
    if entry_kind in ENTRY_PATHS and ENTRY_PATHS[entry_kind] in paths:
        return ENTRY_PATHS[entry_kind], None
    return DEFAULT_PATH, None


def resolve_agents(registry: dict, path_id: str, signal: dict | None = None) -> dict:
    paths = registry.get("paths") or {}
    spec = paths.get(path_id) if isinstance(paths, dict) else None
    spec = spec if isinstance(spec, dict) else {}

    active: list[str] = []
    on_demand: list[str] = []
    optional: list[str] = []

    if spec.get("extends"):
        base = resolve_agents(registry, spec["extends"], None)
        active.extend(base["active"])
        on_demand.extend(base["on_demand"])
        optional.extend(base["optional"])

    active.extend(spec.get("agents") or [])
    on_demand.extend(spec.get("on_demand") or [])
    active.extend(spec.get("agents_add") or [])

    if signal:
        signal_agents = signal.get("agents") or {}
        active.extend(signal_agents.get("required") or [])
        optional.extend(signal_agents.get("optional") or [])
        on_demand.extend(signal_agents.get("on_demand") or [])

    return {
        "active": _dedupe(active),
        "optional": [
            item for item in _dedupe(optional) if item not in active and item not in on_demand
        ],
        "on_demand": [item for item in _dedupe(on_demand) if item not in active],
    }


def inactive_agents(registry: dict, agents: dict) -> list[dict]:
    used = set(agents["active"]) | set(agents["optional"]) | set(agents["on_demand"])
    return [
        {
            "id": agent,
            "reason": INACTIVE_REASONS.get(agent, "bu path'te aktif değil"),
        }
        for agent in all_agents(registry)
        if agent not in used
    ]


def role_docs(role: str) -> list[str]:
    if role == "orchestrator":
        base = "delivery/orchestrator"
    else:
        base = f"delivery/agents/{role}"
    return [f"{base}/{name}" for name in ("ROLE.md", "how.md", "communicates.md", "dependencies.md", "SKILL.md")]


def next_action(labels: set[str], epic: bool) -> str:
    if "epic-done" in labels:
        return "no-op: epic kapandı"
    if "leaf-done" in labels:
        return "no-op: leaf kapandı; epic closure bekle"
    if "executing" in labels:
        return "resume: evidence'ları oku, pass olmayan CP'den devam et"
    if "agent-approved" in labels:
        return "health-check → next-leaf --claim → CP-1"
    if epic:
        return "orchestrator: plan + child leaf'leri mühürle"
    return "seal: work-package → doctor --body"


def human_gates(risk: str, epic: bool) -> list[str]:
    gates: list[str] = []
    if risk == "high":
        gates.append("leaf QA (high)")
    elif risk == "critical":
        gates.append("iki insan (critical)")
    if epic:
        gates.append("epic kabulü")
    gates.append("store submit / prod deploy / fiyat / yıkıcı migration (gerektiğinde)")
    return gates


def _dedupe(items) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
