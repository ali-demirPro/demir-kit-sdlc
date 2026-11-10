#!/usr/bin/env python3
"""doctor: `.kit/local.yaml` kişisel override beyaz listesi denetimi.

Beyaz listenin tek kaynağı `delivery/local-overrides.yaml`. `read` ve `write`
listeleri ayrışırsa, `values` read ile eşleşmezse veya kilitli bir anahtar
listeye girerse hata verilir. Kişisel dosya gitignore dışındaysa ya da git'te
izleniyorsa da hata verilir; depoya kişisel tercih girmemeli.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import resolver  # noqa: E402

ROOT = SCRIPTS.parents[1]

# Politika dosyası tek başına kaldırılamaz: bu anahtarlar her zaman kilitli
# olmalı. Kanıt, reviewer, risk ve insan kapıları kişisel dosyaya açılmaz.
# `docs.density` bilinçli olarak dışarıda: kişisel dosyaya açılan tek düğme o.
REQUIRED_LOCKED = (
    "process.rigor",
    "qa.level",
    "modes.workflow",
    "modes.story_granularity",
    "modes.review_mode",
    "team.size",
    "routing.evidence_reviewers",
    "risk.level",
    "risk.auto_escalate",
    "gates.human",
    "gates.*",
)


def check_installed_skills(
    root: Path,
    check: Callable[[str], None],
    warn: Callable[[str], None],
) -> None:
    """`install.sh` kopyaları kaynaktan geride kalırsa uyar.

    `.agents/` makineye özel kurulum durumudur (gitignore); testler
    `DEMIR_KIT_DOCTOR_IGNORE_INSTALLED=1` ile bu denetimi atlar ki sonuç
    makinenin kurulum yaşına bağlı kalmasın.
    """
    check("installed skills")
    if os.environ.get("DEMIR_KIT_DOCTOR_IGNORE_INSTALLED") == "1":
        return
    installed = root / ".agents" / "skills"
    source = root / "skills"
    if not installed.is_dir() or not source.is_dir():
        return
    stale = [
        entry.name
        for entry in sorted(installed.iterdir())
        if (source / entry.name / "SKILL.md").is_file()
        and (entry / "SKILL.md").is_file()
        and (source / entry.name / "SKILL.md").read_bytes()
        != (entry / "SKILL.md").read_bytes()
    ]
    if stale:
        warn(
            "kurulu skill kopyası kaynaktan farklı: "
            f"{', '.join(stale)} — './install.sh' ile tazele"
        )


def check_local_overrides(
    root: Path,
    policy_path: Path | None = None,
    error: Callable[[str], None] | None = None,
    check: Callable[[str], None] | None = None,
    load_yaml: Callable[[Path], dict] | None = None,
    rel: Callable[[Path], str] | None = None,
) -> None:
    """Beyaz liste tutarlı ve `.kit/local.yaml` depo dışı olmalı."""
    if check is None or error is None or load_yaml is None or rel is None:
        raise TypeError("check_local_overrides: error/check/load_yaml/rel gerekli")
    check("local_overrides")
    path = (
        Path(policy_path)
        if policy_path
        else ROOT / "delivery" / "local-overrides.yaml"
    )
    data = load_yaml(path)
    if not isinstance(data, dict) or not data:
        error(f"{rel(path)}: eksik veya geçersiz")
        return
    read = data.get("read") or []
    write = data.get("write") or []
    values = data.get("values") or {}
    locked = [str(item) for item in data.get("locked") or []]
    reasons = data.get("reasons") or {}
    # Zorunlu anahtar birebir yoksa da bir glob ile kapsanıyorsa yeterli:
    # `gates.*` varken `gates.human` literalini aramak yanlış pozitif üretir.
    missing_locked = [
        key
        for key in REQUIRED_LOCKED
        if resolver.locked_reason(key, {"locked": locked}) is None
    ]
    if missing_locked:
        error(
            f"{rel(path)}: zorunlu kilitli anahtar eksik — "
            + ", ".join(missing_locked)
        )
    if not isinstance(read, list) or not read:
        error(f"{rel(path)}: read listesi boş")
        read = []
    if not isinstance(write, list) or not write:
        error(f"{rel(path)}: write listesi boş")
        write = []
    read_keys = [str(item) for item in read]
    write_keys = [str(item) for item in write]
    if read_keys != write_keys:
        error(
            f"{rel(path)}: read ve write listeleri ayrışıyor — "
            f"read={read_keys} write={write_keys}"
        )
    if not isinstance(values, dict):
        error(f"{rel(path)}: values mapping değil")
        values = {}
    if set(values) != set(read_keys):
        error(
            f"{rel(path)}: values anahtarları read listesiyle aynı değil — "
            f"values={sorted(values)} read={sorted(read_keys)}"
        )
    # Kilit semantiği resolver ile ortak: nested alt-anahtar (ör.
    # `risk.auto_escalate.high`) da kilitli sayılır ve zorunlu set her zaman
    # geçerlidir; politika dosyası tek başına anahtarı açamaz.
    locked_policy = {
        "locked": locked,
        "reasons": reasons if isinstance(reasons, dict) else {},
    }
    for key in sorted(set(read_keys) | set(write_keys)):
        reason = resolver.locked_reason(
            key, locked_policy, required=REQUIRED_LOCKED
        )
        if reason is not None:
            error(
                f"{rel(path)}: '{key}' kilitli ama read/write içinde "
                f"({reason})"
            )
    if not isinstance(reasons, dict):
        error(f"{rel(path)}: reasons mapping değil")
        reasons = {}
    for pattern in locked:
        if not str(reasons.get(pattern) or "").strip():
            error(f"{rel(path)}: '{pattern}' için gerekçe yok")

    local_rel = resolver.LOCAL_FILE
    inside = _git_output(root, "rev-parse", "--is-inside-work-tree")
    if inside == "true":
        try:
            ignored = subprocess.run(
                ["git", "-C", str(root), "check-ignore", "-q", "--", local_rel],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            error(f"git check-ignore çalıştırılamadı — {exc}")
        else:
            if ignored.returncode != 0:
                error(
                    f".gitignore: {local_rel} yok — kişisel dosya depoya girebilir"
                )
        if _git_output(root, "ls-files", "--", local_rel):
            error(f"{local_rel}: git'te izleniyor — kişisel dosya commit edilmemeli")


def _git_output(path: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()
