"""Surface gate contract for ecosystem.yaml (extracted from doctor.py)."""

from __future__ import annotations


def surface_gate_errors(product: str, surface: str, spec: dict) -> list[str]:
    """Gate contract for one surface: behavior always, snapshot for UI."""
    errors: list[str] = []
    gates = (spec or {}).get("gates") or {}
    prefix = f"ecosystem.{product}.{surface}"
    if not gates.get("behavior"):
        errors.append(f"{prefix}: gates.behavior yok")
    if gates.get("ui") is True and not gates.get("snapshot"):
        errors.append(
            f"{prefix}: gates.ui açık ama gates.snapshot yok "
            "(görsel kanıt olmadan UI gate koşamaz)"
        )
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
    return errors
