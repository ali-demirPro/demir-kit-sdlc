#!/usr/bin/env python3
"""Model selection policy: the user/session owns the model.

Default: the kit passes no ``--model``/``--effort``; workers use the
environment default. ``orca.inherit_session_model: true`` opts into passing the
coordinator session model. ``orca.role_defaults`` model/effort only applies with
``orca.allow_model_override: true`` (doctor enforces it).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import usage  # noqa: E402


def load_config(project: Path) -> dict:
    try:
        data = yaml.safe_load((project / "kit.config.yaml").read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def main_checkout(project: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=str(project),
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return project
    if result.returncode != 0:
        return project
    common = Path(result.stdout.strip())
    candidate = common.parent
    return candidate if candidate.is_dir() else project


def session_model(project: Path) -> str | None:
    try:
        session = usage.current_session(main_checkout(project))
        info = usage.api_session_info(str(session.get("id")))
    except (SystemExit, ValueError, json.JSONDecodeError):
        return None
    model = info.get("model") or {}
    model_id = str(model.get("id") or "")
    if not model_id:
        return None
    provider = str(model.get("providerID") or "")
    return f"{provider}/{model_id}" if provider else model_id


def role_launch(project: Path, role: str) -> dict:
    config = load_config(project)
    orca = config.get("orca") if isinstance(config.get("orca"), dict) else {}
    defaults = (orca.get("role_defaults") or {}).get(role) or {}
    launch: dict[str, str] = {}
    if isinstance(defaults, dict):
        for key in ("model", "effort", "agent"):
            if defaults.get(key):
                launch[key] = str(defaults[key])
    if launch.get("model") or launch.get("effort"):
        if orca.get("allow_model_override") is not True:
            launch.pop("model", None)
            launch.pop("effort", None)
    if not launch.get("model") and orca.get("inherit_session_model") is True:
        inherited = session_model(project)
        if inherited:
            launch["model"] = inherited
    return launch
