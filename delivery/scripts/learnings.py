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

`--propose` canlı skill'e yazmaz: taslak + diff `.kit/proposals/` altında durur,
ajan başına en fazla `PENDING_LIMIT` öneri bekler. Onayda önceki sürüm
`.kit/skill-history/<skill>/` altında saklanır, `--revert` geri yazar.
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


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def proposal_slug(item: dict) -> str:
    return slugify(f"{item.get('class', 'learning')}-{item['id']}")


def proposal_files(root: Path, slug: str) -> tuple[Path, Path, Path]:
    """Öneri kaydı, taslak skill ve issue gövdesi yolları."""
    base = root / ".kit" / "proposals"
    return base / f"{slug}.json", base / f"{slug}.draft.md", base / f"{slug}.md"


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


def pending_proposals(root: Path, agent: str | None = None) -> list[dict]:
    """`.kit/proposals` altındaki bekleyen öneriler (ajan süzgeci opsiyonel)."""
    base = root / ".kit" / "proposals"
    if not base.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(base.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict) or record.get("status") != "pending":
            continue
        if agent and record.get("agent") != agent:
            continue
        out.append(record)
    return out


def skill_target(root: Path, item: dict) -> str | None:
    """Öğrenimin hedeflediği canlı skill dosyası; yoksa None."""
    change = item.get("proposed_change") or {}
    candidates = [change.get("target"), *(item.get("targets") or [])]
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not (text.startswith("skills/") and text.endswith("SKILL.md")):
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


def propose_one(root: Path, item: dict, agent: str = "developer") -> dict:
    """Seçilen öğrenim için taslak skill + diff + issue gövdesi üretir.

    Canlı skill dosyasına yazmaz. Bekleyen öneri sayısı `PENDING_LIMIT` ise
    yeni öneri reddedilir; imleç `status` alanıyla bildirilir.
    """
    slug = proposal_slug(item)
    existing = load_proposal(root, slug)
    if existing:
        return {
            "id": slug,
            "status": str(existing.get("status") or "existing"),
            "note": "öneri zaten var",
        }
    target = skill_target(root, item)
    if target is None:
        return {"id": slug, "status": "skipped", "note": "skill hedefi yok"}
    live = (root / target).read_text(encoding="utf-8")
    draft = skill_note_applied(live, item)
    if draft is None:
        return {"id": slug, "status": "skipped", "note": "not zaten var"}
    if len(pending_proposals(root, agent)) >= PENDING_LIMIT:
        return {
            "id": slug,
            "status": "refused",
            "note": f"bekleyen öneri sınırı {PENDING_LIMIT}",
        }

    record_path, draft_path, body_path = proposal_files(root, slug)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    diff = unified_diff(target, live, draft)
    record = {
        "demir_kit_version": "2",
        "id": slug,
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
    draft_path.write_text(draft, encoding="utf-8")
    body_path.write_text(render_proposal(item, record, diff), encoding="utf-8")
    record_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "id": slug,
        "status": "pending",
        "target": target,
        "draft": record["draft"],
        "body": record["body"],
        "diff": diff,
    }


def accept_proposal(root: Path, slug: str) -> dict:
    """Öneriyi canlı skill'e uygular; önceki sürümü geçmişe saklar."""
    record = load_proposal(root, slug)
    if record is None:
        return {"id": slug, "status": "missing", "note": "öneri yok"}
    if record.get("status") != "pending":
        return {
            "id": slug,
            "status": str(record.get("status")),
            "note": "onay bekleyen değil",
        }
    target = root / str(record.get("target") or "")
    draft_path = root / str(record.get("draft") or "")
    if not target.is_file() or not draft_path.is_file():
        return {"id": slug, "status": "missing", "note": "hedef veya taslak yok"}

    name = target.parent.name
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    archive = history_root(root) / name / f"{stamp}.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    target.write_text(draft_path.read_text(encoding="utf-8"), encoding="utf-8")

    record["status"] = "accepted"
    record["accepted"] = date.today().isoformat()
    record["history"] = archive.relative_to(root).as_posix()
    proposal_files(root, slug)[0].write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "id": slug,
        "status": "accepted",
        "target": record["target"],
        "history": record["history"],
    }


def reject_proposal(root: Path, slug: str) -> dict:
    """Reddedilen öneriyi siler; canlı skill'e dokunmaz."""
    record = load_proposal(root, slug)
    if record is None:
        return {"id": slug, "status": "missing", "note": "öneri yok"}
    removed: list[str] = []
    for path in proposal_files(root, slug):
        if path.is_file():
            path.unlink()
            removed.append(path.relative_to(root).as_posix())
    return {
        "id": slug,
        "status": "rejected",
        "removed": removed,
        "target": record.get("target"),
    }


def accepted_target(root: Path, name: str) -> str:
    """`name` skill'i için son onaylanan canlı dosya yolu (yoksa varsayılan)."""
    base = root / ".kit" / "proposals"
    found: list[tuple[str, str]] = []
    if base.is_dir():
        for path in sorted(base.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict) or record.get("status") != "accepted":
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
    target = next((t for t in targets if (root / t).is_file()), None)
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
        pending = load_proposal(root, proposal_slug(item))
        if pending and pending.get("status") == "pending":
            actions.append(
                f"pending: {item['id']} — onay bekleyen taslak "
                f"({pending.get('id')}) canlı dosyaya yazılmaz"
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
            if item.get("status") not in ("candidate", "escalated"):
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