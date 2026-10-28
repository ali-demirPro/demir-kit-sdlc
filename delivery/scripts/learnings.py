#!/usr/bin/env python3
"""demir-kit learnings — fleet öğrenim federasyonu (self-improvement lane).

Hedef projelerdeki `learning` issue'ları ve closure metriklerini hasat eder,
normalize edip 2+ projede tekrar eden dersleri genel kural adayına dönüştürür.
Beyaz listedeki **ekleme** sınıfı değişiklikler otomatik uygulanır; kural
azaltma/silme ve kod değişikliği otomatik yazılmaz (I13 kapsamı: ürün teslimatı;
kit self-improvement lane'de kabul doctor + testtir).

Usage:
  python3 delivery/scripts/learnings.py --harvest [--project .]
  python3 delivery/scripts/learnings.py --digest
  python3 delivery/scripts/learnings.py --emit
  python3 delivery/scripts/learnings.py --apply
  python3 delivery/scripts/learnings.py --all
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
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
    text = path.read_text(encoding="utf-8")
    note = f"- [öğrenim {item['id']}] {item['summary'][:80]}"
    if note in text:
        return "skip: not zaten var"
    if "## Öğrenimler" not in text:
        text = text.rstrip("\n") + "\n\n## Öğrenimler\n"
    path.write_text(text.rstrip("\n") + "\n" + note + "\n", encoding="utf-8")
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


def apply_all(root: Path) -> list[str]:
    items = json.loads(DIGEST.read_text(encoding="utf-8")) if DIGEST.is_file() else []
    actions: list[str] = []
    applied_any = False
    for item in items:
        change = item["proposed_change"]
        kind = change["kind"]
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

    DIGEST.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    return actions


# ---------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description="demir-kit learnings")
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--harvest", action="store_true")
    parser.add_argument("--digest", action="store_true")
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    root = args.project.resolve()
    run_all = args.all

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

    if args.apply or run_all:
        for line in apply_all(root):
            print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())