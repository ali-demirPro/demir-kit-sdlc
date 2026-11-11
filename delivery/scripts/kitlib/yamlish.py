"""The single fenced YAML block parser for delivery scripts.

A seal, epic, closure or evidence record lives in a Markdown comment as::

    ```yaml <tag>
    ...
    ```

Before this module every script carried its own regex and ``safe_load`` copy.
``parse_block`` is the one supported entry point; the remaining helpers expose
the same regex to callers that need the raw text, a cheap presence check or
block stripping.
"""

from __future__ import annotations

import re
from typing import Any

import yaml


def _pattern(tag: str) -> re.Pattern[str]:
    return re.compile(
        r"```yaml\s+" + re.escape(str(tag)) + r"\s*\n(.*?)```", re.S
    )


def block_text(text: str, tag: str) -> str | None:
    """Inner text of the first fenced block with ``tag``; ``None`` when absent."""
    match = _pattern(tag).search(text or "")
    return match.group(1) if match else None


def load_text(raw: str) -> Any:
    """Parse raw YAML; callers that need error detail keep the exception."""
    return yaml.safe_load(raw)


def parse_text(raw: str) -> dict:
    """Parse raw YAML into a mapping; anything else collapses to ``{}``."""
    data = load_text(raw) or {}
    return data if isinstance(data, dict) else {}


def parse_block(text: str, tag: str) -> dict:
    """Parse the first ``yaml <tag>`` fenced block into a dict.

    Missing, invalid or non-mapping blocks return ``{}`` — the documented
    fallback every migrated caller used.
    """
    raw = block_text(text, tag)
    if raw is None:
        return {}
    try:
        return parse_text(raw)
    except yaml.YAMLError:
        return {}


def has_block(text: str, tag: str) -> bool:
    """Whether ``text`` carries a ``yaml <tag>`` block."""
    return block_text(text, tag) is not None


def strip_blocks(text: str, tags: tuple[str, ...] = ("demir-kit", "demir-kit-epic")) -> str:
    """Remove the given fenced blocks from a body."""
    result = text or ""
    for tag in tags:
        result = _pattern(tag).sub("", result)
    return result
