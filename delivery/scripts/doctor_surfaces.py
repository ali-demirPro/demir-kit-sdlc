"""Surface gate contract for ecosystem.yaml (extracted from doctor.py).

The UI rule is graded by the evidence the project declares:

- `ui_compare` absent or `none`: no comparison exists yet, so a missing
  `snapshot` command is a warning. The product is not forced to claim
  `ui: false` (a lie about the surface) or to patch the kit.
- a real comparison mode (`screenshot`, `pixel`, …) without `snapshot`: error.
- the same case with a valid, dated `ui_waiver`: warning until that date.
- an expired or malformed waiver: error.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

WAIVER_MAX_DAYS = 180


def _today() -> date:
    """UTC today: dev machines and CI must agree on a waiver's last day."""
    return datetime.now(timezone.utc).date()


def _parse_day(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def waiver_state(gates: dict, today: date) -> tuple[str, str]:
    """Classify `gates.ui_waiver`: ('none'|'valid'|'expired'|'invalid', message)."""
    waiver = gates.get("ui_waiver")
    if waiver is None:
        return "none", ""
    if not isinstance(waiver, dict):
        return "invalid", "gates.ui_waiver mapping olmalı"
    reason = waiver.get("reason")
    issue = waiver.get("issue")
    until = _parse_day(waiver.get("until"))
    if not isinstance(reason, str) or not reason.strip():
        return "invalid", "gates.ui_waiver reason (string) ister"
    if not isinstance(issue, int) or isinstance(issue, bool) or issue < 1:
        return "invalid", "gates.ui_waiver issue (pozitif tam sayı) ister"
    if until is None:
        return "invalid", "gates.ui_waiver until YYYY-MM-DD olmalı"
    if (until - today).days > WAIVER_MAX_DAYS:
        return (
            "invalid",
            f"gates.ui_waiver en fazla {WAIVER_MAX_DAYS} gün ileri olabilir",
        )
    if until < today:
        return "expired", f"UI snapshot muafiyeti süresi doldu ({until.isoformat()})"
    return "valid", f"UI snapshot muafiyeti {until.isoformat()} tarihine kadar (issue #{issue}): {reason.strip()}"


def surface_gate_errors(
    product: str,
    surface: str,
    spec: dict,
    today: date | None = None,
) -> list[str]:
    """Blocking gate problems for one surface."""
    today = today or _today()
    errors: list[str] = []
    gates = (spec or {}).get("gates") or {}
    prefix = f"ecosystem.{product}.{surface}"
    if not gates.get("behavior"):
        errors.append(f"{prefix}: gates.behavior yok")
    if not isinstance(gates.get("ui"), (bool, type(None))):
        errors.append(f"{prefix}: gates.ui boolean olmalı")
    if not isinstance(gates.get("ui_compare"), (str, type(None))):
        errors.append(f"{prefix}: gates.ui_compare string olmalı")
    for key in ("selftest", "snapshot", "behavior"):
        value = gates.get(key)
        if value is not None and not isinstance(value, str):
            errors.append(f"{prefix}: gates.{key} string olmalı")
    pages = gates.get("snapshot_pages")
    if pages is not None and not isinstance(pages, list):
        errors.append(f"{prefix}: gates.snapshot_pages liste olmalı")

    if gates.get("ui") is not True:
        return errors

    state_any, message_any = waiver_state(gates, today)
    if gates.get("snapshot"):
        if state_any == "expired":
            errors.append(f"{prefix}: {message_any}")
        elif state_any == "invalid":
            errors.append(f"{prefix}: {message_any}")
        return errors

    compare = str(gates.get("ui_compare") or "none").strip().lower()
    state, message = waiver_state(gates, today)
    if state == "expired":
        errors.append(f"{prefix}: {message}")
    elif state == "invalid":
        errors.append(f"{prefix}: {message}")
    elif state == "none" and compare not in {"", "none"}:
        errors.append(
            f"{prefix}: gates.ui açık ama gates.snapshot yok "
            "(görsel kanıt olmadan UI gate koşamaz)"
        )
    return errors


def surface_gate_warnings(
    product: str,
    surface: str,
    spec: dict,
    today: date | None = None,
) -> list[str]:
    """Non-blocking gate gaps for one surface."""
    today = today or _today()
    gates = (spec or {}).get("gates") or {}
    prefix = f"ecosystem.{product}.{surface}"
    if gates.get("ui") is not True:
        return []
    state, message = waiver_state(gates, today)
    if gates.get("snapshot"):
        if state == "valid":
            return [
                f"{prefix}: snapshot tanımlı; {message} artık gereksiz — kaldır"
            ]
        return []
    compare = str(gates.get("ui_compare") or "none").strip().lower()
    if state == "valid":
        return [f"{prefix}: {message}"]
    if compare in {"", "none"}:
        return [
            f"{prefix}: gates.ui açık ama ui_compare yok ve snapshot komutu yok "
            "— UI gate henüz kanıt üretmiyor"
        ]
    return []


def surface_gate_messages(
    product: str,
    surface: str,
    spec: dict,
    on_error,
    on_warn,
    today: date | None = None,
) -> None:
    """Record errors and warnings for one surface (single path for kit+product)."""
    for message in surface_gate_errors(product, surface, spec, today=today):
        on_error(message)
    for message in surface_gate_warnings(product, surface, spec, today=today):
        on_warn(message)
