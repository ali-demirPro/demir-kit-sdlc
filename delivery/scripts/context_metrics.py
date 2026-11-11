#!/usr/bin/env python3
"""Context metrics: miss/over-read rates and the leaf-done record.

Definitions (single source of truth, see ``delivery/policies/context-budget.md``):

- ``miss_rate = |missed_docs| / (|brief_docs| + |missed_docs|)`` — brief docs
  here are the *used* ones; an unused brief doc is over-read, not missed.
- ``over_read_rate = (extra_docs_token + unused_brief_token) / tokens`` — the
  denominator is the session token delta: ``.kit/usage-<issue>.json`` wins,
  otherwise ``usage.session_delta`` is called; neither means ``unknown`` tokens.
- A zero denominator, a missing usage delta or a missing document means the
  rate cannot be produced: the field is **absent** from the row (``miss_rate``
  / ``over_read_rate`` are simply not written), never ``unknown``. A zero is
  never invented either. Rates above 1 are clamped to 1.0 and the row records
  ``clamped: true``; ``clamped`` exists only when ``over_read_rate`` does. The
  ``method`` field names the source as ``usage-delta`` (session delta) or
  ``usage-total`` (explicit snapshot file).
- ``selected_docs`` is what the CP brief chose. When use evidence is absent
  (``usage_known=False``, the ``record_from_brief`` path) the used/unused split
  stays empty, both rate fields are absent from the row and ``method`` carries
  ``split:unknown``; ``tokens`` may still come from the usage delta, because
  only the used/unused split is unmeasurable, not the token total. The selection
  is never reported as used.

One deterministic JSON line is written per ``(issue, cp)`` to
``.kit/context-metrics.jsonl`` so a leaf-done transition can tell whether the CP
was measured; recording the same pair again replaces its line instead of
appending a duplicate. Writers serialize on ``.kit/context-metrics.lock``
(``fcntl.flock`` where available) and a read error raises
:class:`ContextMetricsError` without touching the file, so a broken line set is
never silently truncated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

try:  # POSIX only; a lock-less platform still records, just unserialized.
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

import usage
import yaml

UNKNOWN = "unknown"
UNMEASURED = "ölçülemedi"
DISTRIBUTION_KEYS = ("0", "(0,0.25]", "(0.25,0.5]", "(0.5,1.0]", "unknown")
METRICS_PATH = Path(".kit") / "context-metrics.jsonl"
ROOT = Path(__file__).resolve().parents[2]
INDEX_VERSION_RE = re.compile(r"^version:\s*(\S+)\s*$", re.M)
FREQUENCY_VERSION = 1
FREQUENCY_PATH = Path("delivery") / "context" / "frequency.yaml"
INDEX_PATH = Path("delivery") / "context" / "index.yaml"
FREQUENCY_KEYS = {"version", "source", "rows"}
FREQUENCY_ROW_KEYS = {"doc", "surface", "selected", "used", "ratio"}


class ContextMetricsError(RuntimeError):
    """The metrics file could not be read; it was left untouched."""


class FrequencyError(ValueError):
    """Invalid ``delivery/context/frequency.yaml`` shape."""


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


def storage_root(root: Path | None = None) -> Path:
    """Root that owns the runtime ``.kit`` files (brief metadata + metrics).

    One rule for writer and reader: an explicit root wins, then
    ``DEMIR_KIT_CONTEXT_ROOT`` (test/runtime override), then the main checkout
    (``cycle.jsonl`` lives there and survives the epic worktree).
    """
    if root is not None:
        target = Path(root).resolve()
        # An explicit epic worktree still owns state in its main checkout:
        # .kit runtime files must survive the worktree's removal.
        import cycle

        common = cycle.git_root(target)
        if common and (common / "kit.config.yaml").is_file():
            return common
        return target
    override = os.environ.get("DEMIR_KIT_CONTEXT_ROOT")
    if override:
        return Path(override).resolve()
    import cycle

    return cycle.project_root(ROOT)


def metrics_path(root: Path | None = None) -> Path:
    return storage_root(root) / METRICS_PATH


def brief_meta_path(issue: int, cp: str, root: Path | None = None) -> Path:
    """Machine metadata written by the CP brief for one issue + checkpoint."""
    return storage_root(root) / ".kit" / f"brief-{issue}-{cp}.json"


def read_brief_meta(
    issue: int, cp: str, root: Path | None = None
) -> dict | None:
    """Brief metadata for ``issue``/``cp``; ``None`` when absent or mismatched.

    A known list key whose value is not a ``list[str]`` marks the whole file as
    corrupt (hand-edited or wrongly written), so it is not trusted at all.
    """
    try:
        data = json.loads(
            brief_meta_path(issue, cp, root).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("issue") != issue or data.get("cp") != cp:
        return None
    for key in ("armed", "unarmed", "fallbacks", "selected_docs"):
        if key in data:
            value = data[key]
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                return None
    return data


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
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
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


def session_delta(issue: int, root: Path | None = None) -> dict | None:
    """Session delta from ``usage.py`` rooted at ``root``; ``None`` when unavailable."""
    try:
        return usage.session_delta(issue, project=resolve_root(root))
    except (Exception, SystemExit):  # noqa: BLE001 - missing/unreachable is ``unknown``
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
    data = session_delta(issue, base)
    total = token_total(data) if data is not None else 0
    if total > 0:
        return total, "tokens:usage-delta:session"
    return UNKNOWN, "tokens:unknown"


def miss_rate(brief_docs: list[str], missed_docs: list[str]) -> float | None:
    denominator = len(brief_docs) + len(missed_docs)
    if denominator == 0:
        return None
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
) -> tuple[float | None, bool, list[str]]:
    """``(rate | None, clamped, missing_docs)``; ``None`` when a term is."""
    missing: list[str] = []
    total = 0
    for value in [*unused_brief_docs, *extra_docs]:
        cost = doc_cost(value, root)
        if cost is None:
            missing.append(display_path(value, root))
            continue
        total += cost
    if isinstance(tokens, str) or tokens <= 0:
        return None, False, sorted(missing)
    if missing:
        return None, False, sorted(missing)
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
    brief_meta: dict | None = None,
    root: Path | None = None,
    selected_docs: list[str] | None = None,
    usage_known: bool = True,
) -> dict:
    base = resolve_root(root)
    selected_sorted = sorted(
        display_path(value, base) for value in selected_docs or []
    )
    if usage_known:
        brief_sorted = sorted(
            display_path(value, base) for value in brief_docs or []
        )
        unused_sorted = sorted(
            display_path(value, base) for value in unused_brief_docs or []
        )
        extra_sorted = sorted(
            display_path(value, base) for value in extra_docs or []
        )
        missed_sorted = sorted(
            display_path(value, base) for value in missed_docs or []
        )
    else:
        # Selection is known but there is no use evidence: never fabricate a
        # used/unused split or a zero rate.
        brief_sorted = []
        unused_sorted = []
        extra_sorted = []
        missed_sorted = []
    token_value, token_method = resolve_tokens(issue, tokens, usage_file, base)
    if usage_known:
        rate, clamped, missing = over_read_rate(
            extra_sorted, unused_sorted, token_value, base
        )
        miss_value = miss_rate(brief_sorted, missed_sorted)
    else:
        rate, clamped, missing = None, False, []
        miss_value = None
    method = [token_method]
    method += [f"doc-missing:{value}" for value in missing]
    if not usage_known:
        # Only the used/unused split is unknown; tokens may still be a delta.
        method.append("split:unknown")
    meta = brief_meta if isinstance(brief_meta, dict) else None
    if meta is not None and "armed" in meta and isinstance(meta["armed"], list):
        armed_value = bool(meta["armed"])
    else:
        # A present key keeps its meaning; an absent key or a non-list value
        # (null/str) is unmeasured, never a fabricated False/0.
        armed_value = UNKNOWN
    if (
        meta is not None
        and "fallbacks" in meta
        and isinstance(meta["fallbacks"], list)
    ):
        fallback_count = len(meta["fallbacks"])
    else:
        # No metadata (or a non-list fallbacks value) means unmeasured.
        fallback_count = UNKNOWN
    row = {
        "issue": issue,
        "cp": cp,
        "selected_docs": selected_sorted,
        "brief_docs": brief_sorted,
        "unused_brief_docs": unused_sorted,
        "extra_docs": extra_sorted,
        "missed_docs": missed_sorted,
        "tokens": token_value,
        "armed": armed_value,
        "fallback_count": fallback_count,
        "config_digest": config_digest(base, config),
        "method": ";".join(sorted(method)),
    }
    # A rate that cannot be produced is absent from the schema, never
    # ``unknown``: readers measure what exists and report absent as ölçülemedi.
    if miss_value is not None:
        row["miss_rate"] = miss_value
    if rate is not None:
        row["over_read_rate"] = rate
        row["clamped"] = clamped
    return row


def line_of(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _existing_lines(path: Path) -> list[str]:
    """Lines of the current metrics file; a read error never erases them.

    A missing file is an empty history. An existing but unreadable file (bad
    UTF-8, permissions, I/O error) raises :class:`ContextMetricsError` so the
    caller leaves the bytes alone instead of rewriting them from ``[]``.
    """
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError) as exc:
        raise ContextMetricsError(
            f"context-metrics okunamadi: {path}: {exc}"
        ) from exc


def _replace_line(lines: list[str], issue: int, cp: str, line: str) -> list[str]:
    """Drop the old rows for ``(issue, cp)`` and append the new line."""
    kept: list[str] = []
    for raw in lines:
        if not raw.strip():
            continue
        try:
            current = json.loads(raw)
        except json.JSONDecodeError:
            # A broken line is not ours to drop.
            kept.append(raw)
            continue
        if (
            isinstance(current, dict)
            and current.get("issue") == issue
            and current.get("cp") == cp
        ):
            continue
        kept.append(raw)
    kept.append(line)
    return kept


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
    brief_meta: dict | None = None,
    root: Path | None = None,
    write: bool = True,
    selected_docs: list[str] | None = None,
    usage_known: bool = True,
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
        brief_meta=brief_meta,
        root=root,
        selected_docs=selected_docs,
        usage_known=usage_known,
    )
    line = line_of(row)
    if write:
        path = metrics_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.parent / "context-metrics.lock"
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            if fcntl is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            kept = _replace_line(_existing_lines(path), issue, cp, line)
            # Write to a sibling temp file and atomically replace, so a crash
            # mid-write cannot truncate the existing metrics file.
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text("\n".join(kept) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        finally:
            if fcntl is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except OSError:  # pragma: no cover - closing releases it too
                    pass
            os.close(lock_fd)
    return row, line


def record_from_brief(
    issue: int, cp: str, root: Path | None = None
) -> tuple[dict, str] | None:
    """Record a row from the CP brief metadata; ``None`` when it is missing.

    The brief only knows which documents it *selected*, not which were used, so
    the row carries ``selected_docs`` with the used/unused split unmeasured and
    ``miss_rate``/``over_read_rate`` absent (the unmeasurable fields are left
    out of the schema instead of fabricating ``0.0``).
    """
    meta = read_brief_meta(issue, cp, root)
    if meta is None:
        return None
    selected = meta.get("selected_docs")
    try:
        return record(
            issue,
            cp,
            selected_docs=selected if isinstance(selected, list) else [],
            usage_known=False,
            brief_meta=meta,
            root=root,
        )
    except ContextMetricsError:
        # A leaf-done must not crash because the metrics file is unreadable.
        print(
            "uyari: context-metrics okunamadi; satir yazilmadi",
            file=sys.stderr,
        )
        return None
    except OSError:
        # Metadata is optional; a read-only project keeps its leaf-done, but
        # the missing row must still be visible on stderr.
        print("uyari: context-metrics yazilamadi; satir yok", file=sys.stderr)
        return None
    except (ValueError, TypeError, OverflowError):
        # A malformed usage snapshot must not turn a measurement into a stop.
        print("uyari: context-metrics okunamadi; satir yazilmadi", file=sys.stderr)
        return None


def check(
    issue: int, cp: str | None = None, root: Path | None = None
) -> tuple[bool, str]:
    """A metrics row exists for ``issue`` and, when given, the same ``cp``."""
    path = metrics_path(root)
    if not path.is_file():
        return False, "uyari: context-metrics satiri yok"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        # A broken file must not crash the leaf-done warning path.
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


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _normalize_doc(value) -> str:
    text = str(value or "").replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text


def _label(path: Path, root: Path | None = None) -> str:
    try:
        return Path(path).resolve().relative_to(resolve_root(root)).as_posix()
    except (OSError, ValueError):
        return Path(path).as_posix()


def surface_map(
    index_file: str | Path | None = None, root: Path | None = None
) -> dict[str, str]:
    """``doc -> surface`` from the route index; unreadable index means no map."""
    path = _target(index_file or INDEX_PATH, root)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    mapping: dict[str, str] = {}
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        doc = _normalize_doc(entry.get("path"))
        surface = str(entry.get("surface") or "").strip()
        if doc and surface:
            mapping[doc] = surface
    return mapping


def _metrics_lines(path: Path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def _distribution(values: list) -> dict:
    """Five deterministic buckets; numeric values never land in ``unknown``."""
    buckets = {key: 0 for key in DISTRIBUTION_KEYS}
    for value in values:
        if not _is_number(value):
            buckets["unknown"] += 1
            continue
        rate = float(value)
        if rate <= 0:
            buckets["0"] += 1
        elif rate <= 0.25:
            buckets["(0,0.25]"] += 1
        elif rate <= 0.5:
            buckets["(0.25,0.5]"] += 1
        else:
            buckets["(0.5,1.0]"] += 1
    return buckets


def _rate_block(values: list) -> dict:
    """``measured``, ``average`` and ``distribution`` for one rate column."""
    numeric = [float(value) for value in values if _is_number(value)]
    average = round(sum(numeric) / len(numeric), 4) if numeric else UNMEASURED
    return {
        "measured": len(numeric),
        "average": average,
        "distribution": _distribution(values),
    }


def _leaf_row(row: dict) -> dict:
    """Per-leaf summary; anything unmeasured stays ``ölçülemedi``."""
    issue = row.get("issue")
    cp = row.get("cp")
    armed = row.get("armed")
    fallback = row.get("fallback_count")
    miss_value = row.get("miss_rate")
    over_value = row.get("over_read_rate")
    return {
        "issue": issue if _is_int(issue) else UNMEASURED,
        "cp": cp if isinstance(cp, str) and cp.strip() else UNMEASURED,
        "armed": armed if isinstance(armed, bool) else UNMEASURED,
        "fallback_count": fallback if _is_number(fallback) else UNMEASURED,
        "miss_rate": miss_value if _is_number(miss_value) else UNMEASURED,
        "over_read_rate": over_value if _is_number(over_value) else UNMEASURED,
    }


def summary(
    metrics_file: str | Path | None = None,
    window: int = 10,
    root: Path | None = None,
) -> dict:
    """Deterministic miss/over-read summary over ``.kit/context-metrics.jsonl``.

    ``sample`` is every readable line, ``window`` is the trailing slice
    (``leaves``) and ``ready`` says whether that slice already holds ten leaves.
    Rates and the armed/fallback counts aggregate over that trailing window: the
    report is a 10-leaf window, not an ever-growing total. A rate that is not
    numeric is never replaced by a fabricated zero.
    """
    base = resolve_root(root)
    path = (
        _target(metrics_file, base)
        if metrics_file is not None
        else metrics_path(root)
    )
    rows = list(_metrics_lines(path))
    size = max(0, int(window))
    recent = rows[-size:] if size else []

    miss_values = [row.get("miss_rate") for row in recent]
    over_values = [row.get("over_read_rate") for row in recent]

    armed = {"true": 0, "false": 0, "unknown": 0}
    fallback_total = 0
    fallback_unknown = 0
    for row in recent:
        armed_value = row.get("armed")
        if armed_value is True:
            armed["true"] += 1
        elif armed_value is False:
            armed["false"] += 1
        else:
            armed["unknown"] += 1
        fallback = row.get("fallback_count")
        if _is_number(fallback):
            fallback_total += fallback
        else:
            fallback_unknown += 1

    return {
        "sample": len(rows),
        "window": len(recent),
        "ready": len(recent) >= 10,
        "leaves": [_leaf_row(row) for row in recent],
        "miss_rate": _rate_block(miss_values),
        "over_read_rate": _rate_block(over_values),
        "armed": armed,
        "fallback_count": {"total": fallback_total, "unknown": fallback_unknown},
    }


def learn_rows(
    metrics_file: str | Path | None = None,
    index_file: str | Path | None = None,
    root: Path | None = None,
) -> list[dict]:
    """Observed ``(document, surface)`` counts from metrics lines.

    ``brief_docs`` are selected *and* used; ``unused_brief_docs`` are selected
    but not used. Both map to a surface through the route index; a document the
    index does not name is not counted because the row needs a surface. Rows are
    sorted by ``(surface, doc)`` so the same trace always yields the same list.
    """
    surfaces = surface_map(index_file, root)
    counts: dict[tuple[str, str], list[int]] = {}
    for row in _metrics_lines(_target(metrics_file or METRICS_PATH, root)):
        used = row.get("brief_docs") if isinstance(row.get("brief_docs"), list) else []
        unused = (
            row.get("unused_brief_docs")
            if isinstance(row.get("unused_brief_docs"), list)
            else []
        )
        for doc in [*used, *unused]:
            if not isinstance(doc, str):
                continue
            key = _normalize_doc(doc)
            surface = surfaces.get(key)
            if surface is None:
                continue
            entry = counts.setdefault((surface, key), [0, 0])
            entry[0] += 1
            if doc in used:
                entry[1] += 1
    learned: list[dict] = []
    for (surface, doc), (selected, used) in sorted(counts.items()):
        if selected <= 0:
            continue
        learned.append(
            {
                "doc": doc,
                "surface": surface,
                "selected": selected,
                "used": used,
                "ratio": round(used / selected, 4),
            }
        )
    return learned


def frequency_document(
    metrics_file: str | Path | None = None,
    index_file: str | Path | None = None,
    root: Path | None = None,
) -> dict:
    """Deterministic, versioned frequency table (counts only, no identity)."""
    base = resolve_root(root)
    metrics = metrics_file if metrics_file is not None else METRICS_PATH
    return {
        "version": FREQUENCY_VERSION,
        "source": display_path(metrics, base),
        "rows": learn_rows(metrics, index_file, base),
    }


def frequency_errors(path: str | Path, root: Path | None = None) -> list[str]:
    """Shape errors for ``frequency.yaml``; an absent file has no errors."""
    target = Path(path)
    if not target.is_file():
        return []
    label = _label(target, root)
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [f"{label}: okunamadı ({exc})"]
    if not isinstance(data, dict):
        return [f"{label}: üst düzey mapping olmalı"]
    errors: list[str] = []
    unknown = sorted(set(data) - FREQUENCY_KEYS)
    if unknown:
        errors.append(f"{label}: bilinmeyen anahtar: {', '.join(unknown)}")
    missing = sorted({"version", "rows"} - set(data))
    if missing:
        errors.append(f"{label}: eksik anahtar: {', '.join(missing)}")
    version = data.get("version")
    if not _is_int(version) or version != FREQUENCY_VERSION:
        errors.append(f"{label}: version {FREQUENCY_VERSION} olmalı")
    if "source" in data and (
        not isinstance(data.get("source"), str) or not data.get("source").strip()
    ):
        errors.append(f"{label}: source boş olamaz")
    rows = data.get("rows")
    if not isinstance(rows, list):
        errors.append(f"{label}: rows liste olmalı")
        return errors
    for position, row in enumerate(rows):
        where = f"{label}: rows[{position}]"
        if not isinstance(row, dict):
            errors.append(f"{where}: mapping olmalı")
            continue
        unknown = sorted(set(row) - FREQUENCY_ROW_KEYS)
        if unknown:
            errors.append(f"{where}: bilinmeyen anahtar: {', '.join(unknown)}")
        missing = sorted(FREQUENCY_ROW_KEYS - set(row))
        if missing:
            errors.append(f"{where}: eksik anahtar: {', '.join(missing)}")
            continue
        for key in ("doc", "surface"):
            value = row.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{where}: {key} boş olamaz")
        selected = row.get("selected")
        used = row.get("used")
        if not _is_int(selected) or selected <= 0:
            errors.append(f"{where}: selected pozitif tam sayı olmalı")
        if not _is_int(used) or used < 0:
            errors.append(f"{where}: used negatif olmayan tam sayı olmalı")
        if _is_int(selected) and _is_int(used) and used > selected:
            errors.append(f"{where}: used selected'dan büyük olamaz")
        ratio = row.get("ratio")
        if not _is_number(ratio) or not 0 <= float(ratio) <= 1:
            errors.append(f"{where}: ratio 0..1 aralığında olmalı")
    return errors


def load_frequency(path: str | Path, root: Path | None = None) -> dict | None:
    """Parsed frequency table, ``None`` when absent; invalid shape raises."""
    target = Path(path)
    if not target.is_file():
        return None
    errors = frequency_errors(target, root)
    if errors:
        raise FrequencyError("; ".join(errors))
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise FrequencyError(f"{_label(target, root)}: okunamadı ({exc})") from exc
    return data if isinstance(data, dict) else None


def report_frequency(
    path: str | Path, report, root: Path | None = None
) -> None:
    """Send each frequency shape error to ``report`` (doctor's error sink)."""
    for message in frequency_errors(path, root):
        report(message)


def write_frequency(
    path: str | Path, document: dict, root: Path | None = None
) -> Path:
    """Write the frequency table deterministically; returns the path."""
    target = _target(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return target


def learn(
    metrics_file: str | Path | None = None,
    index_file: str | Path | None = None,
    output: str | Path | None = None,
    root: Path | None = None,
    write: bool = True,
) -> tuple[dict, Path | None]:
    """Learn the frequency table and optionally write it."""
    base = resolve_root(root)
    document = frequency_document(metrics_file, index_file, base)
    target = None
    if write:
        target = write_frequency(output or FREQUENCY_PATH, document, base)
    return document, target


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

    record_parser = sub.add_parser(
        "record",
        help="write/replace the metrics line for one issue + checkpoint",
    )
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

    summary_parser = sub.add_parser("summary", help="10-leaf miss/over-read ozeti")
    summary_parser.add_argument("--window", type=int, default=10)
    # The top-level flag still parses before the subcommand; SUPPRESS keeps this
    # alias from overwriting a value that came before ``summary``.
    summary_parser.add_argument(
        "--project",
        type=Path,
        default=argparse.SUPPRESS,
        help="proje koku (alt komuttan sonra da kabul edilir)",
    )

    learn_parser = sub.add_parser(
        "learn", help="derive delivery/context/frequency.yaml from metrics"
    )
    learn_parser.add_argument("--metrics", default=str(METRICS_PATH))
    learn_parser.add_argument("--index", default=str(INDEX_PATH))
    learn_parser.add_argument("--output", default=str(FREQUENCY_PATH))
    learn_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    root = (
        resolve_root(args.project)
        if args.command == "learn"
        else storage_root(args.project)
    )

    if args.command == "summary":
        # The task's public surface: JSON on stdout, exit 0.
        document = summary(window=args.window, root=root)
        sys.stdout.write(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        )
        return 0

    if args.command == "learn":
        document, target = learn(
            args.metrics,
            args.index,
            args.output,
            root,
            write=not args.dry_run,
        )
        if args.dry_run:
            sys.stdout.write(
                yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
            )
        else:
            print(display_path(target, root))
        return 0

    if args.command == "check":
        ok, message = check(args.issue, args.cp, root)
        print(message, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1

    brief: list[str] = []
    unused: list[str] = list(args.unused_brief_doc)
    for value in args.brief_doc:
        path, is_unused = parse_brief(value)
        (unused if is_unused else brief).append(path)
    try:
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
    except (ContextMetricsError, OSError) as exc:
        print(f"context-metrics: {exc}", file=sys.stderr)
        return 1
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
