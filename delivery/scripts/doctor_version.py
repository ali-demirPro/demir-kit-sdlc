#!/usr/bin/env python3
"""doctor: sürüm başlığı hizası (VERSION ↔ kit.config / AGENTS / CHANGELOG).

doctor.py satır bütçesini korumak için ayrı modülde; rapor fonksiyonları
çağıran taraftan geçirilir (doctor.py betik olarak da çalışır).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

Error = Callable[[str], None]
LoadYaml = Callable[[Path], object]


def check_version_drift(
    root: Path, version: str, error: Error, warn: Error, load_yaml: LoadYaml
) -> None:
    """kit.config.yaml ve AGENTS.md başlıkları VERSION ile hizalı olmalı."""
    config_path = root / "kit.config.yaml"
    if config_path.is_file():
        config = load_yaml(config_path)
        config = config if isinstance(config, dict) else {}
        configured = str(((config.get("kit") or {}).get("version")) or "")
        if not configured:
            warn("kit.config.yaml: kit.version yok")
        elif configured != version:
            error(f"kit.config.yaml: kit.version '{configured}' ≠ VERSION ({version})")
    agents = root / "AGENTS.md"
    short = ".".join(version.split(".")[:2])
    if agents.is_file() and f"demir-kit {short}" not in agents.read_text(
        encoding="utf-8"
    ):
        warn(f"AGENTS.md sürüm başlığı 'demir-kit {short}' değil")
    changelog = root / "CHANGELOG.md"
    if changelog.is_file():
        first = re.search(
            r"^## .*?(\d+\.\d+\.\d+)\b", changelog.read_text(encoding="utf-8"), re.M
        )
        if not first:
            warn("CHANGELOG.md: sürüm başlığı bulunamadı")
        elif first.group(1) != version:
            error(
                f"CHANGELOG.md: ilk sürüm başlığı {first.group(1)}"
                f" ≠ VERSION ({version})"
            )
