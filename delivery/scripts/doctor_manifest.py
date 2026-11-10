"""Product kit manifest reporting for `doctor --product`.

Kept out of doctor.py so the main module stays within its split budget.
The check is read-only: `vendor_sync.check_manifest` reads the vendored
KIT-MANIFEST.json and the local bytes, nothing else.
"""

from __future__ import annotations

from pathlib import Path

import vendor_sync


def report(kit_path: Path, error, warn) -> None:
    """Print/report the offline digest layer; never replaces the commit pin."""
    result = vendor_sync.check_manifest(kit_path)
    status = result.get("status")
    if status == "pass":
        print(f"kit pin: manifest digest ok ({result.get('files')} dosya)")
        return
    if status == "not_run":
        print(f"kit pin: manifest digest not_run — {result.get('reason')}")
        warn(f"kit manifest doğrulanamadı (not_run): {result.get('reason')}")
        return
    if status == "invalid":
        detail = "; ".join(result.get("errors") or []) or str(result.get("reason"))
        print(f"kit pin: manifest digest fail — {detail}")
        error(f"kit manifest geçersiz: {detail}")
        return
    if status != "fail":
        print(f"kit pin: manifest digest error — bilinmeyen durum {status!r}")
        error(f"kit manifest: bilinmeyen durum {status!r}")
        return
    missing = result.get("missing") or []
    extra = result.get("extra") or []
    changed = result.get("changed") or []
    print(
        "kit pin: manifest digest fail — "
        f"{len(missing)} eksik, {len(extra)} fazla, {len(changed)} değişmiş"
    )
    for path in missing:
        error(f"kit manifest: eksik dosya {path}")
    for path in extra:
        error(f"kit manifest: fazladan dosya {path}")
    for item in changed:
        error(
            f"kit manifest: değişmiş dosya {item['path']} — beklenen "
            f"{item['expected']} gerçek {item['actual']}"
        )
