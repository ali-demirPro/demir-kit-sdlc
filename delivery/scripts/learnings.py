#!/usr/bin/env python3
"""demir-kit learnings — fleet öğrenim federasyonu (self-improvement lane).

Hedef projelerdeki `learning` issue'ları ve closure metriklerini hasat eder,
normalize edip 2+ projede tekrar eden dersleri genel kural adayına dönüştürür.
Beyaz listedeki **ekleme** sınıfı değişiklikler otomatik uygulanır; kural
azaltma/silme ve kod değişikliği otomatik yazılmaz (I22 kapsamı: ürün teslimatı;
kit self-improvement lane'de de T2 insan onayı ve T9 insan kabulü gerekir,
doctor + testler ek kanıttır).

Usage:
  python3 delivery/scripts/learnings.py --harvest [--project .]
  python3 delivery/scripts/learnings.py --digest
  python3 delivery/scripts/learnings.py --emit
  python3 delivery/scripts/learnings.py --propose [--agent developer]
  python3 delivery/scripts/learnings.py --list
  python3 delivery/scripts/learnings.py --accept <öneri>
  python3 delivery/scripts/learnings.py --reject <öneri>
  python3 delivery/scripts/learnings.py --revert <skill>
  python3 delivery/scripts/learnings.py --apply
  python3 delivery/scripts/learnings.py --all

`--propose` canlı skill'e yazmaz: taslak `skills/.drafts/<öneri>/SKILL.md`,
diff ve issue gövdesi `.kit/proposals/` altında durur; ajan başına en fazla
`PENDING_LIMIT` öneri bekler. Aynı öğrenim reddedildiyse, onaylandıysa ya da
kayıt bayatladıysa `--propose` eski kaydı geçmişte bırakıp **yeni öneri
kimliği** açar; "onay bekliyor" yalnız gerçekten `pending` kayıt için denir.
Eski biçimdeki `.kit/proposals/<öneri>.draft.md` taslakları geriye dönük
okunur. Onayda önceki sürüm `.kit/skill-history/<skill>/` altında saklanır,
`--revert` geri yazar.

Onay sınırı: öneri kaydı taşıyan öğrenim `--apply` ile canlı dosyaya yazılmaz.
`pending`, `refused`, `rejected`, `accepted` ve `stale` kayıtlar `--apply`
beyaz listesini kapatır; yalnız `--accept` canlı skill'i günceller. Reddedilen
veya limit nedeniyle kabul edilmeyen öğrenim asla canlı dosyaya yazılmaz.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("learnings: PyYAML required (python3 -m pip install pyyaml)")

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / ".orchestration" / "learnings"
RECORDS = WORK / "records.json"
DIGEST = WORK / "digest.json"

# Beyaz liste: otomatik uygulanabilen değişiklik sınıfları (yalnız ekleme).
AUTO_KINDS = {"risk_glob_add", "eval_scenario_add", "skill_note_add"}
# Otomatik yazılamaz: kural azaltma/silme ve kod — daima insan/kit akışına.
MANUAL_KINDS = {"capability_add", "code_change"}


# ---------------------------------------------------------------- harvest

def load_fleet(root: Path) -> list[dict]:
    path = root / "delivery" / "fleet.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    repos = data.get("repos") or []
    return [r for r in repos if isinstance(r, dict) and r.get("repo")]


def run_gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"learnings: gh failed — {result.stderr.strip()}")
    return result.stdout


def fetch_repo_learnings(repo: str, tracker: str = "github") -> list[dict]:
    """Hedef repodaki `learning` issue'larını çeker (gh CLI)."""
    if tracker != "github":
        return []
    raw = run_gh(
        [
            "issue", "list", "--repo", repo, "--label", "learning",
            "--state", "all", "--limit", "100",
            "--json", "number,title,body,state",
        ]
    )
    return json.loads(raw or "[]")


def classify(title: str, body: str) -> tuple[str, str, str, str, list[str]]:
    """Issue metninden sınıf, şiddet, değişiklik sınıfı/hedefi ve dosyalar türetir."""
    text = f"{title}\n{body}".lower()
    if "gate" in text and ("tekrar" in text or "retry" in text or "fail" in text):
        klass = "gate-retry"
    elif "qa" in text or "insan" in text or "review" in text:
        klass = "qa-feedback"
    elif "yöntem" in text or "method" in text or "yeni" in text:
        klass = "method-novelty"
    elif "kapsam" in text or "scope" in text:
        klass = "scope-gap"
    else:
        klass = "metric-anomaly"

    severity = (
        "high"
        if any(w in text for w in ("auth", "payment", "prod", "veri kayb"))
        else ("medium" if "gate" in text or "risk" in text else "low")
    )

    if "glob" in text or "escalate" in text:
        kind, target = "risk_glob_add", "delivery/registry.yaml"
    elif "eval" in text or "senaryo" in text:
        kind, target = "eval_scenario_add", "delivery/agents"
    elif "skill" in text or "playbook" in text:
        kind, target = "skill_note_add", "skills"
    elif "capability" in text or "yetenek" in text:
        kind, target = "capability_add", "delivery/capabilities/registry.yaml"
    else:
        kind, target = "code_change", "delivery/scripts"

    targets = re.findall(r"`([\w./-]+)`", f"{title}\n{body}")
    return klass, severity, kind, target, targets


def normalize(raw: dict, repo: str) -> dict:
    title = raw.get("title") or ""
    body = raw.get("body") or ""
    klass, severity, kind, target, targets = classify(title, body)
    return {
        "demir_kit_version": "2",
        "id": f"{repo}#{raw.get('number', 0)}",
        "repo": repo,
        "issue": raw.get("number"),
        "class": klass,
        "summary": (title.strip() or body.strip()[:80]),
        "severity": severity,
        "occurrences": 1,
        "targets": targets,
        "proposed_change": {"kind": kind, "target": target, "auto": kind in AUTO_KINDS},
        "status": "local",
    }


def harvest(root: Path) -> list[dict]:
    records: list[dict] = []
    for entry in load_fleet(root):
        repo = entry["repo"]
        for raw in fetch_repo_learnings(repo, entry.get("tracker", "github")):
            records.append(normalize(raw, repo))
    WORK.mkdir(parents=True, exist_ok=True)
    RECORDS.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return records


# ---------------------------------------------------------------- digest

def signature(record: dict) -> str:
    change = record["proposed_change"]
    return f"{record['class']}|{change['kind']}|{change['target']}"


def digest(records: list[dict]) -> list[dict]:
    """Kümeleme: aynı imzalı ders 2+ farklı repoda → genel kural adayı."""
    clusters: dict[str, list[dict]] = {}
    for record in records:
        clusters.setdefault(signature(record), []).append(record)

    out: list[dict] = []
    for key in sorted(clusters):
        group = clusters[key]
        repos = sorted({r["repo"] for r in group})
        head = dict(group[0])
        head["occurrences"] = len(group)
        head["status"] = "candidate" if len(repos) >= 2 else "local"
        head["repos"] = repos
        out.append(head)
    WORK.mkdir(parents=True, exist_ok=True)
    DIGEST.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


# ---------------------------------------------------------------- emit

def render_issue(item: dict) -> str:
    change = item["proposed_change"]
    lines = [
        f"## Öğrenim — {item['id']}",
        "",
        f"**Sınıf:** {item['class']} · **Şiddet:** {item['severity']} · "
        f"**Tekrar:** {item['occurrences']} ({', '.join(item.get('repos', [item['repo']]))})",
        "",
        f"**Özet:** {item['summary']}",
        "",
        f"**Önerilen değişiklik:** `{change['kind']}` → `{change['target']}`",
    ]
    if change.get("auto"):
        lines += ["", "Beyaz listede — `learnings.py --apply` otomatik uygulayabilir."]
    else:
        lines += ["", "Beyaz liste dışı (kural azaltma / kod) — kit akışında işlenmeli."]
    return "\n".join(lines)


# ---------------------------------------------------------------- propose

# Ajan başına bekleyen öneri sınırı: öneri kuyruğu insan onayı bekler.
PENDING_LIMIT = 5

# Taslak skill konumu (AC-1): `skills/` altında yalnızca öneri olarak durur.
# `doctor` skill lint'i ve isim denetimi bu dizini atlar.
DRAFT_ROOT = ("skills", ".drafts")

# Karar verilmiş öneri durumları: aynı öğrenim için yeni öneri kimliği açılır.
TERMINAL_STATUSES = frozenset({"accepted", "rejected", "refused", "stale"})


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def proposal_slug(item: dict) -> str:
    return slugify(f"{item.get('class', 'learning')}-{item['id']}")


def proposal_files(root: Path, slug: str) -> tuple[Path, Path, Path]:
    """Öneri kaydı, taslak skill ve issue gövdesi yolları.

    Taslak `skills/.drafts/<öneri>/SKILL.md` altında durur (canlı skill değil);
    kayıt ve issue gövdesi `.kit/proposals/` altında kalır.
    """
    base = root / ".kit" / "proposals"
    draft = root.joinpath(*DRAFT_ROOT) / slug / "SKILL.md"
    return base / f"{slug}.json", draft, base / f"{slug}.md"


def remove_draft(draft_path: Path) -> None:
    """Taslak dosyasını ve boş kalan öneri dizinini siler."""
    if draft_path.is_file():
        draft_path.unlink()
    parent = draft_path.parent
    # Yalnız `skills/.drafts/<öneri>/` dizini temizlenir; `.kit/proposals` korunur.
    if is_draft_path(draft_path) and parent.name != ".drafts" and parent.is_dir():
        try:
            parent.rmdir()
        except OSError:  # dizin boş değilse dokunma
            pass


def legacy_draft_path(root: Path, slug: str) -> Path:
    """Eski biçim taslak yolu: `.kit/proposals/<öneri>.draft.md` (geriye dönük)."""
    return root / ".kit" / "proposals" / f"{slug}.draft.md"


def draft_candidates(root: Path, record: dict) -> list[Path]:
    """Önerinin taslağı için aday yollar: kayıtlı yol, eski biçim, yeni konum."""
    slug = str(record.get("id") or "")
    paths: list[Path] = []
    recorded = str(record.get("draft") or "").strip()
    if recorded:
        paths.append(root / recorded)
    paths.append(legacy_draft_path(root, slug))
    paths.append(root.joinpath(*DRAFT_ROOT) / slug / "SKILL.md")
    unique: list[Path] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique


def existing_draft(root: Path, record: dict) -> Path | None:
    """Önerinin gerçekten var olan taslağı (eski biçim dahil); yoksa None."""
    return next((path for path in draft_candidates(root, record) if path.is_file()), None)


def history_root(root: Path) -> Path:
    return root / ".kit" / "skill-history"


def load_proposal(root: Path, slug: str) -> dict | None:
    path = proposal_files(root, slug)[0]
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) else None


def load_all_proposals(root: Path) -> list[dict]:
    """`.kit/proposals` altındaki tüm karar kayıtları (kabul/ret/dahil)."""
    base = root / ".kit" / "proposals"
    if not base.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(base.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, dict):
            out.append(record)
    return out


def proposal_revision(record: dict, base: str) -> int:
    """Kaydın sürüm numarası: açık alan, kimlik son eki ya da 1."""
    raw = record.get("revision")
    if isinstance(raw, int) and raw > 0:
        return raw
    slug = str(record.get("id") or "")
    if slug == base:
        return 1
    if slug.startswith(f"{base}-"):
        tail = slug[len(base) + 1 :]
        if tail.isdigit() and int(tail) > 0:
            return int(tail)
    return 1


def proposal_records(root: Path, item: dict) -> list[dict]:
    """Aynı öğrenimin tüm öneri kayıtları (eski kimlikler dahil), sürüme göre."""
    base = proposal_slug(item)
    issue_ref = str(item.get("id") or "")
    found: list[dict] = []
    for candidate in load_all_proposals(root):
        slug = str(candidate.get("id") or "")
        suffix = slug[len(base) + 1 :] if slug.startswith(f"{base}-") else ""
        same_slug = slug == base or (suffix.isdigit() and int(suffix) > 0)
        same_issue = bool(issue_ref) and str(candidate.get("issue_ref") or "") == issue_ref
        if same_slug or same_issue:
            found.append(candidate)
    return sorted(found, key=lambda record: proposal_revision(record, base))


def proposal_for(root: Path, item: dict) -> dict | None:
    """Öğrenimin **en güncel** öneri kaydı (yoksa None)."""
    records = proposal_records(root, item)
    return records[-1] if records else None


def next_proposal_slug(root: Path, item: dict) -> tuple[str, int]:
    """Aynı öğrenim için yeni öneri kimliği ve sürümü.

    İlk öneri temel kimliği kullanır; terminal durumdaki (kabul/ret/refused)
    veya bayat kayıttan sonra kimlik `-2`, `-3` … sürüm eki alır. Eski kayıt
    geçmiş olarak dosyada kalır.
    """
    base = proposal_slug(item)
    records = proposal_records(root, item)
    revision = max((proposal_revision(record, base) for record in records), default=0) + 1
    slug = base if revision == 1 else f"{base}-{revision}"
    return slug, revision


def pending_proposals(root: Path, agent: str | None = None) -> list[dict]:
    """`.kit/proposals` altındaki bekleyen öneriler (ajan süzgeci opsiyonel)."""
    records = load_all_proposals(root)
    return [
        record
        for record in records
        if record.get("status") == "pending"
        and (not agent or record.get("agent") == agent)
    ]


def is_draft_path(path: Path | str) -> bool:
    """Yol `skills/.drafts/...` altındaysa True (taslak canlı değildir)."""
    return ".drafts" in Path(path).parts


def skill_target(root: Path, item: dict) -> str | None:
    """Öğrenimin hedeflediği canlı skill dosyası; yoksa None."""
    change = item.get("proposed_change") or {}
    candidates = [change.get("target"), *(item.get("targets") or [])]
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not (text.startswith("skills/") and text.endswith("SKILL.md")):
            continue
        if is_draft_path(text):
            continue
        if (root / text).is_file():
            return text
    return None


def skill_note_applied(text: str, item: dict) -> str | None:
    """Skill gövdesine öğrenim notunu ekler; not zaten varsa None.

    Bölüm `## Done when`'den **önce** durur: o bölüm skill'in son bölümüdür
    (`delivery/policies/skill-writing.md`).
    """
    note = f"- [öğrenim {item['id']}] {item['summary'][:80]}"
    if note in text:
        return None
    if "## Öğrenimler" in text:
        start = text.index("## Öğrenimler")
        nxt = text.find("\n## ", start + len("## Öğrenimler"))
        head = text[:nxt] if nxt != -1 else text
        tail = text[nxt:].lstrip("\n") if nxt != -1 else ""
        block = head.rstrip("\n") + "\n" + note + "\n"
        return block + ("\n" + tail if tail else "")
    block = f"## Öğrenimler\n{note}\n"
    if "## Done when" in text:
        index = text.index("## Done when")
        head = text[:index].rstrip("\n")
        return f"{head}\n\n{block}\n{text[index:]}"
    return text.rstrip("\n") + "\n\n" + block


def unified_diff(target: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=target,
            tofile=f"{target} (taslak)",
        )
    )


def render_proposal(item: dict, record: dict, diff: str) -> str:
    """Onay bekleyen önerinin issue/PR gövdesi."""
    name = Path(record["target"]).parent.name
    lines = [
        f"## Skill önerisi — {item['id']}",
        "",
        f"**Durum:** onay bekliyor · **Ajan:** {record['agent']} · "
        f"**Tarih:** {record['created']}",
        f"**Hedef:** `{record['target']}` · **Taslak:** `{record['draft']}`",
        "",
        f"**Özet:** {item['summary']}",
        "",
        "### Diff",
        "",
        "```diff",
        diff.rstrip("\n"),
        "```",
        "",
        "### Onay",
        "",
        f"- Onay: `python3 delivery/scripts/learnings.py --accept {record['id']}` "
        f"— canlı skill güncellenir, önceki sürüm "
        f"`.kit/skill-history/{name}/` altında saklanır.",
        f"- Ret: `python3 delivery/scripts/learnings.py --reject {record['id']}` "
        "— taslak silinir, canlı skill değişmez.",
        f"- Geri dönüş: `python3 delivery/scripts/learnings.py --revert {name}`.",
        "",
        "Onaya kadar canlı skill değişmez; kayıt issue yorumunda tutulur.",
    ]
    return "\n".join(lines) + "\n"


def proposal_state_note(status: str) -> str:
    """Öneri durumunun Türkçe karşılığı (rapor/CLI metni)."""
    return {
        "pending": "onay bekliyor",
        "refused": "bekleyen sınırı nedeniyle reddedildi",
        "rejected": "reddedildi",
        "accepted": "onaylandı",
        "stale": "bayat öneri",
    }.get(status, "onay bekliyor")


def write_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")


def proposal_is_current(root: Path, record: dict) -> bool:
    """`pending` kayıt hâlâ geçerli mi: canlı hedef, taslak ve base hash tutuyor mu."""
    target = root / str(record.get("target") or "")
    if not target.is_file() or existing_draft(root, record) is None:
        return False
    base = str(record.get("base_sha256") or "")
    if not base:
        return True
    live = target.read_text(encoding="utf-8")
    return hashlib.sha256(live.encode("utf-8")).hexdigest() == base


def supersede_proposal(root: Path, record: dict) -> None:
    """Bayat `pending` kaydı geçmişe alır: durum `stale`, taslak/gövde temizlenir."""
    slug = str(record.get("id") or "")
    record_path, _, body_path = proposal_files(root, slug)
    for path in (*draft_candidates(root, record), body_path):
        if path.is_file():
            path.unlink()
        remove_draft(path)
    record["status"] = "stale"
    record["stale"] = date.today().isoformat()
    for key in ("draft", "body", "note", "reason"):
        record.pop(key, None)
    write_record(record_path, record)


def propose_one(root: Path, item: dict, agent: str = "developer") -> dict:
    """Seçilen öğrenim için taslak skill + diff + issue gövdesi üretir.

    Canlı skill dosyasına yazmaz. Yalnız gerçekten `pending` ve güncel kayıt
    "onay bekliyor" döndürür; kabul/ret/refused ya da bayat kayıttan sonra aynı
    öğrenim **yeni öneri kimliğiyle** yeniden önerilir (eski kayıt geçmiş
    olarak kalır). Bekleyen öneri sayısı `PENDING_LIMIT` ise yeni öneri
    reddedilir; imleç `status` alanıyla bildirilir ve ret kaydı `--apply`
    beyaz listesini kapatır.
    """
    latest = proposal_for(root, item)
    if latest is not None and latest.get("status") == "pending":
        if proposal_is_current(root, latest):
            return {
                "id": latest["id"],
                "status": "pending",
                "note": f"öneri zaten var (onay bekliyor) — {latest['id']}",
            }
        supersede_proposal(root, latest)
    elif latest is not None and latest.get("status") not in TERMINAL_STATUSES:
        status = str(latest.get("status") or "pending")
        return {
            "id": latest["id"],
            "status": status,
            "note": f"öneri zaten var ({proposal_state_note(status)})",
        }

    slug, revision = next_proposal_slug(root, item)
    record_path, draft_path, body_path = proposal_files(root, slug)
    target = skill_target(root, item)
    if target is None:
        return {"id": slug, "status": "skipped", "note": "skill hedefi yok"}
    live = (root / target).read_text(encoding="utf-8")
    draft = skill_note_applied(live, item)
    if draft is None:
        return {"id": slug, "status": "skipped", "note": "not zaten var"}
    if len(pending_proposals(root, agent)) >= PENDING_LIMIT:
        write_record(
            record_path,
            {
                "demir_kit_version": "2",
                "id": slug,
                "revision": revision,
                "issue_ref": item["id"],
                "class": item.get("class"),
                "kind": (item.get("proposed_change") or {}).get("kind"),
                "target": target,
                "agent": agent,
                "created": date.today().isoformat(),
                "status": "refused",
                "reason": f"bekleyen öneri sınırı {PENDING_LIMIT}",
            },
        )
        return {
            "id": slug,
            "status": "refused",
            "note": f"bekleyen öneri sınırı {PENDING_LIMIT} — canlı dosyaya yazılmaz",
        }

    diff = unified_diff(target, live, draft)
    record = {
        "demir_kit_version": "2",
        "id": slug,
        "revision": revision,
        "issue_ref": item["id"],
        "class": item.get("class"),
        "kind": (item.get("proposed_change") or {}).get("kind"),
        "target": target,
        "draft": draft_path.relative_to(root).as_posix(),
        "body": body_path.relative_to(root).as_posix(),
        "base_sha256": hashlib.sha256(live.encode("utf-8")).hexdigest(),
        "agent": agent,
        "created": date.today().isoformat(),
        "status": "pending",
    }
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(draft, encoding="utf-8")
    body_path.parent.mkdir(parents=True, exist_ok=True)
    body_path.write_text(render_proposal(item, record, diff), encoding="utf-8")
    write_record(record_path, record)
    return {
        "id": slug,
        "status": "pending",
        "target": target,
        "draft": record["draft"],
        "body": record["body"],
        "diff": diff,
    }


def accept_proposal(root: Path, slug: str) -> dict:
    """Öneriyi canlı skill'e uygular; önceki sürümü geçmişe saklar.

    Öneri `base_sha256` taşıyorsa ve canlı skill o tarihten sonra değiştiyse
    onay reddedilir (bayat öneri) — canlı dosya yazılmaz.
    """
    record = load_proposal(root, slug)
    if record is None:
        return {"id": slug, "status": "missing", "note": "öneri yok"}
    if record.get("status") != "pending":
        status = str(record.get("status"))
        return {
            "id": slug,
            "status": status,
            "note": f"onay bekleyen değil ({proposal_state_note(status)})",
        }
    target = root / str(record.get("target") or "")
    if not target.is_file():
        return {"id": slug, "status": "missing", "note": "canlı hedef yok — yeniden --propose"}
    draft_path = existing_draft(root, record)
    if draft_path is None:
        expected = ", ".join(
            f"`{path.relative_to(root).as_posix()}`" for path in draft_candidates(root, record)
        )
        return {
            "id": slug,
            "status": "missing",
            "note": f"taslak yok — {expected} (yeniden --propose)",
        }

    live = target.read_text(encoding="utf-8")
    base = str(record.get("base_sha256") or "")
    if base and hashlib.sha256(live.encode("utf-8")).hexdigest() != base:
        return {
            "id": slug,
            "status": "stale",
            "note": "bayat öneri — canlı skill değişti, yeniden --propose",
        }

    name = target.parent.name
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    archive = history_root(root) / name / f"{stamp}.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text(live, encoding="utf-8")
    target.write_text(draft_path.read_text(encoding="utf-8"), encoding="utf-8")
    remove_draft(draft_path)

    record["status"] = "accepted"
    record["accepted"] = date.today().isoformat()
    record["history"] = archive.relative_to(root).as_posix()
    record.pop("draft", None)
    record.pop("note", None)
    record.pop("reason", None)
    write_record(proposal_files(root, slug)[0], record)
    return {
        "id": slug,
        "status": "accepted",
        "target": record["target"],
        "history": record["history"],
    }


def reject_proposal(root: Path, slug: str) -> dict:
    """Reddedilen öneriyi siler; canlı skill'e dokunmaz.

    Taslak ve issue gövdesi silinir, kayıt `rejected` olarak kalır: `--apply`
    bu öğrenimi canlı dosyaya asla yazmaz.
    """
    record = load_proposal(root, slug)
    if record is None:
        return {"id": slug, "status": "missing", "note": "öneri yok"}
    removed: list[str] = []
    _, _, default_body = proposal_files(root, slug)
    body_path = root / str(record.get("body") or "") if record.get("body") else default_body
    for path in (*draft_candidates(root, record), body_path):
        if path.is_file():
            removed.append(path.relative_to(root).as_posix())
            path.unlink()
        remove_draft(path)
    record["status"] = "rejected"
    record["rejected"] = date.today().isoformat()
    for key in ("draft", "body", "note", "reason"):
        record.pop(key, None)
    write_record(proposal_files(root, slug)[0], record)
    return {
        "id": slug,
        "status": "rejected",
        "removed": removed,
        "target": record.get("target"),
    }


def accepted_target(root: Path, name: str) -> str:
    """`name` skill'i için son onaylanan canlı dosya yolu (yoksa varsayılan)."""
    found: list[tuple[str, str]] = []
    for record in load_all_proposals(root):
        if record.get("status") != "accepted":
            continue
        target = str(record.get("target") or "")
        if Path(target).parent.name == name:
            found.append((str(record.get("accepted") or ""), target))
    if found:
        return sorted(found)[-1][1]
    return f"skills/{name}/SKILL.md"


def revert_skill(root: Path, name: str) -> dict:
    """Saklanan son sürümü canlı skill'e geri yazar; kayıt tüketilir."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", str(name or "")):
        return {"name": str(name), "status": "invalid", "note": "skill adı geçersiz"}
    folder = history_root(root) / name
    entries = sorted(folder.glob("*.md")) if folder.is_dir() else []
    if not entries:
        return {"name": name, "status": "missing", "note": "geçmiş yok"}
    entry = entries[-1]
    target = root / accepted_target(root, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(entry.read_text(encoding="utf-8"), encoding="utf-8")
    entry.unlink()
    return {
        "name": name,
        "status": "reverted",
        "target": target.relative_to(root).as_posix(),
        "history": entry.name,
    }


# ---------------------------------------------------------------- apply

def apply_risk_glob_add(root: Path, item: dict) -> str:
    """registry.yaml risk.auto_escalate.high listesine glob ekler (idempotent)."""
    match = re.search(r"`([\w*./{}-]+)`", item["summary"])
    glob = match.group(1) if match else None
    if not glob:
        return "skip: glob bulunamadı (issue'da `glob` olarak işaretleyin)"
    path = root / "delivery" / "registry.yaml"
    text = path.read_text(encoding="utf-8")
    if f'"{glob}"' in text:
        return "skip: glob zaten var"
    pattern = re.compile(r"(auto_escalate:\n    high:\n(?:      - \"[^\"]+\"\n)*)")
    if not pattern.search(text):
        return "skip: auto_escalate.high bloğu bulunamadı"
    text = pattern.sub(lambda m: m.group(1) + f'      - "{glob}"\n', text, count=1)
    path.write_text(text, encoding="utf-8")
    return f"applied: risk high ← {glob}"


def apply_eval_scenario_add(root: Path, item: dict) -> str:
    """Hedef eval dosyasına senaryo satırı ekler (idempotent)."""
    targets = [t for t in item.get("targets", []) if t.endswith(".md")]
    target = next((t for t in targets if t.startswith("delivery/")), None)
    if not target:
        return "skip: eval hedefi yok (`delivery/agents/<rol>/evals/<x>.md`)"
    path = root / target
    if not path.is_file():
        return f"skip: {target} yok"
    text = path.read_text(encoding="utf-8")
    row = f"| L-{item['id']} | {item['summary'][:60]} | Öğrenim senaryosu | Öğrenim kaydı |"
    if row in text:
        return "skip: senaryo zaten var"
    path.write_text(text.rstrip("\n") + "\n" + row + "\n", encoding="utf-8")
    return f"applied: eval ← {target}"


def apply_skill_note_add(root: Path, item: dict) -> str:
    """Hedef SKILL.md'ye öğrenim notu ekler (idempotent)."""
    targets = [t for t in item.get("targets", []) if "SKILL" in t or t.startswith("skills/")]
    target = next(
        (t for t in targets if not is_draft_path(t) and (root / t).is_file()),
        None,
    )
    if not target:
        return "skip: SKILL.md hedefi yok (`skills/<ad>/SKILL.md`)"
    path = root / target
    updated = skill_note_applied(path.read_text(encoding="utf-8"), item)
    if updated is None:
        return "skip: not zaten var"
    path.write_text(updated, encoding="utf-8")
    return f"applied: skill notu ← {target}"


APPLIERS = {
    "risk_glob_add": apply_risk_glob_add,
    "eval_scenario_add": apply_eval_scenario_add,
    "skill_note_add": apply_skill_note_add,
}


def bump_patch(version: str) -> str:
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def add_changelog(root: Path, version: str, bullet: str) -> None:
    path = root / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    entry = f"## {version} — {date.today().isoformat()}\n\n- **Öğrenim** — {bullet}\n"
    text = text.replace("# Changelog\n\n", f"# Changelog\n\n{entry}\n", 1)
    path.write_text(text, encoding="utf-8")
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")


def apply_all(root: Path, digest_path: Path | None = None) -> list[str]:
    path = digest_path or DIGEST
    items = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    actions: list[str] = []
    applied_any = False
    for item in items:
        change = item["proposed_change"]
        kind = change["kind"]
        proposal = proposal_for(root, item)
        if proposal is not None:
            status = str(proposal.get("status") or "pending")
            actions.append(
                f"{status}: {item['id']} — {proposal_state_note(status)} "
                f"({proposal.get('id')}) canlı dosyaya yazılmaz"
            )
            continue
        if kind not in AUTO_KINDS or not change.get("auto"):
            actions.append(f"manual: {item['id']} ({kind}) — issue açılmalı")
            item["status"] = "escalated" if item["status"] == "candidate" else item["status"]
            continue
        result = APPLIERS[kind](root, item)
        actions.append(f"{item['id']}: {result}")
        if result.startswith("applied:"):
            applied_any = True
            item["status"] = "applied"

    if applied_any:
        current = (root / "VERSION").read_text(encoding="utf-8").strip()
        new_version = bump_patch(current)
        add_changelog(root, new_version, "federasyon uygulaması — detay `.orchestration/learnings/`")
        actions.append(f"version: {current} → {new_version} (doctor.sh --strict koşun)")

    path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    return actions


# ---------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description="demir-kit learnings")
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--harvest", action="store_true")
    parser.add_argument("--digest", action="store_true")
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--propose", action="store_true", help="taslak skill önerisi")
    parser.add_argument("--list", dest="list_proposals", action="store_true")
    parser.add_argument("--accept", metavar="ID", help="öneriyi canlı skill'e uygula")
    parser.add_argument("--reject", metavar="ID", help="öneriyi sil")
    parser.add_argument("--revert", metavar="SKILL", help="son onayı geri al")
    parser.add_argument("--agent", default=None, help="öneri sahibi (varsayılan developer)")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    root = args.project.resolve()
    run_all = args.all
    agent = args.agent or "developer"

    if args.harvest or run_all:
        records = harvest(root)
        print(f"harvest: {len(records)} kayıt")
    else:
        records = json.loads(RECORDS.read_text(encoding="utf-8")) if RECORDS.is_file() else []

    if args.digest or run_all:
        items = digest(records)
        candidates = [i for i in items if i["status"] == "candidate"]
        print(f"digest: {len(items)} küme · {len(candidates)} genel kural adayı")
        for item in candidates:
            print(f"  - {item['id']} ×{item['occurrences']} → {item['proposed_change']['kind']}")

    if args.emit or run_all:
        items = json.loads(DIGEST.read_text(encoding="utf-8")) if DIGEST.is_file() else []
        for item in items:
            if item["status"] in ("candidate", "escalated"):
                print("---")
                print(render_issue(item))

    if args.propose:
        items = json.loads(DIGEST.read_text(encoding="utf-8")) if DIGEST.is_file() else []
        proposed = False
        for item in items:
            # `proposed` da taranır: terminal/bayat kayıt yeni kimlikle açılabilir.
            if item.get("status") not in ("candidate", "escalated", "proposed"):
                continue
            result = propose_one(root, item, agent)
            note = f" — {result['note']}" if result.get("note") else ""
            print(f"propose: {result['id']} → {result['status']}{note}")
            if result["status"] == "pending":
                proposed = True
                print((root / result["body"]).read_text(encoding="utf-8"))
                item["status"] = "proposed"
        if proposed and DIGEST.is_file():
            DIGEST.write_text(
                json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    if args.apply or run_all:
        for line in apply_all(root):
            print(line)

    if args.list_proposals:
        pending = pending_proposals(root, args.agent)
        print(f"bekleyen öneri: {len(pending)}/{PENDING_LIMIT}")
        for record in pending:
            print(
                f"  - {record.get('id')} · {record.get('agent')} · "
                f"{record.get('target')} · {record.get('created')}"
            )

    if args.accept:
        result = accept_proposal(root, args.accept)
        print(
            f"accept: {result['id']} → {result['status']}"
            + (f" — {result['note']}" if result.get("note") else "")
        )
        if result.get("history"):
            print(f"  önceki sürüm: {result['history']}")
    if args.reject:
        result = reject_proposal(root, args.reject)
        print(f"reject: {result['id']} → {result['status']}")
        for path in result.get("removed", []):
            print(f"  silindi: {path}")
    if args.revert:
        result = revert_skill(root, args.revert)
        print(
            f"revert: {result['name']} → {result['status']}"
            + (f" — {result['note']}" if result.get("note") else "")
        )
        if result.get("target"):
            print(f"  yazıldı: {result['target']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())