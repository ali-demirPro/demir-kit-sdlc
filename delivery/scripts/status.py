#!/usr/bin/env python3
"""Proje ve epic durumunu salt-okunur özetleyen CLI.

Sözleşme alanları:
- `source`: "live" taze hesaplandı, "cache" önbellekten okundu.
- `stale`: yalnızca durum eksikse true (kit kökü yok ya da çevrimdışı önbellek yok).
- `kit.dirty`: git durumu okunamazsa null (bilinmiyor), true/false değil.

CP-2 kapsamı: `epics` ve `counts` GitHub issue'larından toplanır
(`gh issue list`). `--offline` ağa çıkmaz ve yalnızca önbellekten döner;
`--with-gate` epic başına `doctor.sh --issue N` koşar; `--with-cost` kabul
edilir ama maliyet CP-3'te toplanır.

Varsayılan olarak yalnız aktif epic'ler listelenir: `epic-done` etiketli ya da
kapalı issue'lar `epics[]` dışında kalır. `--all-epics` hepsini gösterir.
`counts.epics` listelenen epic sayısı, `counts.leaves` bu epic'lerin `leaves[]`
toplamıdır; `counts.blocked` tüm issue'ları saymaya devam eder.

Her epic `evaluations` bloğu taşır: `.kit/evaluations.json` salt-okur; dosya ya
da kayıt yoksa tüm alanlar `null` (sıfır uydurulmaz), geçersiz alan `null` +
uyarı olur. Düz metin çıktısı bu blokta değişmez; yalnız `--json` genişler.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

CONTRACT_VERSION = 1
CONFIG_NAME = "kit.config.yaml"
KIT_MARKERS = (
    Path("delivery") / "scripts" / "doctor.py",
    Path("delivery") / "scripts" / "doctor.sh",
)
DOCTOR_SCRIPT = Path("delivery") / "scripts" / "doctor.sh"
GH_FIELDS = "number,title,state,labels,body,updatedAt"
GH_LIMIT = "500"
GH_TIMEOUT = 30
DOCTOR_TIMEOUT = 120
EPIC_BLOCK = "demir-kit-epic"
LEAF_BLOCK = "demir-kit"
# Eval özeti: proje kökünde `.kit/evaluations.json`, salt-okur.
EVALUATIONS_PATH = Path(".kit") / "evaluations.json"
EVALUATION_KEYS = {
    "batch",
    "cases_pass",
    "cases_total",
    "discovery_rate",
    "findings",
    "updated_at",
}
FINDING_KEYS = ("friction", "objection", "opportunity")
# Epic anahtarı yalnız sade pozitif tam sayı: boşluk, işaret, baştaki sıfır yok.
EVAL_EPIC_KEY = re.compile(r"^[1-9][0-9]*$")
# JS güvenli tam sayı sınırı; daha büyük sayı panelde kaybolur.
EVALUATION_COUNT_MAX = 2**53
# `updated_at` yalnız ISO-8601 kabul eder; başka metin `null` olur.
ISO_8601 = re.compile(
    r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
    r"T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?"
    r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)
# Etiket önceliği: ilk eşleşen kazanır.
STATE_PRIORITY = (
    "epic-done",
    "epic-reconcile",
    "blocked",
    "executing",
    "scope-confirmed",
)
# Leaf listesi için ayrı öncelik: leaf-done > blocked > deferred > executing >
# agent-approved > intake. Engel ve erteleme, ilerlemeden önce anlatılır.
LEAF_STATE_PRIORITY = (
    "leaf-done",
    "blocked",
    "deferred",
    "executing",
    "agent-approved",
    "intake",
)
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


def repo_root(project: Path) -> str | None:
    """Ortak git dizininin üst dizini; git yoksa ya da depo değilse None.

    Worktree'de ortak dizin ana checkout'un `.git`'idir, yani üst dizin ana
    checkout köküdür: aynı repo tek proje sayılabilir.
    """
    common = git(project, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        return None
    return str(Path(common).resolve().parent)


def find_kit_root(start: Path, config: dict | None = None) -> Path | None:
    """Kit kökü: önce `kit.root`, sonra yukarı doğru delivery/scripts/doctor.py."""
    declared = str(section(config or {}, "kit").get("root") or "").strip()
    if declared:
        candidate = Path(declared).expanduser()
        if not candidate.is_absolute():
            candidate = start / candidate
        candidate = candidate.resolve()
        if any((candidate / marker).is_file() for marker in KIT_MARKERS):
            return candidate
    for candidate in (start, *start.parents):
        if any((candidate / marker).is_file() for marker in KIT_MARKERS):
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
    for candidate in (cwd, *cwd.parents):
        if (candidate / CONFIG_NAME).is_file():
            return candidate
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
        warnings.append("kit kökü bulunamadı: delivery/scripts/doctor.py|doctor.sh yok")
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
        "repo_root": repo_root(project),
        "tracker": {
            "provider": str(tracker.get("provider") or ""),
            "repo": str(tracker.get("repo") or ""),
        },
    }


def yaml_block(body: object, kind: str) -> dict:
    """Issue body içindeki ```yaml <kind> bloğu; yoksa/bozuksa {}."""
    if not isinstance(body, str):
        return {}
    match = re.search(rf"```yaml\s+{kind}\s*\n(.*?)```", body, re.S)
    if match is None:
        return {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def labels_of(issue: dict) -> set[str]:
    labels = issue.get("labels")
    if not isinstance(labels, list):
        return set()
    names: set[str] = set()
    for item in labels:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.add(item["name"])
        elif isinstance(item, str):
            names.add(item)
    return names


def epic_state(
    labels: set[str],
    issue_state: str = "",
    priority: tuple[str, ...] = STATE_PRIORITY,
) -> str:
    for name in priority:
        if name in labels:
            return name
    return "closed" if str(issue_state).upper() == "CLOSED" else "open"


def epic_is_done(labels: set[str], issue_state: str = "") -> bool:
    """Kapanmış epic: `epic-done` etiketi ya da kapalı issue."""
    return "epic-done" in labels or str(issue_state).upper() == "CLOSED"


def child_numbers(epic_block: dict) -> list[int]:
    numbers: list[int] = []
    children = epic_block.get("children")
    if not isinstance(children, list):
        return numbers
    for item in children:
        try:
            numbers.append(int(item))
        except (TypeError, ValueError):
            continue
    return numbers


def checkpoint_items(seal: dict, leaf: int, done: bool) -> list[dict]:
    """Seal'deki checkpoint'ler; `done` çocuğun `leaf-done` olmasından gelir.

    Her öğe çocuğun numarasını `leaf` alanında taşır: panel CP satırını
    `#<leaf> · CP-1 ✓ başlık` diye çizer.
    """
    checkpoints = seal.get("checkpoints")
    if not isinstance(checkpoints, list):
        return []
    items: list[dict] = []
    for item in checkpoints:
        if not isinstance(item, dict):
            continue
        cp_id = item.get("id")
        if not isinstance(cp_id, str) or not cp_id:
            continue
        items.append(
            {
                "id": cp_id,
                "title": str(item.get("title") or ""),
                "done": done,
                "leaf": leaf,
            }
        )
    return items


def epic_children(epic_block: dict, number: int, seals: dict[int, dict]) -> list[int]:
    """Seal'i olan epic çocukları; children yoksa seal'deki epic alanına düşer."""
    children = child_numbers(epic_block)
    if children:
        return [child for child in children if child in seals]
    return [
        child
        for child, seal in seals.items()
        if str(seal.get("epic")) == str(number)
    ]


def epic_leaves(epic_block: dict, issues_by_number: dict[int, dict]) -> list[dict]:
    """`children` numaralarından issue listesinde bulunanlar; seal şartı yok.

    Seal yalnız checkpoint sayımında (`epic_children`) gerekir; seal'i olmayan
    çocuk da başlığı ve durumuyla listede görünür.
    """
    leaves: list[dict] = []
    for child in child_numbers(epic_block):
        issue = issues_by_number.get(child)
        if issue is None:
            continue
        leaves.append(
            {
                "number": child,
                "title": str(issue.get("title") or ""),
                "state": epic_state(
                    labels_of(issue),
                    str(issue.get("state") or ""),
                    LEAF_STATE_PRIORITY,
                ),
            }
        )
    return leaves


def epic_checkpoint_items(
    epic_block: dict,
    number: int,
    seals: dict[int, dict],
    labels_by_number: dict[int, set[str]],
) -> list[dict]:
    """Epic çocuklarının checkpoint'leri; `done` çocuk bazlıdır (leaf-done)."""
    items: list[dict] = []
    for child in epic_children(epic_block, number, seals):
        items.extend(
            checkpoint_items(
                seals[child],
                child,
                "leaf-done" in labels_by_number.get(child, set()),
            )
        )
    return items


def epic_url(number: int, repo: str) -> str | None:
    """GitHub issue bağlantısı; `tracker.repo` yoksa null."""
    repo = repo.strip()
    return f"https://github.com/{repo}/issues/{number}" if repo else None


def empty_evaluations() -> dict:
    """Tüm alanları `null`; kayıt yoksa sıfır uydurulmaz."""
    return {
        "batch": None,
        "cases_pass": None,
        "cases_total": None,
        "discovery_rate": None,
        "findings": {key: None for key in FINDING_KEYS},
        "updated_at": None,
    }


def evaluation_block(value: object) -> dict:
    """Geçerli kaydı kanonik bloğa kopyalar; eksik/bozuk alan `null` kalır."""
    block = empty_evaluations()
    if not isinstance(value, dict):
        return block
    for key in ("batch", "cases_pass", "cases_total", "discovery_rate", "updated_at"):
        if key in value:
            block[key] = value[key]
    rate = block["discovery_rate"]
    if isinstance(rate, (int, float)) and not isinstance(rate, bool):
        try:
            block["discovery_rate"] = float(rate)
        except (OverflowError, ValueError):
            block["discovery_rate"] = None
    findings = value.get("findings")
    if isinstance(findings, dict):
        for key in FINDING_KEYS:
            if key in findings:
                block["findings"][key] = findings[key]
    return block


def non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def valid_evaluation_count(value: object) -> bool:
    """Negatif olmayan ve JS güvenli sınırı aşmayan tam sayı."""
    return non_negative_int(value) and value <= EVALUATION_COUNT_MAX


def valid_batch(value: object) -> bool:
    """Boş olmayan batch adı; yalnız boşluk da geçersiz."""
    return isinstance(value, str) and bool(value.strip())


def valid_discovery_rate(value: object) -> bool:
    """0..1 arası sonlu sayı; dev int OverflowError yerine geçersiz sayılır."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(number) and 0 <= number <= 1


def valid_updated_at(value: object) -> bool:
    """ISO-8601 biçim + gerçek takvim günü (2026-02-31 geçersiz)."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not ISO_8601.match(text):
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def eval_field(
    raw: dict,
    epic: str,
    key: str,
    check,
    warnings: list[str],
) -> object:
    """Tek alan: eksik/geçersiz → `null` + kısa uyarı; açık `null` geçerli."""
    if key not in raw:
        warnings.append(f"evaluations {epic}: {key} eksik, null")
        return None
    value = raw[key]
    if value is None or check(value):
        return value
    warnings.append(f"evaluations {epic}: {key} geçersiz, null")
    return None


def normalize_evaluations(raw: object, epic: str, warnings: list[str]) -> dict:
    """Tek epic kaydını doğrular; her alan bağımsız olarak `null`a düşer."""
    block = empty_evaluations()
    if not isinstance(raw, dict):
        warnings.append(f"evaluations {epic}: kayıt eşleme değil, null")
        return block
    block["batch"] = eval_field(raw, epic, "batch", valid_batch, warnings)
    if isinstance(block["batch"], str):
        block["batch"] = block["batch"].strip()
    for key in ("cases_pass", "cases_total"):
        block[key] = eval_field(raw, epic, key, valid_evaluation_count, warnings)
    block["discovery_rate"] = eval_field(
        raw, epic, "discovery_rate", valid_discovery_rate, warnings
    )
    if isinstance(block["discovery_rate"], (int, float)) and not isinstance(
        block["discovery_rate"], bool
    ):
        block["discovery_rate"] = float(block["discovery_rate"])
    cases_pass, cases_total = block["cases_pass"], block["cases_total"]
    if (
        cases_pass is not None
        and cases_total is not None
        and cases_pass > cases_total
    ):
        warnings.append(f"evaluations {epic}: cases_pass > cases_total, null")
        block["cases_pass"] = None
        block["cases_total"] = None
    findings = raw.get("findings")
    if "findings" not in raw:
        warnings.append(f"evaluations {epic}: findings eksik, null")
    elif findings is not None and not isinstance(findings, dict):
        warnings.append(f"evaluations {epic}: findings geçersiz, null")
    elif isinstance(findings, dict):
        for key in FINDING_KEYS:
            block["findings"][key] = eval_field(
                findings, epic, key, non_negative_int, warnings
            )
    updated_at = eval_field(raw, epic, "updated_at", valid_updated_at, warnings)
    block["updated_at"] = updated_at.strip() if isinstance(updated_at, str) else None
    return block


def load_evaluations(project: Path) -> tuple[dict[int, dict], list[str]]:
    """`.kit/evaluations.json` → epic numarası → doğrulanmış blok.

    Dosya yoksa boş eşleme döner (uyarı yok); bozuk dosyada tüm alanlar `null`
    kalır ve tek bir uyarı eklenir. Komut hiçbir durumda çökmez.
    """
    warnings: list[str] = []
    path = project / EVALUATIONS_PATH
    if not path.exists():
        return {}, warnings
    if not path.is_file():
        warnings.append("evaluations dosya değil, tüm alanlar null")
        return {}, warnings
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        warnings.append("evaluations okunamadı: dosyaya erişilemedi, tüm alanlar null")
        return {}, warnings
    except ValueError:
        warnings.append("evaluations okunamadı: JSON geçersiz, tüm alanlar null")
        return {}, warnings
    if not isinstance(data, dict):
        warnings.append("evaluations kökü eşleme değil, tüm alanlar null")
        return {}, warnings
    epics = data.get("epics")
    if not isinstance(epics, dict):
        warnings.append("evaluations epics eşlemesi yok, tüm alanlar null")
        return {}, warnings
    records: dict[int, dict] = {}
    for key, raw in epics.items():
        name = key if isinstance(key, str) else str(key)
        if not isinstance(key, str) or not EVAL_EPIC_KEY.match(name):
            warnings.append(f"evaluations epic anahtarı geçersiz: {name}")
            continue
        number = int(name)
        if number in records:
            warnings.append(f"evaluations epic anahtarı yinelenen: {name}")
            continue
        records[number] = normalize_evaluations(raw, name, warnings)
    return records, warnings


def epic_entry(
    number: int,
    title: str,
    labels: set[str],
    checkpoints: list[dict],
    updated_at: str | None,
    url: str | None,
    issue_state: str = "",
    leaves: list[dict] | None = None,
    evaluations: dict | None = None,
) -> dict:
    return {
        "number": number,
        "title": title,
        "state": epic_state(labels, issue_state),
        "risk": None,
        "checkpoints": list(checkpoints),
        "updated_at": updated_at,
        "url": url,
        "leaves": list(leaves or []),
        "gate": None,
        "open_findings": 0,
        "approvals": {
            "agent_approved": "agent-approved" in labels,
            "human_qa": "human-qa" in labels,
        },
        "next_action": None,
        "cycle_minutes": None,
        "cost_delta": None,
        "evaluations": evaluation_block(evaluations),
    }


def issue_updated_at(issue: dict) -> str | None:
    """Issue `updatedAt`; ISO-8601 değilse `null` (panel bozuk metin çizmesin)."""
    value = issue.get("updatedAt")
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if ISO_8601.match(text) else None


def collect_issues(
    issues: list[dict],
    all_epics: bool = False,
    repo: str = "",
    evaluations: dict[int, dict] | None = None,
) -> tuple[list[dict], dict]:
    """Issue listesinden epics + counts; epic/leaf bloklarına göre ayırır.

    `all_epics` kapalıyken `epic-done` etiketli veya kapalı issue'lar listeye
    girmez; `counts.leaves` yalnız listelenen epic'lerin `leaves[]` toplamıdır.
    `leaves[]` seal şartı aramaz; seal yalnız checkpoint listesini besler.
    `evaluations` epic numarasıyla eşleştirilir; kayıt yoksa alanlar `null`.
    """
    eval_by_number = evaluations or {}
    seals: dict[int, dict] = {}
    issues_by_number: dict[int, dict] = {}
    labels_by_number: dict[int, set[str]] = {}
    epic_rows: list[tuple[int, dict, set[str], str, str, str | None]] = []
    blocked = 0
    for issue in issues:
        number = issue.get("number")
        if not isinstance(number, int) or isinstance(number, bool):
            continue
        labels = labels_of(issue)
        labels_by_number[number] = labels
        issues_by_number[number] = issue
        if "blocked" in labels:
            blocked += 1
        body = issue.get("body")
        seal = yaml_block(body, LEAF_BLOCK)
        if seal:
            seals[number] = seal
        epic_block = yaml_block(body, EPIC_BLOCK)
        if epic_block:
            epic_rows.append(
                (
                    number,
                    epic_block,
                    labels,
                    str(issue.get("title") or ""),
                    str(issue.get("state") or ""),
                    issue_updated_at(issue),
                )
            )
    active_rows = [
        row
        for row in epic_rows
        if all_epics or not epic_is_done(row[2], row[4])
    ]
    epics = [
        epic_entry(
            number,
            title,
            labels,
            epic_checkpoint_items(block, number, seals, labels_by_number),
            updated_at,
            epic_url(number, repo),
            issue_state,
            epic_leaves(block, issues_by_number),
            eval_by_number.get(number),
        )
        for number, block, labels, title, issue_state, updated_at in sorted(
            active_rows, key=lambda row: row[0]
        )
    ]
    counts = {
        "epics": len(epics),
        "leaves": sum(len(epic["leaves"]) for epic in epics),
        "blocked": blocked,
    }
    return epics, counts


def fetch_issues(project: Path, warnings: list[str]) -> list[dict] | None:
    """`gh issue list`; gh yoksa/başarısızsa None + uyarı (hata değil)."""
    try:
        proc = subprocess.run(
            ["gh", "issue", "list", "--json", GH_FIELDS, "--limit", GH_LIMIT, "--state", "all"],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        warnings.append(f"gh çalıştırılamadı: {exc}")
        return None
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        reason = detail[0].strip() if detail else "bilinmeyen hata"
        warnings.append(f"gh issue list başarısız: {reason}")
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        warnings.append("gh çıktısı JSON değil: issue'lar okunamadı")
        return None
    if not isinstance(data, list):
        warnings.append("gh çıktısı liste değil: issue'lar okunamadı")
        return None
    if len(data) >= int(GH_LIMIT):
        warnings.append(f"gh issue list {GH_LIMIT} ile sınırlı; daha fazla issue olabilir")
    return [item for item in data if isinstance(item, dict)]


def gate_state(
    project: Path, kit_root: Path, issue: int, warnings: list[str]
) -> str:
    """`doctor.sh --issue N`; exit 0 → pass, değilse fail."""
    script = kit_root / DOCTOR_SCRIPT
    if not script.is_file():
        warnings.append(f"doctor.sh yok: epic {issue} gate hesaplanamadı")
        return "fail"
    try:
        proc = subprocess.run(
            [str(script), "--issue", str(issue)],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=DOCTOR_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        warnings.append(f"doctor çalıştırılamadı (epic {issue}): {exc}")
        return "fail"
    return "pass" if proc.returncode == 0 else "fail"


def build_status(project: Path, args: argparse.Namespace) -> dict:
    warnings: list[str] = []
    evaluations, eval_warnings = load_evaluations(project)
    warnings.extend(eval_warnings)
    config = load_config(project)
    if not (project / CONFIG_NAME).is_file():
        warnings.append(f"{CONFIG_NAME} yok: {project}")
    declared = str(section(config, "kit").get("root") or "").strip()
    if declared:
        candidate = Path(declared).expanduser()
        if not candidate.is_absolute():
            candidate = project / candidate
        if not candidate.is_dir():
            warnings.append(f"kit.root bulunamadı: {declared}")
    kit_root = find_kit_root(project, config)
    kit = kit_state(kit_root, config, warnings)
    epics: list[dict] = []
    counts = {"epics": 0, "leaves": 0, "blocked": 0}
    stale = kit_root is None
    if args.offline:
        warnings.append("önbellek yok: çevrimdışı modda ağa çıkılmadı")
        stale = True
    else:
        issues = fetch_issues(project, warnings)
        if issues is None:
            stale = True
        else:
            epics, counts = collect_issues(
                issues,
                all_epics=args.all_epics,
                repo=str(section(config, "tracker").get("repo") or ""),
                evaluations=evaluations,
            )
    if args.with_gate:
        if not epics:
            warnings.append("--with-gate: epic yok, doctor çağrılmadı")
        elif kit_root is None:
            warnings.append("--with-gate: kit kökü yok, doctor çağrılmadı")
        else:
            for epic in epics:
                epic["gate"] = gate_state(project, kit_root, epic["number"], warnings)
    if args.with_cost:
        warnings.append("maliyet henüz toplanmıyor")
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "stale": stale,
        "source": "live",
        "kit": kit,
        "project": project_state(project, config),
        "epics": epics,
        "counts": counts,
        "warnings": warnings,
    }


def cache_path(project: Path) -> Path:
    return project / ".orchestration" / "status-cache.json"


EPIC_KEYS = {
    "number",
    "title",
    "state",
    "risk",
    "checkpoints",
    "updated_at",
    "url",
    "leaves",
    "gate",
    "open_findings",
    "approvals",
    "next_action",
    "cycle_minutes",
    "cost_delta",
    "evaluations",
}


def valid_checkpoint(item: object) -> bool:
    return (
        isinstance(item, dict)
        and set(item) == {"id", "title", "done", "leaf"}
        and isinstance(item.get("id"), str)
        and isinstance(item.get("title"), str)
        and isinstance(item.get("done"), bool)
        and isinstance(item.get("leaf"), int)
        and not isinstance(item.get("leaf"), bool)
    )


def valid_evaluations(item: object) -> bool:
    if not isinstance(item, dict) or set(item) != EVALUATION_KEYS:
        return False
    if item.get("batch") is not None and not valid_batch(item.get("batch")):
        return False
    for key in ("cases_pass", "cases_total"):
        value = item.get(key)
        if value is not None and not valid_evaluation_count(value):
            return False
    cases_pass, cases_total = item.get("cases_pass"), item.get("cases_total")
    if (
        cases_pass is not None
        and cases_total is not None
        and cases_pass > cases_total
    ):
        return False
    rate = item.get("discovery_rate")
    if rate is not None and not valid_discovery_rate(rate):
        return False
    findings = item.get("findings")
    if not isinstance(findings, dict) or set(findings) != set(FINDING_KEYS):
        return False
    if not all(
        value is None or valid_evaluation_count(value) for value in findings.values()
    ):
        return False
    return item.get("updated_at") is None or valid_updated_at(item.get("updated_at"))


def valid_epic(item: object, *, allow_legacy: bool = False) -> bool:
    if not isinstance(item, dict):
        return False
    keys = set(item)
    if keys == EPIC_KEYS:
        if not valid_evaluations(item.get("evaluations")):
            return False
    elif not (allow_legacy and keys == EPIC_KEYS - {"evaluations"}):
        return False
    if not isinstance(item.get("number"), int) or isinstance(item.get("number"), bool):
        return False
    if not isinstance(item.get("title"), str) or not isinstance(item.get("state"), str):
        return False
    if item.get("risk") is not None and not isinstance(item.get("risk"), str):
        return False
    checkpoints = item.get("checkpoints")
    if not isinstance(checkpoints, list) or not all(
        valid_checkpoint(checkpoint) for checkpoint in checkpoints
    ):
        return False
    if item.get("updated_at") is not None and not isinstance(item.get("updated_at"), str):
        return False
    if item.get("url") is not None and not isinstance(item.get("url"), str):
        return False
    if item.get("gate") not in {None, "pass", "fail"}:
        return False
    leaves = item.get("leaves")
    if not isinstance(leaves, list) or not all(
        isinstance(leaf, dict) for leaf in leaves
    ):
        return False
    if not isinstance(item.get("open_findings"), int) or isinstance(
        item.get("open_findings"), bool
    ):
        return False
    approvals = item.get("approvals")
    if not isinstance(approvals, dict) or set(approvals) != {"agent_approved", "human_qa"}:
        return False
    if not all(isinstance(value, bool) for value in approvals.values()):
        return False
    return all(
        item.get(key) is None or isinstance(item.get(key), (str, int, float))
        for key in ("next_action", "cycle_minutes", "cost_delta")
    )


def valid_contract(data: object, *, allow_legacy: bool = False) -> bool:
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
    if not isinstance(project, dict) or set(project) != {
        "name",
        "profile",
        "repo_root",
        "tracker",
    }:
        return False
    if not all(isinstance(project.get(key), str) for key in ("name", "profile")):
        return False
    if project.get("repo_root") is not None and not isinstance(
        project.get("repo_root"), str
    ):
        return False
    tracker = project.get("tracker")
    if not isinstance(tracker, dict) or set(tracker) != {"provider", "repo"}:
        return False
    if not all(isinstance(tracker.get(key), str) for key in ("provider", "repo")):
        return False
    if not isinstance(data.get("epics"), list):
        return False
    if not all(valid_epic(item, allow_legacy=allow_legacy) for item in data["epics"]):
        return False
    counts = data.get("counts")
    if not isinstance(counts, dict) or set(counts) != {"epics", "leaves", "blocked"}:
        return False
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in counts.values()):
        return False
    warnings = data.get("warnings")
    return isinstance(warnings, list) and all(isinstance(item, str) for item in warnings)


def normalize_cached_contract(data: dict) -> dict:
    """Önbellek epic'lerini kanonikleştirir.

    Eski kit sürümünün yazdığı önbellekte `evaluations` yoktur; eksik alan
    all-null bloğa tamamlanır ki `--offline` eski önbelleği kullanmaya devam etsin.
    """
    epics = []
    for item in data["epics"]:
        epic = dict(item)
        epic["evaluations"] = evaluation_block(epic.get("evaluations"))
        epics.append(epic)
    return {**data, "epics": epics}


def args_fingerprint(args: argparse.Namespace) -> dict:
    return {
        "with_gate": bool(args.with_gate),
        "with_cost": bool(args.with_cost),
        "full": bool(args.full),
        "all_epics": bool(args.all_epics),
    }


def read_cache(
    project: Path,
    ttl: int,
    fingerprint: dict,
    *,
    ignore_ttl: bool = False,
    ignore_args: bool = False,
) -> tuple[dict | None, int]:
    """Geçerli önbellek ve yaşı; bozuk/eski/başka argümanlar için (None, 0)."""
    path = cache_path(project)
    try:
        age = int(time.time() - path.stat().st_mtime)
    except OSError:
        return None, 0
    if not ignore_ttl and age > ttl:
        return None, 0
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, 0
    if not isinstance(envelope, dict):
        return None, 0
    if not ignore_args and envelope.get("args") != fingerprint:
        return None, 0
    data = envelope.get("data")
    if not valid_contract(data, allow_legacy=True):
        return None, 0
    data = normalize_cached_contract(data)
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


def from_cache(cached: dict, age: int) -> dict:
    data = dict(cached)
    data["source"] = "cache"
    data["warnings"] = [
        *(data.get("warnings") or []),
        f"önbellekten okundu: {age}s",
    ]
    return data


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
        checkpoints = epic.get("checkpoints") or []
        done = sum(1 for checkpoint in checkpoints if checkpoint.get("done"))
        detail = f"cp {done}/{len(checkpoints)}"
        if epic.get("gate"):
            detail += f" · gate {epic['gate']}"
        lines.append(f"epic {epic.get('number', '?')}: {epic.get('state', '-')} · {detail}")
    for warning in data["warnings"]:
        lines.append(f"[uyarı] {warning}")
    if data["stale"]:
        lines.append("[uyarı] kit kökü yok — durum eksik")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="proje ve epic durumu (salt-okunur)")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--offline", action="store_true", help="ağa çıkmaz; önbellekten döner")
    parser.add_argument("--with-gate", action="store_true", help="epic başına doctor gate'i koş")
    parser.add_argument("--with-cost", action="store_true", help="maliyet (CP-3)")
    parser.add_argument("--cache-ttl", type=int, default=0, metavar="N")
    parser.add_argument("--full", action="store_true", help="rezerve (CP-3)")
    parser.add_argument(
        "--all-epics",
        action="store_true",
        help="kapanmış (epic-done/kapalı) epic'leri de listele",
    )
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
    if args.offline:
        cached, age = read_cache(
            project, 0, fingerprint, ignore_ttl=True, ignore_args=True
        )
        if cached is not None:
            data = from_cache(cached, age)
            data["stale"] = False
            if not args.with_gate:
                for epic in data.get("epics") or []:
                    epic["gate"] = None
        else:
            try:
                data = build_status(project, args)
            except StatusError as exc:
                print(f"status: {exc}", file=sys.stderr)
                return 1
            if cache_path(project).is_file():
                data["warnings"].insert(0, "önbellek geçersiz: yok sayıldı")
    else:
        cached, age = (
            read_cache(project, args.cache_ttl, fingerprint) if args.cache_ttl > 0 else (None, 0)
        )
        if cached is not None:
            data = from_cache(cached, age)
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
