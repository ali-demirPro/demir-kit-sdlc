#!/usr/bin/env python3
"""Fail-closed process gate: dirty source work and local hooks."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

HOOK_MARKER = "# demir-kit:hook"


def _run(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            args, cwd=str(cwd), capture_output=True, text=True
        )
    except (FileNotFoundError, OSError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def app_paths(root: Path) -> list[str]:
    paths: set[str] = set()
    try:
        eco = yaml.safe_load((root / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError):
        eco = {}
    for product in (eco.get("products") or {}).values():
        if not isinstance(product, dict):
            continue
        for surface in (product.get("surfaces") or {}).values():
            if isinstance(surface, dict) and surface.get("path"):
                paths.add(str(surface["path"]).strip("/"))
    try:
        config = yaml.safe_load((root / "kit.config.yaml").read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError):
        config = {}
    for item in ((config.get("factory") or {}).get("app_paths") or []):
        paths.add(str(item).strip("/"))
    return sorted(path for path in paths if path)


def _matches(path: str, roots: list[str]) -> bool:
    lowered = path.casefold()
    return any(
        lowered == root.casefold() or lowered.startswith(root.casefold() + "/")
        for root in roots
    )


def dirty_sources(root: Path) -> list[str]:
    paths = app_paths(root)
    if not paths:
        return []
    raw = _run(["git", "status", "--porcelain", "-uall"], root)
    dirty: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        changed = line[3:].strip()
        if " -> " in changed:
            changed = changed.split(" -> ", 1)[1].strip()
        changed = changed.strip('"')
        if _matches(changed, paths):
            dirty.append(changed)
    return dirty


def current_branch(root: Path) -> str:
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root).strip()
    if branch and branch != "HEAD":
        return branch
    return _run(["git", "symbolic-ref", "--short", "HEAD"], root).strip()


def hooks_dir(root: Path) -> Path | None:
    raw = _run(["git", "rev-parse", "--git-path", "hooks"], root).strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _pre_commit(kit_dir: Path) -> str:
    return f"""#!/usr/bin/env bash
{HOOK_MARKER} pre-commit
set -euo pipefail
kit="{kit_dir}"
branch="$(git branch --show-current 2>/dev/null || true)"
if [[ "$branch" =~ epic-([0-9]+) ]]; then
  exec "$kit/delivery/scripts/guard.sh" --issue "${{BASH_REMATCH[1]}}" --staged
fi
exec "$kit/delivery/scripts/guard.sh" --staged
"""


def _pre_push() -> str:
    return f"""#!/usr/bin/env bash
{HOOK_MARKER} pre-push
set -euo pipefail
branch="$(git branch --show-current 2>/dev/null || true)"
if [[ "$branch" == "main" || "$branch" == "master" ]]; then
  echo "demir-kit: main'e dogrudan push yasak; epic PR kullan." >&2
  exit 1
fi
"""


def install_hooks(root: Path, kit_prefix: str = "demir-kit") -> dict:
    hooks = hooks_dir(root)
    if not hooks:
        return {"written": [], "skipped": []}
    hooks.mkdir(parents=True, exist_ok=True)
    kit_dir = (root / kit_prefix).resolve() if kit_prefix else root.resolve()
    written: list[str] = []
    skipped: list[str] = []
    for name, content in (
        ("pre-commit", _pre_commit(kit_dir)),
        ("pre-push", _pre_push()),
    ):
        path = hooks / name
        if path.is_file() and HOOK_MARKER not in path.read_text(
            encoding="utf-8", errors="ignore"
        ):
            skipped.append(str(path))
            continue
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            continue
        path.write_text(content, encoding="utf-8")
        os.chmod(path, 0o755)
        written.append(str(path))
    return {"written": written, "skipped": skipped}


def missing_hooks(root: Path) -> list[str]:
    hooks = hooks_dir(root)
    if not hooks:
        return []
    missing: list[str] = []
    for name in ("pre-commit", "pre-push"):
        path = hooks / name
        if not path.is_file():
            missing.append(name)
        elif HOOK_MARKER not in path.read_text(encoding="utf-8", errors="ignore"):
            missing.append(name)
    return missing


def unsealed_report(root: Path, is_ci: bool = False) -> tuple[list[str], list[str]]:
    dirty = dirty_sources(root)
    errors: list[str] = []
    warnings: list[str] = []
    if dirty:
        branch = current_branch(root) or "?"
        detail = ", ".join(dirty[:5]) + (" …" if len(dirty) > 5 else "")
        message = f"{len(dirty)} kaynak dosyası kirli ('{branch}'): {detail}"
        if branch in {"main", "master"}:
            errors.append(
                message + " — epic/leaf aç veya epic worktree'sine taşı"
            )
        elif "epic-" not in branch:
            warnings.append(message)
    try:
        config = yaml.safe_load((root / "kit.config.yaml").read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError):
        config = {}
    kit_root = str((config.get("kit") or {}).get("root") or ".")
    if not is_ci and kit_root not in {".", ""} and missing_hooks(root):
        warnings.append("pre-commit/pre-push hook yok — `init.py --apply` ile kur")
    return errors, warnings
