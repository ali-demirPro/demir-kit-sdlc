"""Config loading shared by delivery scripts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_NAME = "kit.config.yaml"
ECOSYSTEM_NAME = "ecosystem.yaml"


def read_yaml(path: Path) -> dict:
    """Parse a YAML mapping; parse and IO errors stay visible to the caller."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def load_optional(path: Path) -> dict:
    """Parse when the file exists and is valid; otherwise the empty mapping."""
    try:
        return read_yaml(path)
    except (OSError, yaml.YAMLError):
        return {}


def kit_config(project: Path) -> dict:
    return load_optional(Path(project) / CONFIG_NAME)


def ecosystem(project: Path) -> dict:
    return load_optional(Path(project) / ECOSYSTEM_NAME)


def tracker_repo(project: Path) -> str | None:
    repo: Any = (ecosystem(project).get("tracker") or {}).get("repo")
    return str(repo) if repo else None


def kit_root_name(project: Path) -> str:
    """Vendored kit path inside a product; ``demir-kit`` is the default name."""
    root = (kit_config(project).get("kit") or {}).get("root") or "demir-kit"
    return str(root).strip("/")
