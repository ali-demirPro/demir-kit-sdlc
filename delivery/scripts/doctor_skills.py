"""Skill lint helpers (extracted from doctor.py).

Kept dependency-free so both doctor and the tests can import them.
`doctor` re-exports every name below; the public interface is unchanged.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit("doctor_skills: PyYAML required")


def is_skill_draft(path: Path) -> bool:
    """`skills/.drafts/...` taslak öneridir; runtime skill değildir."""
    return ".drafts" in path.parts


def iter_files(root: Path, pattern: str = "*"):
    """Öneri taslaklarını atlayarak `root` altındaki dosyaları üretir."""
    for path in root.rglob(pattern):
        if not is_skill_draft(path):
            yield path


SKILL_TRIGGER_RE = re.compile(
    r"(?i)\b("
    r"use when|use this skill when|use the skill when|whenever|"
    r"ne zaman|şu durumda kullan"
    r")\b"
)

SKILL_NEGATION_RE = re.compile(
    r"(?i)\b(not|never|don'?t|doesn'?t|avoid|asla|değil)\b"
)
# Turkish negation can follow the trigger: "... kullanma", "... gerekmiyor".
SKILL_POST_NEGATION_RE = re.compile(
    r"(?i)\b(kullanma|kullanmay|kullanılmaz|gerekmiyor|değil)"
)
CLAUSE_RE = re.compile(r"[.;!?\n]")

SKILL_REF_DEF_RE = re.compile(
    r"^\s{0,3}\[([^\]]+)\]:\s*(<[^>]*>|(?:\\.|\S)+)", re.M
)

SKILL_REF_USE_RE = re.compile(r"\[([^\]]+)\]\[([^\]]*)\]")

def frontmatter_name(text: str) -> str | None:
    block = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not block:
        return None
    match = re.search(r"^name:\s*(.+)$", block.group(1), re.M)
    return match.group(1).strip().strip("\"'") if match else None


def frontmatter_data(text: str) -> dict:
    """Parse the SKILL.md frontmatter block as YAML (empty dict on failure)."""
    block = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not block:
        return {}
    try:
        data = yaml.safe_load(block.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def has_trigger(description: str) -> bool:
    """True when a non-negated trigger phrase appears in the description."""
    for match in SKILL_TRIGGER_RE.finditer(description):
        prefix = description[: match.start()]
        clause_start = 0
        for sep in CLAUSE_RE.finditer(prefix):
            clause_start = sep.end()
        clause = prefix[clause_start:][-80:]
        if SKILL_NEGATION_RE.search(clause):
            continue
        rest = description[match.end() :]
        clause_end = len(rest)
        for sep in CLAUSE_RE.finditer(rest):
            clause_end = sep.start()
            break
        if SKILL_POST_NEGATION_RE.search(rest[:clause_end]):
            continue
        return True
    return False


def strip_code_and_comments(text: str) -> str:
    """Blank out fenced code blocks and HTML comments.

    Examples of the skill format must not satisfy (or break) structural checks:
    a fenced `## Done when` is documentation, not a section. Nested fences are
    tracked by character and length, so a four-backtick block may contain a
    three-backtick example.
    """
    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    in_comment = False
    for line in text.splitlines():
        stripped = line.strip()
        if fence_char:
            closing = re.fullmatch(rf"{re.escape(fence_char)}{{{fence_len},}}\s*", stripped)
            if closing:
                fence_char = None
            out.append("")
            continue
        opening = re.match(r"^(`{3,}|~{3,})", stripped)
        if opening:
            fence_char = opening.group(1)[0]
            fence_len = len(opening.group(1))
            out.append("")
            continue
        # Blank inline code spans outside fences so `[x](y)` in backticks is
        # documentation, not a link, and a `<!--` inside a span is not a comment.
        line = re.sub(
            r"(`+)(?!`)(.*?)\1",
            lambda m: " " * len(m.group(0)),
            line,
        )
        if in_comment:
            if "-->" in line:
                in_comment = False
            out.append("")
            continue
        if "<!--" in line:
            before, _, after = line.partition("<!--")
            if "-->" in after:
                out.append(before + after.split("-->", 1)[1])
            else:
                in_comment = True
                out.append(before)
            continue
        out.append(line)
    return "\n".join(out)


def normalize_link(target: str) -> str:
    """Strip angle brackets, query string and fragment from a link target."""
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = re.sub(r"\\(.)", r"\1", target)
    target = target.split("#", 1)[0]
    target = target.split("?", 1)[0]
    return target


def inline_link_targets(text: str) -> list[str]:
    """Destinations of inline links, allowing parentheses inside a title."""
    targets: list[str] = []
    for match in re.finditer(r"\]\(", text):
        index = match.end()
        start = index
        depth = 1
        in_angle = False
        while index < len(text):
            char = text[index]
            if char == "<":
                in_angle = True
            elif char == ">":
                in_angle = False
            elif char == "(" and not in_angle:
                depth += 1
            elif char == ")" and not in_angle:
                depth -= 1
                if depth == 0:
                    break
            index += 1
        raw = text[start:index].strip()
        if not raw:
            continue
        if raw.startswith("<"):
            end = raw.find(">")
            targets.append(raw[: end + 1] if end > 0 else raw)
        else:
            # A backslash-escaped space is part of the destination, not a title
            # separator: protect it, split, restore.
            protected = raw.replace("\\ ", "\x00")
            targets.append(protected.split()[0].replace("\x00", " "))
    return targets


def relative_links(text: str) -> list[str]:
    """Relative markdown link targets (inline and reference style)."""
    definitions = {
        label.lower(): target
        for label, target in SKILL_REF_DEF_RE.findall(text)
        if not label.startswith("^")
    }
    targets = inline_link_targets(text) + list(definitions.values())
    result: list[str] = []
    for target in targets:
        normalized = normalize_link(target)
        if not normalized:
            continue
        if re.match(r"^[a-z][a-z0-9+.-]*:", normalized, re.I):
            continue
        if normalized.startswith("#") or normalized.startswith("//"):
            continue
        result.append(normalized)
    return result


def undefined_references(text: str) -> list[str]:
    """Reference-style usages whose label has no definition."""
    definitions = {
        label.lower() for label, _ in SKILL_REF_DEF_RE.findall(text)
        if not label.startswith("^")
    }
    missing: list[str] = []
    for label, ref in SKILL_REF_USE_RE.findall(text):
        key = (ref or label).lower()
        if key not in definitions:
            missing.append(key)
    return missing


def lint_skill(path: Path, text: str) -> tuple[list[str], list[str]]:
    """Lint one SKILL.md; returns (errors, warnings).

    Contract: delivery/policies/skill-writing.md. Pure function so the tests can
    call it without touching the repo tree.
    """
    errors: list[str] = []
    warnings: list[str] = []

    data = frontmatter_data(text)
    description = " ".join(str(data.get("description") or "").split())
    if not description:
        errors.append("description yok")
    else:
        if not 40 <= len(description) <= 400:
            errors.append(f"description {len(description)} karakter (40-400)")
        if not has_trigger(description):
            errors.append("description tetikleyici içermiyor (Use when ...)")

    prose = strip_code_and_comments(text)
    done = re.search(r"^## Done when\b", prose, re.M)
    if not done:
        errors.append("## Done when bölümü yok")
    else:
        rest = prose[done.end() :]
        next_heading = re.search(r"^ {0,3}#{1,6} ", rest, re.M)
        section = rest[: next_heading.start()] if next_heading else rest
        lines = section.splitlines()
        setext = any(
            re.fullmatch(r"[=-]+\s*", lines[index + 1].strip())
            and lines[index].strip()
            for index in range(len(lines) - 1)
        )
        if next_heading or setext:
            errors.append("## Done when son bölüm değil")
        content = [
            line
            for line in lines
            if line.strip() and not re.fullmatch(r"[=-]+\s*", line.strip())
        ]
        if not content:
            errors.append("## Done when bölümü boş")

    for link in relative_links(prose):
        candidate = Path(os.path.normpath(path.parent / link))
        if not candidate.exists():
            errors.append(f"göreli link çözülmüyor: {link}")
    for label in undefined_references(prose):
        errors.append(f"referans tanımı yok: {label}")

    body = re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S)
    lines = len(body.splitlines())
    if lines > 300:
        errors.append(f"gövde {lines} satır (üst sınır 300)")
    elif lines > 200:
        warnings.append(f"gövde {lines} satır (200 üstü)")

    if re.search(r"\b(TODO|TBD)\b", prose):
        warnings.append("TODO/TBD içeriyor")

    return errors, warnings


def lint_runtime_skills(root: Path, check, error, warn, rel) -> None:
    """Lint every runtime skill under root and record doctor results.

    `skills/.drafts/` öneri taslakları runtime skill değildir; lint dışında
    kalır (AC-1: taslak `skills/` altında yalnızca öneri olarak durur).
    """
    check("skill writing")
    if not root.is_dir():
        return
    for path in sorted(root.glob("*/SKILL.md")):
        if ".drafts" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        lint_errors, lint_warnings = lint_skill(path, text)
        for message in lint_errors:
            error(f"{rel(path)}: {message}")
        for message in lint_warnings:
            warn(f"{rel(path)}: {message}")


