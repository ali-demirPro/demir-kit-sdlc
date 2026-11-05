#!/usr/bin/env python3
"""Compose project profiles (base + overlays)."""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import risk_filter as risk_filter_lib  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROFILE_DIR = ROOT / "delivery" / "profiles"
REGISTRY = ROOT / "delivery" / "registry.yaml"
SELF = Path(__file__).resolve()

# Sözleşme üstverisi: hangi aşamaların çözümlendiğini listeler, çalışma
# sırası değildir. Gerçek akış risk_stage içinde yürütülür.
ORDER = ["base", "overlays", "packs", "risk_globs"]


def _lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def _scalar(text: str) -> str:
    """Satır içi yorum ve tırnakları temizle: `"x"  # not` -> `x`."""
    cleaned = text.strip()
    for quote in ('"', "'"):
        if cleaned.startswith(quote):
            end = cleaned.find(quote, 1)
            if end != -1:
                return cleaned[1:end]
            break
    if " #" in cleaned:
        cleaned = cleaned.split(" #", 1)[0]
    elif cleaned.startswith("#"):
        cleaned = ""
    return cleaned.strip()


def _source(path: Path, line: int | None, base: Path | None = None) -> str | None:
    """<göreli yol>:<satır>; kök dışındaysa None (mutlak yol yazmayız)."""
    if not line:
        return None
    anchor = (base or ROOT).resolve()
    try:
        relative = path.resolve().relative_to(anchor).as_posix()
    except (OSError, ValueError):
        return None
    return f"{relative}:{line}"


def yaml_entries(path: Path):
    """(line, key path, kind, text) for every key and list item."""
    stack: list[tuple[int, str]] = []
    for number, line in enumerate(_lines(path), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stripped.startswith("-"):
            yield number, tuple(name for _, name in stack), "item", _scalar(
                stripped[1:]
            )
            continue
        if ":" not in stripped:
            continue
        name, rest = stripped.split(":", 1)
        stack.append((indent, name.strip()))
        keys = tuple(key for _, key in stack)
        text = _scalar(rest)
        yield number, keys, "key", text
        if not text.startswith("["):
            continue
        for item in text[1:].split("]", 1)[0].split(","):
            item_text = _scalar(item)
            if item_text:
                yield number, keys, "item", item_text


def entry_line(
    path: Path, keys: tuple[str, ...], kind: str, value: str | None = None
) -> int | None:
    """Exact 1-based line for a key or list item under keys; None if absent."""
    for number, found, found_kind, text in yaml_entries(path):
        if found != keys or found_kind != kind:
            continue
        if value is None or text == value:
            return number
    return None


def item_source(path: Path, key: str, value: str) -> str | None:
    return _source(path, entry_line(path, (key,), "item", value))


def key_source(path: Path, *keys: str) -> str | None:
    return _source(path, entry_line(path, tuple(keys), "key"))


def function_source(func) -> str | None:
    try:
        _, start = inspect.getsourcelines(func)
    except (OSError, TypeError):
        return None
    return _source(SELF, start)


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def load_profile(name: str) -> dict:
    return load_yaml(PROFILE_DIR / f"{name}.yaml")


def platform_gate(profile: dict, project_data: dict | None = None) -> bool:
    """Tek kural: pack veya extra gate varsa platform gate açılır."""
    data = project_data or {}
    return bool(
        (profile or {}).get("platform_packs")
        or (profile or {}).get("extra_gates")
        or data.get("platform_packs")
    )


def gates_for(project: Path, seal_profile: str = "") -> dict:
    """Effective profile gates, aligned with doctor's needs_platform rule."""
    try:
        project_data = compose(project)
    except ValueError:
        project_data = {}
    data = load_profile(seal_profile) if seal_profile else project_data
    gates = {str(gate): True for gate in data.get("extra_gates") or []}
    if platform_gate(data, project_data):
        gates["platform"] = True
    return gates


def overlay_names() -> set[str]:
    return {
        path.stem
        for path in PROFILE_DIR.glob("*.yaml")
        if load_yaml(path).get("product_class") == "overlay"
    }


OVERLAYS = overlay_names()


def project_config(project: Path) -> dict:
    return load_yaml(project / "kit.config.yaml")


def explicit_profile_names(project: Path) -> list[str]:
    names = (project_config(project).get("factory") or {}).get("profiles")
    return [str(name) for name in names] if isinstance(names, list) else []


def profile_names(project: Path) -> list[str]:
    names = explicit_profile_names(project)
    if names:
        return names
    default = (project_config(project).get("factory") or {}).get("default_profile")
    return [str(default)] if default else []


def compose(project: Path) -> dict:
    names = profile_names(project)
    if not names:
        return {
            "profiles": [],
            "default": None,
            "base": [],
            "overlays": [],
            "capabilities": [],
            "platform_packs": [],
            "extra_gates": [],
            "required_skills": [],
            "architecture_baseline_required": False,
            "commercial_baseline_required": False,
        }
    config = project_config(project)
    factory = config.get("factory") or {}
    default = str(factory.get("default_profile") or names[0])
    capabilities: set[str] = set()
    packs: set[str] = set()
    extra: set[str] = set()
    skills: set[str] = set()
    architecture = False
    commercial = False
    for name in names:
        profile = load_profile(name)
        if not profile:
            raise ValueError(f"profil bulunamadı: {name}")
        capabilities.update(str(item) for item in profile.get("capabilities") or [])
        packs.update(str(item) for item in profile.get("platform_packs") or [])
        extra.update(str(item) for item in profile.get("extra_gates") or [])
        skills.update(str(item) for item in profile.get("required_skills") or [])
        architecture = architecture or bool(
            profile.get("architecture_baseline_required")
        )
        commercial = commercial or bool(profile.get("commercial_baseline_required"))
    return {
        "profiles": names,
        "default": default,
        "base": [name for name in names if name not in OVERLAYS],
        "overlays": [name for name in names if name in OVERLAYS],
        "capabilities": sorted(capabilities),
        "platform_packs": sorted(packs),
        "extra_gates": sorted(extra),
        "required_skills": sorted(skills),
        "architecture_baseline_required": architecture,
        "commercial_baseline_required": commercial,
    }


def ordered_names(names: list[str]) -> list[str]:
    """Aşama sırası: önce base, sonra overlay (her ikisi config sırasıyla)."""
    base = [name for name in names if name not in OVERLAYS]
    overlays = [name for name in names if name in OVERLAYS]
    return base + overlays


def _profile_source(name: str) -> str | None:
    return key_source(PROFILE_DIR / f"{name}.yaml", "id")


def _union(names: list[str], key: str) -> dict[str, str | None]:
    """value -> source for a list key, first profile in stage order wins."""
    found: dict[str, str | None] = {}
    for name in names:
        path = PROFILE_DIR / f"{name}.yaml"
        for item in load_profile(name).get(key) or []:
            value = str(item)
            if value not in found:
                found[value] = item_source(path, key, value)
    return found


def _flag(names: list[str], key: str) -> dict:
    for name in names:
        if load_profile(name).get(key):
            return {
                "value": True,
                "source": key_source(PROFILE_DIR / f"{name}.yaml", key),
            }
    for name in names:
        path = PROFILE_DIR / f"{name}.yaml"
        if key_source(path, key):
            return {"value": False, "source": key_source(path, key)}
    return {"value": False, "source": None}


def risk_stage(project: Path, paths: list[str] | None = None) -> dict:
    """registry + proje overlay risk glob'ları: eşleşme, seviye, insan kapısı."""
    registry = load_yaml(REGISTRY)
    overlay = risk_filter_lib.load_overlay(project)
    merged = risk_filter_lib.merge_risk(registry, overlay)
    risk = merged.get("risk") or {}
    exclude = [str(item) for item in risk.get("exclude") or []]
    kept = risk_filter_lib.filter_paths(paths or [], exclude)
    base = (registry.get("risk") or {}).get("auto_escalate") or {}
    overlay_path = project / ".kit" / "risk.yaml"
    matches: dict[str, str | None] = {}
    level_sources: dict[str, str | None] = {}
    escalate = risk.get("auto_escalate") or {}
    for name in [str(item) for item in risk.get("levels") or []] + [
        str(item) for item in escalate if str(item) not in (risk.get("levels") or [])
    ]:
        for pattern in escalate.get(name) or []:
            pattern = str(pattern)
            if not any(risk_filter_lib._matches(path, pattern) for path in kept):
                continue
            if pattern in [str(item) for item in base.get(name) or []]:
                source = _source(
                    REGISTRY,
                    entry_line(
                        REGISTRY, ("risk", "auto_escalate", name), "item", pattern
                    ),
                )
            else:
                source = _source(
                    overlay_path,
                    entry_line(
                        overlay_path, ("auto_escalate", name), "item", pattern
                    ),
                    project,
                )
            matches[f"{name}:{pattern}"] = source
            level_sources.setdefault(name, source)
    human = risk.get("human_gate") or {}
    level = risk_filter_lib.risk_for_paths(kept, merged) if paths else None
    if level == "none" and matches:
        # Bilinmeyen/ek seviyeler: registry.levels sırasıyla deterministik seç.
        order = [str(item) for item in risk.get("levels") or []]
        level = max(
            level_sources,
            key=lambda name: order.index(name) if name in order else -1,
        )
    level_source = None
    if level and level != "none":
        level_source = level_sources.get(level)
    gate = str(human.get(level)) if level in human else None
    gate_source = None
    if gate is not None:
        gate_source = _source(
            REGISTRY,
            entry_line(REGISTRY, ("risk", "human_gate", str(level)), "key", gate),
        )
    return {
        "level": level,
        "level_source": level_source,
        "origin": "match" if level_source else "derived",
        "matches": _items(matches),
        "human_gate": {"value": gate, "source": gate_source},
    }


def _items(found: dict[str, str | None]) -> list[dict]:
    return [{"value": value, "source": found[value]} for value in sorted(found)]


def resolve(project: Path, paths: list[str] | None = None) -> dict:
    """Composed profile plus the source of every value."""
    names = profile_names(project)
    for name in names:
        if not load_profile(name):
            raise ValueError(f"profil bulunamadı: {name}")
    ordered = ordered_names(names)
    config_path = project / "kit.config.yaml"
    factory = project_config(project).get("factory") or {}
    configured = factory.get("default_profile")
    default = str(configured or (names[0] if names else ""))
    default_source = None
    if configured:
        default_source = key_source(
            config_path, "factory", "default_profile"
        ) or key_source(config_path, "default_profile")
    overlays = {
        name: _profile_source(name) for name in names if name in OVERLAYS
    }
    packs = _union(ordered, "platform_packs")
    gates = _union(ordered, "extra_gates")
    if platform_gate({"platform_packs": packs, "extra_gates": gates}):
        gates["platform"] = function_source(platform_gate)
    return {
        "profile": {"value": default, "source": default_source},
        "profiles": _items({name: _profile_source(name) for name in names}),
        "overlays": _items(overlays),
        "packs": _items(packs),
        "gates": _items(gates),
        "capabilities": _items(_union(ordered, "capabilities")),
        "required_skills": _items(_union(ordered, "required_skills")),
        "architecture_baseline_required": _flag(
            ordered, "architecture_baseline_required"
        ),
        "commercial_baseline_required": _flag(
            ordered, "commercial_baseline_required"
        ),
        "risk": risk_stage(project, paths),
        "order": list(ORDER),
    }


def profile_capabilities(names: list[str]) -> list[str]:
    capabilities: set[str] = set()
    for name in names:
        profile = load_profile(name)
        capabilities.update(str(item) for item in profile.get("capabilities") or [])
    return sorted(capabilities)


def validate_project(project: Path, capability_ids: set[str], pack_names: set[str]) -> list[str]:
    errors: list[str] = []
    try:
        names = profile_names(project)
    except ValueError as exc:
        return [str(exc)]
    # Profil yapılandırması isteğe bağlıdır: eski ürünler profilsiz geçerli kalır.
    # Yapılandırıldıysa base/overlay ve referanslar doğrulanır.
    if not names:
        return []
    # 2.20 init bazı eski adlar yazdı (mobile-app, unknown). Açık
    # factory.profiles yoksa bilinmeyen tek default_profile uyumluluk için
    # sessizce atlanır; yeni profil listeleri sıkı doğrulanır.
    if not explicit_profile_names(project):
        known = [name for name in names if load_profile(name)]
        if not known:
            return []
        names = known
    if len(names) != len(set(names)):
        errors.append("factory.profiles tekrarlı")
    for name in names:
        profile = load_profile(name)
        if not profile:
            errors.append(f"profil yok: {name}")
            continue
        for cap_id in profile.get("capabilities") or []:
            if cap_id not in capability_ids:
                errors.append(f"{name}: bilinmeyen capability {cap_id}")
        for pack in profile.get("platform_packs") or []:
            if pack not in pack_names:
                errors.append(f"{name}: bilinmeyen pack {pack}")
    config = project_config(project)
    factory = config.get("factory") or {}
    default = str(factory.get("default_profile") or (names[0] if names else ""))
    if default not in names:
        errors.append(f"default_profile '{default}' factory.profiles içinde değil")
    base = [name for name in names if name not in OVERLAYS]
    if not base:
        errors.append("en az bir base profil gerekli")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="compose project profiles")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--resolve", action="store_true")
    parser.add_argument("--paths", action="append", default=[])
    args = parser.parse_args()
    paths = [
        item.strip()
        for chunk in args.paths
        for item in chunk.split(",")
        if item.strip()
    ]

    if args.check:
        registry = load_yaml(ROOT / "delivery" / "capabilities" / "registry.yaml")
        capabilities = set((registry.get("capabilities") or {}).keys())
        packs = {
            path.name
            for path in (ROOT / "delivery" / "packs").iterdir()
            if path.is_dir()
        }
        errors = validate_project(args.project, capabilities, packs)
        for message in errors:
            print(f"[fail] {message}")
        print(f"{len(errors)} hata")
        return 1 if errors else 0

    try:
        if args.resolve:
            print(
                json.dumps(
                    resolve(args.project, paths),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        data = compose(args.project)
    except ValueError as exc:
        sys.exit(f"profiles: {exc}")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("profiles: " + ", ".join(data["profiles"]))
        print("default: " + str(data["default"]))
        print("base: " + ", ".join(data["base"]))
        print("overlays: " + ", ".join(data["overlays"]))
        print("capabilities: " + ", ".join(data["capabilities"]))
        print("packs: " + ", ".join(data["platform_packs"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
