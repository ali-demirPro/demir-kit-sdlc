#!/usr/bin/env python3
"""Proje ve epic durumunu salt-okunur özetleyen CLI.

Sözleşme alanları:
- `source`: "live" taze hesaplandı, "cache" önbellekten okundu.
- `stale`: yalnızca kit kökü çözülemediğinde true (durum eksik).
- `kit.dirty`: git durumu okunamazsa null (bilinmiyor), true/false değil.

CP-1 kapsamı sözleşme iskeletidir: `kit` ve `project` alanları
`kit.config.yaml`, `ecosystem.yaml`, `VERSION` ve git'ten doldurulur; `epics`
sonraki checkpoint'lerde toplanır. Ağ çağrısı yapılmaz.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

CONTRACT_VERSION = 1
CONFIG_NAME = "kit.config.yaml"
KIT_MARKER = Path("delivery") / "scripts" / "doctor.py"
CONTRACT_KEYS = {
    "contract_version",
    "generated_at",
    "stale",
    "source",
    "kit",
    "project",
    "epics",
    "counts",
    "warnings",
}


class StatusError(Exception):
    """Kullanıcıya kısa mesajla anlatılacak durum hatası."""


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def section(config: dict, key: str) -> dict:
    value = config.get(key)
    return value if isinstance(value, dict) else {}


def git(root: Path, *args: str) -> str | None:
    """Git çıktısı; git yoksa ya da komut başarısızsa None."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def find_kit_root(start: Path) -> Path | None:
    """En yakın kit kökü: içinde delivery/scripts/doctor.py olan dizin."""
    for candidate in (start, *start.parents):
        if (candidate / KIT_MARKER).is_file():
            return candidate
    return None


def resolve_project(explicit: Path | None, cwd: Path) -> Path:
    """--project → o dizin; yoksa cwd'de kit.config.yaml; yoksa kit kökü."""
    if explicit is not None:
        candidate = explicit.expanduser().resolve()
        if not candidate.is_dir():
            raise StatusError(f"proje dizini yok: {candidate}")
        return candidate
    cwd = cwd.expanduser().resolve()
    if (cwd / CONFIG_NAME).is_file():
        return cwd
    root = find_kit_root(cwd)
    if root is not None:
        return root
    raise StatusError(
        "proje bulunamadı: --project verin ya da kit.config.yaml olan bir dizinde çalışın"
    )


def load_config(project: Path) -> dict:
    path = project / CONFIG_NAME
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise StatusError(f"{CONFIG_NAME} okunamadı: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise StatusError(f"{CONFIG_NAME} bir eşleme olmalı: {path}")
    return data


def kit_state(kit_root: Path | None, config: dict, warnings: list[str]) -> dict:
    if kit_root is None:
        warnings.append("kit kökü bulunamadı: delivery/scripts/doctor.py yok")
        return {"version": "", "pin": None, "dirty": None}
    version = read_text(kit_root / "VERSION") or str(section(config, "kit").get("version") or "")
    if not version:
        warnings.append("kit sürümü okunamadı: VERSION yok")
    pin = git(kit_root, "rev-parse", "--short", "HEAD")
    if pin is None:
        warnings.append("git durumu okunamadı: kit kökü bir git deposu değil")
    porcelain = git(kit_root, "status", "--porcelain")
    if porcelain is None:
        dirty: bool | None = None
        if pin is not None:
            warnings.append("git durumu okunamadı: dirty bilinmiyor")
    else:
        dirty = bool(porcelain)
    return {"version": version, "pin": pin, "dirty": dirty}


def project_state(project: Path, config: dict) -> dict:
    meta = section(config, "project")
    name = str(meta.get("name") or config.get("name") or "")
    if not name:
        ecosystem = project / "ecosystem.yaml"
        try:
            data = yaml.safe_load(ecosystem.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            data = {}
        name = str((data or {}).get("name") or "") if isinstance(data, dict) else ""
    name = name or project.name
    profile = str(meta.get("profile") or section(config, "factory").get("default_profile") or "")
    tracker = section(config, "tracker")
    return {
        "name": name,
        "profile": profile,
        "tracker": {
            "provider": str(tracker.get("provider") or ""),
            "repo": str(tracker.get("repo") or ""),
        },
    }


def build_status(project: Path, args: argparse.Namespace) -> dict:
    warnings: list[str] = []
    config = load_config(project)
    if not (project / CONFIG_NAME).is_file():
        warnings.append(f"{CONFIG_NAME} yok: {project}")
    kit_root = find_kit_root(project)
    kit = kit_state(kit_root, config, warnings)
    epics: list[dict] = []
    counts = {"epics": len(epics), "leaves": 0, "blocked": 0}
    if args.with_gate:
        warnings.append("--with-gate: gate verisi bu checkpoint'te toplanmıyor")
    if args.with_cost:
        warnings.append("--with-cost: maliyet verisi bu checkpoint'te toplanmıyor")
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "stale": kit_root is None,
        "source": "live",
        "kit": kit,
        "project": project_state(project, config),
        "epics": epics,
        "counts": counts,
        "warnings": warnings,
    }


def cache_path(project: Path) -> Path:
    return project / ".orchestration" / "status-cache.json"


def valid_contract(data: object) -> bool:
    if not isinstance(data, dict) or set(data) != CONTRACT_KEYS:
        return False
    if data.get("contract_version") != CONTRACT_VERSION:
        return False
    if not isinstance(data.get("generated_at"), str):
        return False
    if not isinstance(data.get("stale"), bool):
        return False
    if data.get("source") not in {"live", "cache"}:
        return False
    kit = data.get("kit")
    if not isinstance(kit, dict) or set(kit) != {"version", "pin", "dirty"}:
        return False
    if not isinstance(kit.get("version"), str):
        return False
    if kit.get("pin") is not None and not isinstance(kit.get("pin"), str):
        return False
    if not isinstance(kit.get("dirty"), (bool, type(None))):
        return False
    project = data.get("project")
    if not isinstance(project, dict) or set(project) != {"name", "profile", "tracker"}:
        return False
    if not all(isinstance(project.get(key), str) for key in ("name", "profile")):
        return False
    tracker = project.get("tracker")
    if not isinstance(tracker, dict) or set(tracker) != {"provider", "repo"}:
        return False
    if not all(isinstance(tracker.get(key), str) for key in ("provider", "repo")):
        return False
    if not isinstance(data.get("epics"), list):
        return False
    counts = data.get("counts")
    if not isinstance(counts, dict) or set(counts) != {"epics", "leaves", "blocked"}:
        return False
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in counts.values()):
        return False
    warnings = data.get("warnings")
    return isinstance(warnings, list) and all(isinstance(item, str) for item in warnings)


def args_fingerprint(args: argparse.Namespace) -> dict:
    return {
        "with_gate": bool(args.with_gate),
        "with_cost": bool(args.with_cost),
        "full": bool(args.full),
    }


def read_cache(project: Path, ttl: int, fingerprint: dict) -> tuple[dict | None, int]:
    """Geçerli önbellek ve yaşı; bozuk/eski/başka argümanlar için (None, 0)."""
    path = cache_path(project)
    try:
        age = int(time.time() - path.stat().st_mtime)
    except OSError:
        return None, 0
    if age > ttl:
        return None, 0
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, 0
    if not isinstance(envelope, dict) or envelope.get("args") != fingerprint:
        return None, 0
    data = envelope.get("data")
    if not valid_contract(data):
        return None, 0
    return data, max(0, age)


def write_cache(project: Path, data: dict, fingerprint: dict) -> None:
    path = cache_path(project)
    envelope = {
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "args": fingerprint,
        "data": data,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def render(data: dict) -> str:
    kit = data["kit"]
    project = data["project"]
    tracker = project["tracker"]
    tracker_text = " · ".join(item for item in (tracker["provider"], tracker["repo"]) if item) or "-"
    counts = data["counts"]
    dirty_text = {True: "kirli", False: "temiz", None: "bilinmiyor"}[kit["dirty"]]
    lines = [
        f"proje: {project['name']} · profil {project['profile'] or '-'} · {tracker_text}",
        f"kit: {kit['version'] or '-'} @{kit['pin'] or '-'} ({dirty_text})",
        f"epic: {counts['epics']} · leaf: {counts['leaves']} · engel: {counts['blocked']}",
    ]
    for epic in data["epics"]:
        lines.append(f"epic {epic.get('number', '?')}: {epic.get('state', '-')}")
    for warning in data["warnings"]:
        lines.append(f"[uyarı] {warning}")
    if data["stale"]:
        lines.append("[uyarı] kit kökü yok — durum eksik")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="proje ve epic durumu (salt-okunur)")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--offline", action="store_true", help="kabul edilir; ağ çağrısı yok")
    parser.add_argument("--with-gate", action="store_true")
    parser.add_argument("--with-cost", action="store_true")
    parser.add_argument("--cache-ttl", type=int, default=0, metavar="N")
    parser.add_argument("--full", action="store_true", help="rezerve (CP-2)")
    args = parser.parse_args()
    if args.cache_ttl < 0:
        print("status: --cache-ttl negatif; 0 kullanıldı", file=sys.stderr)
    args.cache_ttl = max(0, args.cache_ttl)

    try:
        project = resolve_project(args.project, Path.cwd())
    except StatusError as exc:
        print(f"status: {exc}", file=sys.stderr)
        return 1

    fingerprint = args_fingerprint(args)
    cached, age = (
        read_cache(project, args.cache_ttl, fingerprint) if args.cache_ttl > 0 else (None, 0)
    )
    if cached is not None:
        data = dict(cached)
        data["source"] = "cache"
        data["warnings"] = [
            *(data.get("warnings") or []),
            f"önbellekten okundu: {age}s",
        ]
    else:
        try:
            data = build_status(project, args)
        except StatusError as exc:
            print(f"status: {exc}", file=sys.stderr)
            return 1
        if args.cache_ttl > 0:
            write_cache(project, data, fingerprint)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
