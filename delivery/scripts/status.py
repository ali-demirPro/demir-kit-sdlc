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
"""

from __future__ import annotations

import argparse
import json
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
GH_FIELDS = "number,title,state,labels,body"
GH_LIMIT = "500"
GH_TIMEOUT = 30
DOCTOR_TIMEOUT = 120
EPIC_BLOCK = "demir-kit-epic"
LEAF_BLOCK = "demir-kit"
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


def checkpoint_count(seal: dict) -> int:
    checkpoints = seal.get("checkpoints")
    return len(checkpoints) if isinstance(checkpoints, list) else 0


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


def epic_checkpoint_total(epic_block: dict, number: int, seals: dict[int, dict]) -> int:
    """Epic çocuklarının seal'lerindeki checkpoint toplamı."""
    return sum(
        checkpoint_count(seals[child]) for child in epic_children(epic_block, number, seals)
    )


def epic_checkpoint_done(
    epic_block: dict,
    number: int,
    seals: dict[int, dict],
    labels_by_number: dict[int, set[str]],
) -> int:
    """Yalnız leaf-done etiketli çocukların checkpoint toplamı."""
    return sum(
        checkpoint_count(seals[child])
        for child in epic_children(epic_block, number, seals)
        if "leaf-done" in labels_by_number.get(child, set())
    )


def epic_entry(
    number: int,
    title: str,
    labels: set[str],
    checkpoint_done: int,
    checkpoint_total: int,
    issue_state: str = "",
    leaves: list[dict] | None = None,
) -> dict:
    return {
        "number": number,
        "title": title,
        "state": epic_state(labels, issue_state),
        "risk": None,
        "checkpoints": {"done": checkpoint_done, "total": checkpoint_total},
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
    }


def collect_issues(issues: list[dict], all_epics: bool = False) -> tuple[list[dict], dict]:
    """Issue listesinden epics + counts; epic/leaf bloklarına göre ayırır.

    `all_epics` kapalıyken `epic-done` etiketli veya kapalı issue'lar listeye
    girmez; `counts.leaves` yalnız listelenen epic'lerin `leaves[]` toplamıdır.
    `leaves[]` seal şartı aramaz; seal yalnız checkpoint sayımını besler.
    """
    seals: dict[int, dict] = {}
    issues_by_number: dict[int, dict] = {}
    labels_by_number: dict[int, set[str]] = {}
    epic_rows: list[tuple[int, dict, set[str], str, str]] = []
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
            epic_checkpoint_done(block, number, seals, labels_by_number),
            epic_checkpoint_total(block, number, seals),
            issue_state,
            epic_leaves(block, issues_by_number),
        )
        for number, block, labels, title, issue_state in sorted(
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
            epics, counts = collect_issues(issues, all_epics=args.all_epics)
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
    "leaves",
    "gate",
    "open_findings",
    "approvals",
    "next_action",
    "cycle_minutes",
    "cost_delta",
}


def valid_epic(item: object) -> bool:
    if not isinstance(item, dict) or set(item) != EPIC_KEYS:
        return False
    if not isinstance(item.get("number"), int) or isinstance(item.get("number"), bool):
        return False
    if not isinstance(item.get("title"), str) or not isinstance(item.get("state"), str):
        return False
    if item.get("risk") is not None and not isinstance(item.get("risk"), str):
        return False
    checkpoints = item.get("checkpoints")
    if not isinstance(checkpoints, dict) or set(checkpoints) != {"done", "total"}:
        return False
    if not all(
        isinstance(checkpoints.get(key), int) and not isinstance(checkpoints.get(key), bool)
        for key in ("done", "total")
    ):
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
    if not all(valid_epic(item) for item in data["epics"]):
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
        checkpoints = epic.get("checkpoints") or {}
        detail = f"cp {checkpoints.get('done', 0)}/{checkpoints.get('total', 0)}"
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
