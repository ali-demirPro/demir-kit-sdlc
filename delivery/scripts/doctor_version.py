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


VERSION_HEADING = re.compile(r"^##\s+(\d+\.\d+\.\d+)\b", re.M)


def check_changelog(
    root: Path, version: str, error: Error, warn: Error
) -> None:
    """CHANGELOG sözleşmesi: tek `# Changelog` en üstte, sürüm başlıkları
    benzersiz ve azalan sırada, ilki VERSION ile aynı."""
    path = root / "CHANGELOG.md"
    if not path.is_file():
        error("CHANGELOG.md yok")
        return
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    header_lines = [
        n for n, line in enumerate(lines) if line.strip() == "# Changelog"
    ]
    if not header_lines:
        error("CHANGELOG.md: `# Changelog` başlığı yok")
    elif len(header_lines) > 1:
        error(
            "CHANGELOG.md: `# Changelog` birden fazla (satır "
            + ", ".join(str(n + 1) for n in header_lines)
            + ")"
        )
    else:
        first = next((n for n, line in enumerate(lines) if line.strip()), None)
        if first != header_lines[0]:
            error(
                f"CHANGELOG.md: `# Changelog` dosyanın başında değil"
                f" (satır {header_lines[0] + 1})"
            )
    headings = [
        (m.group(1), text[: m.start()].count("\n") + 1)
        for m in VERSION_HEADING.finditer(text)
    ]
    if not headings:
        error("CHANGELOG.md: sürüm başlığı bulunamadı")
        return
    seen: dict[str, int] = {}
    for ver, line in headings:
        if ver in seen:
            error(f"CHANGELOG.md: sürüm {ver} birden fazla (satır {seen[ver]}, {line})")
        else:
            seen[ver] = line

    def semver(value: str) -> tuple[int, ...]:
        return tuple(int(part) for part in value.split("."))

    for (prev, _), (cur, line) in zip(headings, headings[1:]):
        if semver(cur) >= semver(prev):
            error(
                f"CHANGELOG.md: sürüm sırası azalan değil: {prev} → {cur}"
                f" (satır {line})"
            )
    if headings[0][0] != version:
        error(
            f"CHANGELOG.md: ilk sürüm başlığı {headings[0][0]}"
            f" ≠ VERSION ({version})"
        )
