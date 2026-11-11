"""One ``project_root`` contract shared by delivery scripts.

Epic D decision D1: the directory that owns project state is the git common
root when it carries ``kit.config.yaml``. A linked worktree shares that common
root with the main checkout, so a script called from a worktree resolves the
main checkout — never the worktree itself. When the common root is not a
project, an explicit ``project`` wins; the kit root is the last resort.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

CONFIG_NAME = "kit.config.yaml"


def _git(cwd: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    return text or None


def git_common_root(project: Path | str | None = None) -> Path | None:
    """Root of the git common directory; stable from a linked worktree."""
    current = Path(project) if project is not None else Path.cwd()
    text = _git(
        current, ["rev-parse", "--path-format=absolute", "--git-common-dir"]
    )
    if not text:
        return None
    common = Path(text)
    if not common.is_absolute():
        common = (current / common).resolve()
    return common.parent if common.name == ".git" else common


def checkout_root(project: Path | str | None = None) -> Path:
    """The current checkout (worktree when linked); session/report scoped.

    This is deliberately not :func:`project_root`: session directories belong
    to the tree a worker runs in, while state belongs to the main checkout.
    """
    current = Path(project) if project is not None else Path.cwd()
    text = _git(current, ["rev-parse", "--show-toplevel"])
    return Path(text) if text else current


def project_root(
    kit_root: Path | str,
    project: Path | str | None = None,
    *,
    env_override: str | None = None,
) -> Path:
    """Resolve the directory that owns ``.kit/`` and ``.orchestration/``.

    1. git common root when it carries ``kit.config.yaml`` (main checkout from
       a linked worktree);
    2. the explicit project (or the current directory) when it carries
       ``kit.config.yaml``;
    3. ``kit_root``.
    """
    if env_override:
        override = os.environ.get(env_override)
        if override:
            return Path(override)
    current = Path(project) if project is not None else Path.cwd()
    common = git_common_root(current)
    if common and (common / CONFIG_NAME).is_file():
        return common
    if (current / CONFIG_NAME).is_file():
        return current
    return Path(kit_root)
