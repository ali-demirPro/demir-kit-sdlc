"""`doctor --explain` helpers (extracted from doctor.py).

doctor.py only builds the name -> check-function mapping and forwards the
flag; summaries, mode rules, source resolution and gate provenance live here.
`source_of` reports where the check function is defined, so the output stays
`delivery/scripts/doctor.py:<line>` after the split.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import profiles  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# Çıktı sırası; adlar check_* fonksiyonlarının kebab-case karşılığıdır.
CHECK_NAMES = (
    "files",
    "schemas",
    "registry",
    "rigor",
    "capabilities",
    "profiles",
    "agent-variants",
    "labels",
    "links",
    "legacy",
    "version",
    "ecosystem",
    "fleet",
    "skills",
    "role-contracts",
    "mcp",
    "compat",
    "worktree",
    "installed-skills",
    "model-policy",
    "unsealed-work",
    "product",
)

# Adlandırma kuralına uymayan tek kontrol.
CHECK_ALIASES = {"worktree": "check_worktree_management"}

SUMMARIES = {
    "files": "Zorunlu dosyaların repoda bulunduğunu doğrular.",
    "schemas": "JSON şemalarının $schema/object kökünü ve frequency.yaml şeklini doğrular.",
    "registry": "registry.yaml yol, sinyal ve agent dizinlerini doğrular.",
    "rigor": "rigor.yaml'ı şemaya ve etkin yapılandırmaya göre doğrular.",
    "capabilities": "Capability registry ile rol matrisini şemaya göre doğrular.",
    "profiles": "Profil tanımlarını ve proje profil seçimini doğrular.",
    "agent-variants": "Agent varyant dosyalarını capability matrisine göre doğrular.",
    "labels": "Kanonal etiketlerin registry ve GitHub şablonuyla uyumunu doğrular.",
    "links": "Markdown linklerini ve backtick'li yolları denetler.",
    "legacy": "Arşiv (archive/) referanslarını uyarı olarak raporlar.",
    "version": "VERSION, CHANGELOG ve README sürümlerini hizalar.",
    "ecosystem": (
        "ecosystem.yaml ürün yüzeylerini ve kit.config protokolünü doğrular."
    ),
    "fleet": "fleet.yaml repo listesini doğrular.",
    "skills": "SKILL.md ad tekilliğini ve runtime/scoped kayıtlarını doğrular.",
    "role-contracts": "Rol sözleşmelerinin registry sırasıyla uyumunu doğrular.",
    "mcp": "MCP sunucusunu başlatır ve araç listesini doğrular.",
    "compat": "Orca komut, flag ve yanıt şekillerini denetler.",
    "worktree": "Checkout'un Orca tarafından açıldığını doğrular.",
    "installed-skills": "Kurulu skill kopyalarının kaynakla aynı olduğunu doğrular.",
    "model-policy": "kit.config orca model/effort politikasını doğrular.",
    "unsealed-work": "Mühürsüz iş kalıntılarını raporlar.",
    "product": "Ürün reposunun kit pinini ve yapılandırmasını doğrular.",
}

# İki modda da çalışan kontroller; kalanlar yalnız kit modunda çalışır.
BOTH_MODE_CHECKS = {"worktree", "installed-skills", "model-policy", "unsealed-work"}
REASON_KIT_ONLY = "yalnız kit modu"
REASON_PRODUCT_ONLY = "yalnız --product"


def checks(scope: dict) -> dict:
    """Ad -> doctor.py'deki kontrol fonksiyonu; eksik fonksiyon import'ta patlar."""
    return {
        name: scope[CHECK_ALIASES.get(name, "check_" + name.replace("-", "_"))]
        for name in CHECK_NAMES
    }


def source_of(func) -> str:
    """Fonksiyonun tanımlı olduğu dosya:satır (repo-göreli, asla mutlak değil)."""
    try:
        path = Path(inspect.getsourcefile(func) or "")
        line = inspect.getsourcelines(func)[1]
        relative = path.resolve().relative_to(ROOT)
    except (OSError, TypeError, ValueError):
        return ""
    return f"{relative.as_posix()}:{line}"


def is_enabled(name: str, product: bool) -> tuple[bool, str]:
    if name == "product":
        return (True, "") if product else (False, REASON_PRODUCT_ONLY)
    if product and name not in BOTH_MODE_CHECKS:
        return False, REASON_KIT_ONLY
    return True, ""


def gates(root: Path) -> int:
    """Etkin gate setini ve her değerin kaynağını yazdırır."""
    print("explain: gates")
    try:
        data = profiles.resolve(root)
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    profile = data.get("profile") or {}
    name = str(profile.get("value") or "")
    print(f"profile: {name or '-'}")
    print(f"profile_source: {profile.get('source') or '-'}")
    if not name:
        print("gates: []")
        print("note: profil yapılandırması yok")
        return 0
    items = data.get("gates") or []
    print(f"gates: {len(items)}")
    for gate in items:
        print(f"gate: {gate.get('value')} source={gate.get('source') or '-'}")
    return 0


def explain(name: str, checks: dict, root: Path, product: bool = False) -> int:
    """Tek kontrolün modunu ve kural kaynağını açıklar; kontrol çalıştırmaz."""
    if name == "gates":
        return gates(root)
    func = checks.get(name) if name else None
    if func is None:
        label = name or "(boş ad)"
        print(f"bilinmeyen kontrol: {label}", file=sys.stderr)
        print("kullanılabilir: gates, " + ", ".join(checks), file=sys.stderr)
        return 2
    enabled, reason = is_enabled(name, product)
    print(f"explain: {name}")
    print(f"enabled: {'true' if enabled else 'false'}")
    if reason:
        print(f"reason: {reason}")
    print(f"source: {source_of(func)}")
    print(f"summary: {SUMMARIES.get(name, '')}")
    print(f"mode: {'product' if product else 'kit'}")
    return 0
