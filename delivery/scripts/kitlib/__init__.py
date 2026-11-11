"""Shared core for delivery scripts.

The package owns the single copies of the rules scripts used to duplicate:

- :mod:`kitlib.root` — one ``project_root`` contract,
- :mod:`kitlib.config` — ``kit.config.yaml`` / ``ecosystem.yaml`` loading,
- :mod:`kitlib.gh` — ``gh`` call templates and pagination,
- :mod:`kitlib.yamlish` — fenced YAML block parsing,
- :mod:`kitlib.comments` — issue comment identity, posting and deletion.
"""

from __future__ import annotations

__all__ = ["comments", "config", "gh", "root", "yamlish"]
