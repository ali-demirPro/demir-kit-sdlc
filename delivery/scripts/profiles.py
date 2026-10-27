#!/usr/bin/env python3
"""Compose project profiles (base + overlays)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROFILE_DIR = ROOT / "delivery" / "profiles"
OVERLAYS = {
    "auth",
    "payments",
    "offline",
    "multi-tenant",
    "regulated",
    "high-scale",
}


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def load_profile(name: str) -> dict:
    return load_yaml(PROFILE_DIR / f"{name}.yaml")


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
    args = parser.parse_args()

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
