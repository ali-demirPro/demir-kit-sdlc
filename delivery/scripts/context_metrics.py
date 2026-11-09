#!/usr/bin/env python3
"""Context metrics: miss/over-read rates and the leaf-done record.

Definitions (single source of truth, see ``delivery/policies/context-budget.md``):

- ``miss_rate = |missed_docs| / (|brief_docs| + |missed_docs|)`` — brief docs
  here are the *used* ones; an unused brief doc is over-read, not missed.
- ``over_read_rate = (extra_docs_token + unused_brief_token) / tokens`` — the
  denominator is the session token delta: ``.kit/usage-<issue>.json`` wins,
  otherwise ``usage.session_delta`` is called; neither means ``unknown``.
- A zero denominator, a missing usage delta or a missing document yields
  ``unknown``; a zero is never invented. Rates above 1 are clamped to 1.0 and
  the row records ``clamped: true``. The ``method`` field names the source as
  ``usage-delta`` (session delta) or ``usage-total`` (explicit snapshot file).

One deterministic JSON line is appended to ``.kit/context-metrics.jsonl`` so a
leaf-done transition can tell whether the CP was measured.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import usage

UNKNOWN = "unknown"
METRICS_PATH = Path(".kit") / "context-metrics.jsonl"
ROOT = Path(__file__).resolve().parents[2]
INDEX_VERSION_RE = re.compile(r"^version:\s*(\S+)\s*$", re.M)


def resolve_root(project: Path | str | None = None) -> Path:
    """Project root that owns ``.kit/``."""
    if project:
        return Path(project).resolve()
    override = os.environ.get("DEMIR_KIT_CONTEXT_ROOT")
    if override:
        return Path(override).resolve()
    cwd = Path.cwd().resolve()
    if (cwd / "kit.config.yaml").is_file() or (cwd / "delivery" / "registry.yaml").is_file():
        return cwd
    return ROOT


def metrics_path(root: Path | None = None) -> Path:
    return resolve_root(root) / METRICS_PATH


def display_path(value: str | Path, root: Path | None = None) -> str:
    """Stable, repo-relative path for the JSON row."""
    base = resolve_root(root)
    path = Path(value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(base).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _target(value: str | Path, root: Path | None = None) -> Path:
    path = Path(value)
    return path if path.is_absolute() else resolve_root(root) / path


def token_total(data: dict) -> int:
    """Sum input + output + reasoning + cache read/write.

    Accepts both the snapshot shape (``tokens.cache.read``) and the delta shape
    (``tokens.cache_read``) written by ``usage.py``.
    """
    tokens = data.get("tokens") if isinstance(data, dict) else None
    tokens = tokens if isinstance(tokens, dict) else {}
    cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
    total = 0
    for key in ("input", "output", "reasoning"):
        total += int(tokens.get(key) or 0)
    total += int(cache.get("read") or tokens.get("cache_read") or 0)
    total += int(cache.get("write") or tokens.get("cache_write") or 0)
    return total


def load_usage(path: Path) -> dict | None:
    """Parsed usage JSON, or ``None`` when missing or invalid."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def usage_kind(data: dict | None) -> str:
    """``usage-delta`` for a session delta, ``usage-total`` for a snapshot."""
    if not isinstance(data, dict):
        return "usage-total"
    if "duration_seconds" in data or data.get("delta") is True:
        return "usage-delta"
    if "time" in data or "created_at" in data:
        return "usage-total"
    return "usage-delta"


def session_delta(issue: int) -> dict | None:
    """Session delta from ``usage.py``; ``None`` when unavailable."""
    try:
        return usage.session_delta(issue)
    except Exception:  # noqa: BLE001 - missing snapshot/session is ``unknown``
        return None


def resolve_tokens(
    issue: int,
    explicit: int | None,
    usage_file: str | Path | None,
    root: Path | None = None,
) -> tuple[int | str, str]:
    """``(tokens | unknown, method flag)`` for the session delta.

    ``.kit/usage-<issue>.json`` (delta) wins, then ``usage.session_delta``.
    A claim-time ``.orchestration/usage-<issue>.json`` is a session total, so it
    is only read when passed explicitly and is labelled ``usage-total``.
    """
    if explicit is not None:
        return (explicit if explicit > 0 else UNKNOWN, "tokens:explicit")
    base = resolve_root(root)
    if usage_file:
        path = Path(usage_file)
        if not path.is_absolute():
            path = base / path
        data = load_usage(path)
        total = token_total(data) if data is not None else 0
        if total > 0:
            return total, f"tokens:{usage_kind(data)}:{display_path(path, root)}"
        return UNKNOWN, "tokens:unknown"
    delta_path = base / ".kit" / f"usage-{issue}.json"
    if delta_path.is_file():
        data = load_usage(delta_path)
        total = token_total(data) if data is not None else 0
        if total > 0:
            return total, f"tokens:usage-delta:{display_path(delta_path, root)}"
        return UNKNOWN, "tokens:unknown"
    data = session_delta(issue)
    total = token_total(data) if data is not None else 0
    if total > 0:
        return total, "tokens:usage-delta:session"
    return UNKNOWN, "tokens:unknown"


def miss_rate(brief_docs: list[str], missed_docs: list[str]) -> float | str:
    denominator = len(brief_docs) + len(missed_docs)
    if denominator == 0:
        return UNKNOWN
    return round(len(missed_docs) / denominator, 4)


def doc_cost(value: str | Path, root: Path | None = None) -> int | None:
    """Document token cost: bytes / 4, or ``None`` when the file is missing."""
    path = _target(value, root)
    try:
        if not path.is_file():
            return None
        return path.stat().st_size // 4
    except OSError:
        return None


def over_read_rate(
    extra_docs: list[str],
    unused_brief_docs: list[str],
    tokens: int | str,
    root: Path | None = None,
) -> tuple[float | str, bool, list[str]]:
    """``(rate, clamped, missing_docs)``; unknown when a denominator/term is."""
    missing: list[str] = []
    total = 0
    for value in [*unused_brief_docs, *extra_docs]:
        cost = doc_cost(value, root)
        if cost is None:
            missing.append(display_path(value, root))
            continue
        total += cost
    if isinstance(tokens, str) or tokens <= 0:
        return UNKNOWN, False, sorted(missing)
    if missing:
        return UNKNOWN, False, sorted(missing)
    raw = total / tokens
    clamped = raw > 1.0
    return round(min(1.0, raw), 4), clamped, []


def config_digest(root: Path | None = None, explicit: str | None = None) -> str:
    """``sha256:<hex>`` over registry.yaml plus the route-index version."""
    if explicit:
        return explicit
    base = resolve_root(root)
    registry = base / "delivery" / "registry.yaml"
    index = base / "delivery" / "context" / "index.yaml"
    if not registry.is_file() and not index.is_file():
        return UNKNOWN
    digest = hashlib.sha256()
    if registry.is_file():
        digest.update(registry.read_bytes())
    if index.is_file():
        try:
            text = index.read_text(encoding="utf-8")
        except OSError:
            text = ""
        match = INDEX_VERSION_RE.search(text)
        version = match.group(1) if match else UNKNOWN
        digest.update(f"\ncontext-index-version:{version}".encode())
    return "sha256:" + digest.hexdigest()


def build_row(
    issue: int,
    cp: str,
    brief_docs: list[str] | None = None,
    unused_brief_docs: list[str] | None = None,
    extra_docs: list[str] | None = None,
    missed_docs: list[str] | None = None,
    tokens: int | None = None,
    usage_file: str | Path | None = None,
    config: str | None = None,
    root: Path | None = None,
) -> dict:
    base = resolve_root(root)
    brief_sorted = sorted(display_path(value, base) for value in brief_docs or [])
    unused_sorted = sorted(
        display_path(value, base) for value in unused_brief_docs or []
    )
    extra_sorted = sorted(display_path(value, base) for value in extra_docs or [])
    missed_sorted = sorted(display_path(value, base) for value in missed_docs or [])
    token_value, token_method = resolve_tokens(issue, tokens, usage_file, base)
    rate, clamped, missing = over_read_rate(
        extra_sorted, unused_sorted, token_value, base
    )
    method = [token_method]
    method += [f"doc-missing:{value}" for value in missing]
    row = {
        "issue": issue,
        "cp": cp,
        "brief_docs": brief_sorted,
        "unused_brief_docs": unused_sorted,
        "extra_docs": extra_sorted,
        "missed_docs": missed_sorted,
        "tokens": token_value,
        "miss_rate": miss_rate(brief_sorted, missed_sorted),
        "over_read_rate": rate,
        "clamped": clamped,
        "config_digest": config_digest(base, config),
        "method": ";".join(sorted(method)),
    }
    return row


def line_of(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def record(
    issue: int,
    cp: str,
    brief_docs: list[str] | None = None,
    unused_brief_docs: list[str] | None = None,
    extra_docs: list[str] | None = None,
    missed_docs: list[str] | None = None,
    tokens: int | None = None,
    usage_file: str | Path | None = None,
    config: str | None = None,
    root: Path | None = None,
    write: bool = True,
) -> tuple[dict, str]:
    row = build_row(
        issue,
        cp,
        brief_docs=brief_docs,
        unused_brief_docs=unused_brief_docs,
        extra_docs=extra_docs,
        missed_docs=missed_docs,
        tokens=tokens,
        usage_file=usage_file,
        config=config,
        root=root,
    )
    line = line_of(row)
    if write:
        path = metrics_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return row, line


def check(
    issue: int, cp: str | None = None, root: Path | None = None
) -> tuple[bool, str]:
    """A metrics row exists for ``issue`` and, when given, the same ``cp``."""
    path = metrics_path(root)
    if not path.is_file():
        return False, "uyari: context-metrics satiri yok"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False, "uyari: context-metrics satiri yok"
    for raw in lines:
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("issue") != issue:
            continue
        if cp and row.get("cp") != cp:
            continue
        label = f"#{issue}" + (f" {cp}" if cp else "")
        return True, f"context-metrics: {label} satiri var"
    return False, "uyari: context-metrics satiri yok"


def parse_brief(value: str) -> tuple[str, bool]:
    """``path[:used|:unused]`` -> ``(path, unused)``."""
    for suffix, unused in ((":unused", True), (":used", False)):
        if value.endswith(suffix):
            return value[: -len(suffix)], unused
    return value, False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="context miss/over-read metrics")
    parser.add_argument("--project", type=Path, help="project root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    record_parser = sub.add_parser("record", help="append one metrics line")
    record_parser.add_argument("--issue", type=int, required=True)
    record_parser.add_argument("--cp", required=True)
    record_parser.add_argument("--brief-doc", action="append", default=[])
    record_parser.add_argument("--unused-brief-doc", action="append", default=[])
    record_parser.add_argument("--extra-doc", action="append", default=[])
    record_parser.add_argument("--missed-doc", action="append", default=[])
    record_parser.add_argument("--tokens", type=int)
    record_parser.add_argument("--usage-file")
    record_parser.add_argument("--config-digest")
    record_parser.add_argument("--dry-run", action="store_true")

    check_parser = sub.add_parser("check", help="verify a line exists for an issue")
    check_parser.add_argument("--issue", type=int, required=True)
    check_parser.add_argument("--cp", help="ayni issue ve cp satirini ara")

    args = parser.parse_args(argv)
    root = resolve_root(args.project)

    if args.command == "check":
        ok, message = check(args.issue, args.cp, root)
        print(message, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1

    brief: list[str] = []
    unused: list[str] = list(args.unused_brief_doc)
    for value in args.brief_doc:
        path, is_unused = parse_brief(value)
        (unused if is_unused else brief).append(path)
    row, line = record(
        args.issue,
        args.cp,
        brief_docs=brief,
        unused_brief_docs=unused,
        extra_docs=args.extra_doc,
        missed_docs=args.missed_doc,
        tokens=args.tokens,
        usage_file=args.usage_file,
        config=args.config_digest,
        root=root,
        write=not args.dry_run,
    )
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
