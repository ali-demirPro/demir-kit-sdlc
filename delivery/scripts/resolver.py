#!/usr/bin/env python3
"""Resolve project capabilities, roles and variant docs."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "delivery" / "agents"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import profiles  # noqa: E402
import rigor as rigor_lib  # noqa: E402
import routing  # noqa: E402

LOCAL_OVERRIDES = ROOT / "delivery" / "local-overrides.yaml"
LOCAL_FILE = ".kit/local.yaml"

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


FALLBACKS: list[str] = []


def note_fallback(reason: str) -> None:
    FALLBACKS.append(reason)


def fallbacks() -> list[str]:
    return list(FALLBACKS)


def reset_fallbacks() -> None:
    FALLBACKS.clear()


def load_yaml(path: Path) -> dict:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        note_fallback(f"yaml {path}")
        return {}
    if not isinstance(data, dict) or not data:
        note_fallback(f"yaml {path}")
        return {}
    return data


def load_capabilities() -> dict:
    return load_yaml(ROOT / "delivery" / "capabilities" / "registry.yaml")


def load_matrix() -> dict:
    return load_yaml(ROOT / "delivery" / "capabilities" / "role-matrix.yaml")


def load_local_policy() -> dict:
    """`.kit/local.yaml` beyaz listesi — tek kaynak `delivery/local-overrides.yaml`."""
    data = load_yaml(LOCAL_OVERRIDES)
    return {
        "version": data.get("version", 1),
        "read": [str(item) for item in data.get("read") or []],
        "write": [str(item) for item in data.get("write") or []],
        "values": data.get("values") if isinstance(data.get("values"), dict) else {},
        "locked": [str(item) for item in data.get("locked") or []],
        "reasons": data.get("reasons") if isinstance(data.get("reasons"), dict) else {},
    }


def _flatten_local(data: dict, prefix: str = "") -> dict:
    """Nested veya noktalı anahtarları tek düzlemde topla."""
    flat: dict = {}
    for key, value in data.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten_local(value, name + "."))
        else:
            flat[name] = value
    return flat


def locked_reason(
    key: str, policy: dict | None = None, required: tuple[str, ...] | list[str] = ()
) -> str | None:
    """Kilitli anahtar gerekçesi; nested alt-anahtar da kilitlidir.

    Tam eşleşme, `fnmatch` globu veya `pattern + "."` ile başlayan alt-anahtar
    kilitli sayılır: `risk.auto_escalate` iken `risk.auto_escalate.high` de
    kişisel dosyaya açılmaz. `required` daima kilitli kabul edilir; politika
    dosyası tek başına zorunlu anahtarı kaldıramaz.
    """
    policy = policy if policy is not None else load_local_policy()
    locked = [str(item) for item in policy.get("locked") or []]
    locked += [str(item) for item in required if str(item) not in locked]
    reasons = policy.get("reasons") or {}
    for pattern in locked:
        if (
            key == pattern
            or fnmatch.fnmatchcase(key, pattern)
            or key.startswith(pattern + ".")
        ):
            reason = reasons.get(pattern)
            return str(reason or "kilitli anahtar")
    return None


def _locked_reason(key: str, policy: dict) -> str | None:
    """Geriye dönük iç ad: `locked_reason` ile aynı semantik."""
    return locked_reason(key, policy)


def load_local(project: Path) -> dict:
    """Beyaz listedeki `.kit/local.yaml` değerlerini oku; kilitli olanı uyar.

    Dönen sözlük `{values, sources, warnings}`: yalnız `read` listesindeki ve
    geçerli değerler uygulanır. Kilitli, liste dışı veya geçersiz anahtar
    sessizce yutulmaz — her biri gerekçeli `uyarı:` satırı üretir.
    """
    result: dict = {"values": {}, "sources": {}, "warnings": []}
    path = Path(project) / LOCAL_FILE
    if not path.is_file():
        return result
    policy = load_local_policy()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        result["warnings"].append(f"uyarı: {LOCAL_FILE}: okunamadı — {exc}")
        return result
    if not isinstance(data, dict):
        result["warnings"].append(f"uyarı: {LOCAL_FILE}: kök mapping değil")
        return result
    read = set(policy.get("read") or [])
    values_spec = policy.get("values") or {}
    for key, value in _flatten_local(data).items():
        reason = _locked_reason(key, policy)
        if reason is not None:
            result["warnings"].append(
                f"uyarı: {LOCAL_FILE}: '{key}' kilitli — {reason}"
            )
            continue
        if key not in read:
            result["warnings"].append(
                f"uyarı: {LOCAL_FILE}: '{key}' beyaz listede değil"
            )
            continue
        allowed = values_spec.get(key)
        if isinstance(allowed, list) and str(value) not in [
            str(item) for item in allowed
        ]:
            result["warnings"].append(
                f"uyarı: {LOCAL_FILE}: '{key}' geçersiz — beklenen: "
                + ", ".join(str(item) for item in allowed)
            )
            continue
        result["values"][key] = value
        result["sources"][key] = LOCAL_FILE
    return result


def effective_docs_density(project: Path | None, local: dict) -> dict:
    """Etkin doküman derinliği: kişisel override varsa o, yoksa rigor kaynağı.

    Kişisel değer yoksa kaynak uydurulmaz: değer `kit.config.yaml` içinden
    geldiyse `kit.config.yaml`, rigor seviyesinden türetildiyse `rigor:<level>`.
    Geçersiz `process.rigor` gibi bir hata kanonik tabloya düşürür; bu düşüş
    sessiz olmaz: `source` `fallback` olur ve `warning` rigor hatasını taşır.
    """
    if "docs.density" in (local.get("values") or {}):
        return {
            "value": local["values"]["docs.density"],
            "source": local["sources"]["docs.density"],
        }
    try:
        knob = rigor_lib.load_effective(project)["knobs"]["docs.density"]
        return {"value": knob["value"], "source": knob["source"]}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        fallback = rigor_lib.fallback_effective()
        knob = fallback["knobs"]["docs.density"]
        return {
            "value": knob["value"],
            "source": "fallback",
            "warning": (
                f"rigor yapılandırması okunamadı — {exc} "
                f"(fallback: rigor:{fallback['level']})"
            ),
        }



def declared_path(project: Path) -> Path:
    return project / ".kit" / "capabilities.yaml"


def load_declared(project: Path, include_profiles: bool = True) -> dict:
    path = declared_path(project)
    data = load_yaml(path) if path.is_file() else {}
    include = data.get("include") if isinstance(data.get("include"), list) else []
    exclude = data.get("exclude") if isinstance(data.get("exclude"), list) else []
    profile_caps: list[str] = []
    if include_profiles:
        try:
            profile_caps = profiles.compose(project).get("capabilities") or []
        except ValueError as exc:
            note_fallback(f"profiles compose ({exc})")
            profile_caps = []
    return {
        "version": data.get("version", 1),
        "include": sorted(
            set(str(item) for item in include) | set(str(item) for item in profile_caps)
        ),
        "exclude": [str(item) for item in exclude],
    }


def apply_declared(capabilities: dict, registry: dict, declared: dict | None) -> dict:
    if not declared:
        return capabilities
    result = dict(capabilities)
    available = registry.get("capabilities") or {}
    for cap_id in declared.get("include") or []:
        if cap_id in available:
            result[cap_id] = available[cap_id]
    for cap_id in declared.get("exclude") or []:
        result.pop(cap_id, None)
    return result


def load_agent_variants() -> dict[str, dict]:
    variants: dict[str, dict] = {}
    for directory in AGENTS.rglob("agent.yaml"):
        role = str(directory.parent.relative_to(AGENTS))
        data = load_yaml(directory)
        if data:
            variants[role] = data
    return variants


def project_signals(ecosystem: dict | None) -> list[dict]:
    signals: list[dict] = []
    for product in ((ecosystem or {}).get("products") or {}).values():
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


def _surface_match(left: str, right: str) -> bool:
    left = left.lower()
    right = right.lower()
    return (
        left == right
        or left.startswith(right + ".")
        or right.startswith(left + ".")
    )


def scoped_signals(ecosystem: dict, seal: dict) -> list[dict]:
    """Merge project surface metadata into the leaf's sealed surfaces."""
    project = project_signals(ecosystem)
    sealed = seal_signals(seal)
    if not sealed:
        return project
    result: list[dict] = []
    for signal in sealed:
        matched = [
            item
            for item in project
            if any(
                _surface_match(surface, name)
                for surface in signal["surfaces"]
                for name in item["surfaces"]
            )
        ]
        if not matched:
            result.append(signal)
            continue
        for item in matched:
            result.append(
                {
                    "name": signal["name"],
                    "surfaces": list(
                        dict.fromkeys(signal["surfaces"] + item["surfaces"])
                    ),
                    "platforms": list(
                        dict.fromkeys(item["platforms"] + signal["platforms"])
                    ),
                    "stacks": list(dict.fromkeys(item["stacks"] + signal["stacks"])),
                    "distribution": list(
                        dict.fromkeys(item["distribution"] + signal["distribution"])
                    ),
                }
            )
    return result


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


GENERIC_KEYWORDS = {"oturum", "session", "checkout", "izin", "şema", "schema", "tablo"}


def match_capabilities(
    registry: dict,
    signals: list[dict],
    text: str = "",
    allow_keywords: bool = True,
) -> dict:
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
            if not hit and allow_keywords:
                hit = any(
                    _keyword_hit(lowered, str(keyword).lower())
                    for keyword in match.get("keywords") or []
                    if str(keyword).lower() not in GENERIC_KEYWORDS
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
    declared: dict | None = None,
    allow_keywords: bool = True,
    project: Path | None = None,
) -> dict:
    delivery = delivery_registry or load_yaml(ROOT / "delivery" / "registry.yaml")
    path_agents = routing.resolve_agents(delivery, path_id)
    capabilities = match_capabilities(registry, signals, text, allow_keywords=allow_keywords)
    capabilities = apply_declared(capabilities, registry, declared)
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

    local = load_local(project or ROOT)
    # `docs` anahtarı doküman yolu listesidir; etkin derinlik çakışmasın diye
    # kişisel blok içinde `docs: {density: {value, source}}` olarak taşınır.
    local["docs"] = {"density": effective_docs_density(project, local)}

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
        "local": local,
        "status": "ready" if not variant_gaps else "gaps",
        "matrix": matrix,
    }


def set_local(project: Path, assignment: str) -> int:
    """`KEY=VALUE` yalnız `write` listesindeki anahtara yazılır.

    Kilitli veya izin dışı anahtar gerekçeli hata ile reddedilir (exit 2);
    geçerli değer mevcut `.kit/local.yaml` değerlerini koruyarak yazılır.
    """
    if "=" not in assignment:
        print("hata: --set-local KEY=VALUE biçiminde olmalı", file=sys.stderr)
        return 2
    key, value = assignment.split("=", 1)
    key = key.strip()
    value = value.strip()
    policy = load_local_policy()
    reason = _locked_reason(key, policy)
    if reason is not None:
        print(f"hata: '{key}' kilitli — {reason}", file=sys.stderr)
        return 2
    if key not in set(policy.get("write") or []):
        print(
            f"hata: '{key}' yazma beyaz listesinde değil — izinli: "
            + (", ".join(policy.get("write") or []) or "-"),
            file=sys.stderr,
        )
        return 2
    allowed = (policy.get("values") or {}).get(key)
    if isinstance(allowed, list) and value not in [str(item) for item in allowed]:
        print(
            f"hata: '{key}' geçersiz — beklenen: "
            + ", ".join(str(item) for item in allowed),
            file=sys.stderr,
        )
        return 2

    path = Path(project) / LOCAL_FILE
    existing: dict = {}
    if path.is_file():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            print(f"hata: {LOCAL_FILE} okunamadı — {exc}", file=sys.stderr)
            return 2
        if not isinstance(loaded, dict):
            print(f"hata: {LOCAL_FILE} kök mapping değil", file=sys.stderr)
            return 2
        existing = loaded
    flat = _flatten_local(existing)
    flat[key] = value
    data: dict = {}
    for name, item in flat.items():
        node = data
        parts = name.split(".")
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        node[parts[-1]] = item
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"[ok] {LOCAL_FILE}: {key}={value}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="resolve project capabilities")
    parser.add_argument("--path", default="full_product")
    parser.add_argument("--surface", action="append", default=[])
    parser.add_argument("--platform", action="append", default=[])
    parser.add_argument("--stack", action="append", default=[])
    parser.add_argument("--distribution", action="append", default=[])
    parser.add_argument("--text", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--project", type=Path, default=ROOT, help=".kit/local.yaml kökü")
    parser.add_argument(
        "--set-local",
        metavar="KEY=VALUE",
        help="kişisel beyaz listedeki anahtarı .kit/local.yaml'a yaz",
    )
    args = parser.parse_args()

    if args.set_local:
        return set_local(args.project, args.set_local)

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
        project=args.project,
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
        density = data["local"]["docs"]["density"]
        print(f"docs.density: {density['value']} ({density['source']})")
        for line in data["local"]["warnings"]:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
