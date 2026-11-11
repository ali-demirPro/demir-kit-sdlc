"""Path routing shared by the delivery brief and doctor."""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

import yaml

from kitlib import config as kitconfig
from kitlib import root as kitroot
from kitlib import yamlish

DEFAULT_PATH = "ui_feature"
NARROW_ORDER = (
    "store_release",
    "landing_only",
    "experiment",
    "ui_feature",
    "pure_technical",
    "full_product",
)
ENTRY_PATHS = {
    "chore": "pure_technical",
    "bugfix": "pure_technical",
    "refactor": "pure_technical",
    "feature": "ui_feature",
    "architecture_baseline": "full_product",
    "commercial_baseline": "full_product",
}
INACTIVE_REASONS = {
    "designer": "UI/UX kapsamda değil",
    "marketing/stores": "dağıtım kapsamda değil",
    "marketing/landing": "landing/SEO kapsamda değil",
    "growth/run": "experiment/rollout kapsamda değil",
    "devops": "altyapı/CI kapsamda değil",
    "architect": "boundary riski yok",
    "security": "güvenlik yüzeyi yok",
    "data": "veri/migration kapsamda değil",
    "release": "dağıtım kapsamda değil",
}


def project_root(kit_root: Path, cwd: Path | None = None) -> Path:
    """State root: main checkout, explicit project, kit root (``kitlib.root``)."""
    return kitroot.project_root(kit_root, project=cwd)


def checkout_root(cwd: Path | None = None) -> Path:
    """Current checkout (the linked worktree when present); session/report scoped."""
    return kitroot.checkout_root(cwd)


def kit_prefix(kit_root: Path, cwd: Path | None = None) -> str:
    """Vendored kit directory inside the product; ``""`` for a self-host.

    The prefix comes from ``kit.config.yaml: kit.root``, never from a path
    comparison: a vendored kit and its product share one git common root.
    """
    root = kitconfig.kit_root_name(project_root(kit_root, cwd))
    return "" if root in {"", "."} else f"{root}/"


def load_registry(root: Path) -> dict:
    path = root / "delivery" / "registry.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def seal_body(body: str) -> dict:
    return yamlish.parse_block(body, "demir-kit")


def is_epic(body: str) -> bool:
    """Legacy semantics: the opening fence alone marks an epic block.

    ``yamlish.has_block`` also requires the closing fence; a seal that is still
    being written must keep resolving as an epic, as it did before kitlib.
    """
    return (
        re.search(r"```yaml\s+demir-kit-epic\s*\n", body or "") is not None
    )


def all_agents(registry: dict) -> list[str]:
    return _dedupe(registry.get("role_order_default") or [])


def _intersects(left, right) -> bool:
    return bool(
        {str(item).lower() for item in left or []}
        & {str(item).lower() for item in right or []}
    )


def _keyword_hit(text: str, keyword: str) -> bool:
    return (
        re.search(
            r"(?<![A-Za-z0-9])" + re.escape(keyword) + r"(?![A-Za-z0-9])", text
        )
        is not None
    )


def detect_signal(registry: dict, seal: dict):
    factory = seal.get("factory") or {}
    surfaces = seal.get("surfaces") or []
    stacks = factory.get("stacks") or []
    distribution = factory.get("distribution") or []

    for signal in registry.get("signals") or []:
        if not isinstance(signal, dict):
            continue
        match = signal.get("match") or {}
        matched = False
        if match.get("surfaces") and surfaces:
            if not _intersects(surfaces, match["surfaces"]):
                continue
            matched = True
        if match.get("stacks") and stacks:
            if not _intersects(stacks, match["stacks"]):
                continue
            matched = True
        if match.get("distribution") and distribution:
            if not _intersects(distribution, match["distribution"]):
                continue
            matched = True
        if matched:
            return signal
    return None


def strip_seal(body: str) -> str:
    return yamlish.strip_blocks(body)


def detect_path_detail(
    registry: dict, title: str, body: str, seal: dict | None = None
) -> tuple[str, dict | None, str]:
    """Like :func:`detect_path`, plus the provenance of the selection.

    ``path_source`` is ``signal`` when a registry signal matched, ``keyword``
    when the title/body keyword score picked the path, ``entry`` when the seal
    entry kind selected it, and ``default`` only for the last-resort
    DEFAULT_PATH fallback. The original two-value signature stays intact for
    existing callers.
    """
    seal = seal_body(body) if seal is None else seal
    paths = registry.get("paths") or {}
    signal = detect_signal(registry, seal)
    if signal and signal.get("default_path") in paths:
        return signal["default_path"], signal, "signal"

    text = f"{title}\n{strip_seal(body)}".lower()
    scores: dict[str, int] = {}
    for name, spec in paths.items():
        if not isinstance(spec, dict):
            continue
        keywords = [str(item).lower() for item in spec.get("keywords") or []]
        scores[name] = sum(1 for keyword in keywords if _keyword_hit(text, keyword))

    best = max(scores.values()) if scores else 0
    if best > 0:
        candidates = [name for name, score in scores.items() if score == best]
        for name in NARROW_ORDER:
            if name in candidates:
                return name, None, "keyword"
        return sorted(candidates)[0], None, "keyword"

    entry_kind = (seal.get("entry") or {}).get("kind")
    if entry_kind in ENTRY_PATHS and ENTRY_PATHS[entry_kind] in paths:
        return ENTRY_PATHS[entry_kind], None, "entry"
    return DEFAULT_PATH, None, "default"


def detect_path(registry: dict, title: str, body: str, seal: dict | None = None):
    path_id, signal, _ = detect_path_detail(registry, title, body, seal)
    return path_id, signal


def resolve_agents(registry: dict, path_id: str, signal: dict | None = None) -> dict:
    paths = registry.get("paths") or {}
    spec = paths.get(path_id) if isinstance(paths, dict) else None
    spec = spec if isinstance(spec, dict) else {}

    active: list[str] = []
    on_demand: list[str] = []
    optional: list[str] = []

    if spec.get("extends"):
        base = resolve_agents(registry, spec["extends"], None)
        active.extend(base["active"])
        on_demand.extend(base["on_demand"])
        optional.extend(base["optional"])

    active.extend(spec.get("agents") or [])
    on_demand.extend(spec.get("on_demand") or [])
    active.extend(spec.get("agents_add") or [])

    if signal:
        signal_agents = signal.get("agents") or {}
        active.extend(signal_agents.get("required") or [])
        optional.extend(signal_agents.get("optional") or [])
        on_demand.extend(signal_agents.get("on_demand") or [])

    return {
        "active": _dedupe(active),
        "optional": [
            item for item in _dedupe(optional) if item not in active and item not in on_demand
        ],
        "on_demand": [item for item in _dedupe(on_demand) if item not in active],
    }


def inactive_agents(registry: dict, agents: dict) -> list[dict]:
    used = set(agents["active"]) | set(agents["optional"]) | set(agents["on_demand"])
    return [
        {
            "id": agent,
            "reason": INACTIVE_REASONS.get(agent, "bu path'te aktif değil"),
        }
        for agent in all_agents(registry)
        if agent not in used
    ]


def evidence_reviewers(
    gates: dict, risk: str, profile_gates: dict | None = None
) -> list[str]:
    """Reviewer roles the evidence schema and doctor enforce for a CP."""
    merged = {**(gates or {}), **(profile_gates or {})}
    roles = {"adversarial-a"}
    if risk in {"high", "critical"}:
        roles.update({"adversarial-a", "adversarial-b", "architect", "human"})
        if profile_gates or merged.get("platform"):
            roles.add("platform")
    if risk == "critical":
        roles.add("human_second")
    if merged.get("architect"):
        roles.add("architect")
    if merged.get("commercial") or risk == "critical":
        roles.add("commercial")
    if merged.get("human"):
        roles.add("human")
    if merged.get("ui"):
        roles.update({"ui", "ui_visual", "ui_interaction"})
    if merged.get("platform") and (profile_gates or {}).get("platform"):
        roles.add("platform")
    return sorted(roles)


def effective_risk(risk: str, floor: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    value = risk if risk in order else "low"
    return max((value, floor), key=lambda item: order.get(item, 0))


def role_docs(role: str, prefix: str = "") -> list[str]:
    if role == "orchestrator":
        base = f"{prefix}delivery/orchestrator"
    else:
        base = f"{prefix}delivery/agents/{role}"
    return [f"{base}/{name}" for name in ("ROLE.md", "how.md", "communicates.md", "dependencies.md", "SKILL.md")]


def next_action(labels: set[str], epic: bool) -> str:
    if "epic-done" in labels:
        return "no-op: epic kapandı"
    if "leaf-done" in labels:
        return "no-op: leaf kapandı; epic closure bekle"
    if "executing" in labels:
        return "resume: evidence'ları oku, pass olmayan CP'den devam et"
    if "agent-approved" in labels:
        return "health-check → next-leaf --claim → CP-1"
    if epic:
        return "orchestrator: plan + child leaf'leri mühürle"
    return "seal: work-package → doctor --body"


def human_gates(risk: str, epic: bool) -> list[str]:
    gates: list[str] = []
    if risk == "high":
        gates.append("leaf QA (high)")
    elif risk == "critical":
        gates.append("iki insan (critical)")
    if epic:
        gates.append("epic kabulü")
    gates.append("store submit / prod deploy / fiyat / yıkıcı migration (gerektiğinde)")
    return gates


def _dedupe(items) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


ROUTE_INDEX_VERSION = 1
ROUTE_INDEX_KEYS = {"version", "entries"}
ROUTE_ENTRY_KEYS = {"surface", "path", "tags", "weight"}
# Optional per entry: ``section`` — the bölüm hedefi. Route/brief render
# ``path#section`` so a long document is read at one heading, never in full.
ROUTE_ENTRY_OPTIONAL_KEYS = {"section"}
ROUTE_CLASSES = ("sink", "window", "retrieved", "candidate")
ROUTE_SOURCES = {"seal", "resolver", "index", "static"}
# One line per path: sink beats window, window beats retrieved/candidate.
ROUTE_PRIORITY = {"sink": 4, "window": 3, "retrieved": 2, "candidate": 1}
# Matching entries below this weight stay visible as candidates with a reason.
ROUTE_MIN_WEIGHT = 2


def route_target(item: dict) -> str:
    """Display target for one route item: ``path#section`` when a section is set."""
    path = str(item.get("path", ""))
    section = str(item.get("section") or "").strip()
    return f"{path}#{section}" if section else path


class RouteIndexError(ValueError):
    """Invalid delivery/context/index.yaml — the brief exits 2."""


def route_index_path(root: Path) -> Path:
    return Path(root) / "delivery" / "context" / "index.yaml"


def registry_sha256(root: Path) -> str:
    """Digest of the active registry; ``yok`` when the file cannot be read."""
    try:
        data = (Path(root) / "delivery" / "registry.yaml").read_bytes()
    except OSError:
        return "yok"
    return hashlib.sha256(data).hexdigest()


def route_index_version_ok(version) -> bool:
    """One validation shared by the banner and :func:`load_route_index`."""
    return (
        isinstance(version, int)
        and not isinstance(version, bool)
        and version == ROUTE_INDEX_VERSION
    )


def route_index_version(path: Path) -> str:
    """Index version for the config banner; ``yok`` when missing/invalid.

    The route itself stays strict: :func:`load_route_index` raises for the same
    invalid version so ``--route`` can exit 2.
    """
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return "yok"
    version = data.get("version") if isinstance(data, dict) else None
    return str(version) if route_index_version_ok(version) else "yok"


def route_index_version_fallback(path: Path) -> str | None:
    """``index surumu gecersiz`` when a present index has an unusable version."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return "index surumu gecersiz"
    version = data.get("version") if isinstance(data, dict) else None
    return None if route_index_version_ok(version) else "index surumu gecersiz"


def policy_files(root: Path, registry: dict) -> list[str]:
    """Registry policies in order; a missing file is labelled ``missing:<path>``."""
    result: list[str] = []
    for value in (registry.get("policies") or {}).values():
        path = str(value)
        label = path if (Path(root) / path).is_file() else f"missing:{path}"
        if label not in result:
            result.append(label)
    return result


def config_snapshot(
    root: Path,
    registry: dict,
    path_id: str,
    path_source: str,
    index_path: Path,
) -> dict:
    """Effective configuration for a brief: registry digest, route and policies."""
    return {
        "registry_sha256": registry_sha256(root),
        "path": path_id,
        "path_source": path_source,
        "index_version": route_index_version(index_path),
        "policies": policy_files(root, registry),
    }


def control_config(root: Path) -> dict:
    """Minimal banner used by next-leaf/orca_plan/handoff."""
    return {
        "registry_sha256": registry_sha256(root),
        "index_version": route_index_version(route_index_path(root)),
    }


def render_config(config: dict | None) -> list[str]:
    """One ``config:`` block; keys stay on a single line each."""
    if not config:
        return []
    lines = ["config:"]
    for key in ("registry_sha256", "path", "path_source", "index_version"):
        if key in config:
            lines.append(f"  {key}: {config[key]}")
    if "policies" in config:
        policies = [str(item) for item in config.get("policies") or []]
        lines.append("  policies: " + (", ".join(policies) or "yok"))
    return lines


def _is_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _entry_path(base: Path, entry_path: str, label: str) -> Path:
    """Resolve one index path inside ``base``; escapes are errors, not fallbacks."""
    candidate = Path(entry_path)
    if candidate.is_absolute():
        raise RouteIndexError(f"{label}: yol kök dışında: {entry_path}")
    if ".." in candidate.parts:
        raise RouteIndexError(f"{label}: yol kök dışında: {entry_path}")
    try:
        root = base.resolve()
        resolved = (base / candidate).resolve()
    except OSError as exc:
        raise RouteIndexError(f"{label}: yol çözülemedi: {entry_path}") from exc
    try:
        resolved.relative_to(root)
    except ValueError:
        # Symlink that points outside the kit root.
        raise RouteIndexError(f"{label}: yol kök dışında: {entry_path}") from None
    return resolved


def load_route_index(path: Path, root: Path | None = None) -> dict | None:
    """Load and validate the route index; ``None`` means "index yok".

    Missing file is the documented fallback. Any malformed shape raises
    ``RouteIndexError`` so the caller can exit 2 instead of degrading silently.
    """
    path = Path(path)
    if not path.is_file():
        return None
    base = Path(root) if root is not None else path.resolve().parents[2]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RouteIndexError(f"{path}: okunamadı ({exc})") from exc
    if not isinstance(data, dict):
        raise RouteIndexError(f"{path}: üst düzey mapping olmalı")
    unknown = sorted(set(data) - ROUTE_INDEX_KEYS)
    if unknown:
        raise RouteIndexError(f"{path}: bilinmeyen anahtar: {', '.join(unknown)}")
    missing = sorted(ROUTE_INDEX_KEYS - set(data))
    if missing:
        raise RouteIndexError(f"{path}: eksik anahtar: {', '.join(missing)}")
    version = data.get("version")
    if not route_index_version_ok(version):
        raise RouteIndexError(f"{path}: version {ROUTE_INDEX_VERSION} olmalı")
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise RouteIndexError(f"{path}: entries liste olmalı")

    result: list[dict] = []
    for position, entry in enumerate(entries):
        label = f"{path}: entries[{position}]"
        if not isinstance(entry, dict):
            raise RouteIndexError(f"{label}: mapping olmalı")
        unknown = sorted(
            set(entry) - (ROUTE_ENTRY_KEYS | ROUTE_ENTRY_OPTIONAL_KEYS)
        )
        if unknown:
            raise RouteIndexError(f"{label}: bilinmeyen anahtar: {', '.join(unknown)}")
        missing = sorted(ROUTE_ENTRY_KEYS - set(entry))
        if missing:
            raise RouteIndexError(f"{label}: eksik anahtar: {', '.join(missing)}")
        surface = entry.get("surface")
        if not isinstance(surface, str) or not surface.strip():
            raise RouteIndexError(f"{label}: surface boş olamaz")
        entry_path = entry.get("path")
        if not isinstance(entry_path, str) or not entry_path.strip():
            raise RouteIndexError(f"{label}: path boş olamaz")
        resolved = _entry_path(base, entry_path, label)
        if not resolved.is_file():
            raise RouteIndexError(f"{label}: çözülmeyen yol: {entry_path}")
        tags = entry.get("tags")
        if not isinstance(tags, list) or any(
            not isinstance(tag, str) or not tag.strip() for tag in tags
        ):
            raise RouteIndexError(f"{label}: tags string listesi olmalı")
        weight = entry.get("weight")
        if not _is_number(weight) or weight <= 0:
            raise RouteIndexError(f"{label}: weight pozitif sayı olmalı")
        section = entry.get("section")
        if section is not None:
            if not isinstance(section, str) or not section.strip():
                raise RouteIndexError(f"{label}: section boş olmayan string olmalı")
            section = section.strip()
        entry_out = {
            "surface": surface.strip(),
            "path": entry_path,
            "tags": list(tags),
            "weight": weight,
        }
        if section is not None:
            entry_out["section"] = section
        result.append(entry_out)

    return {"version": version, "entries": result}


def _surface_match(left: str, right: str) -> bool:
    left = left.lower()
    right = right.lower()
    return (
        left == right
        or left.startswith(right + ".")
        or right.startswith(left + ".")
    )


def build_route(
    seal: dict,
    docs: list[str],
    index: dict | None,
    prefix: str = "",
) -> tuple[list[dict], str | None]:
    """Explainable sink/window/retrieved/candidate selection for one brief.

    Deterministic: same seal + same docs + same index version yield the same
    ordered list. No clock, HEAD or environment value participates. Every path
    appears once; a higher class wins (sink > window > retrieved > candidate).
    """
    seal = seal if isinstance(seal, dict) else {}
    docs = [str(doc) for doc in docs or []]
    route: dict[str, dict] = {}

    def add(item: dict) -> None:
        current = route.get(item["path"])
        if current is None or ROUTE_PRIORITY[item["class"]] > ROUTE_PRIORITY[
            current["class"]
        ]:
            route[item["path"]] = item

    reference = (seal.get("reference") or {}).get("paths") or []
    for path in reference:
        add(
            {
                "class": "sink",
                "path": f"{prefix}{path}",
                "source": "seal",
                "reason": "seal reference.paths (zorunlu çekirdek)",
            }
        )
    for doc in docs:
        add(
            {
                "class": "window",
                "path": doc,
                "source": "resolver",
                "reason": "aktif rol dokümanı",
            }
        )

    surfaces = [str(item) for item in seal.get("surfaces") or []]
    if index is None:
        # The static list overlaps the window docs; window wins so no path is
        # listed twice. The explicit fallback line keeps the degrade visible.
        for doc in docs:
            add(
                {
                    "class": "retrieved",
                    "path": doc,
                    "source": "static",
                    "reason": "index yok; statik resolver listesi",
                }
            )
        return list(route.values()), "index yok"

    selected: list[dict] = []
    candidates: list[dict] = []
    for entry in index.get("entries") or []:
        matched = any(
            _surface_match(entry["surface"], surface) for surface in surfaces
        )
        weight = float(entry["weight"])
        if matched and weight >= ROUTE_MIN_WEIGHT:
            selected.append(entry)
        elif matched:
            candidates.append(
                {
                    "class": "candidate",
                    "path": f"{prefix}{entry['path']}",
                    "source": "index",
                    "reason": (
                        f"surface {entry['surface']} eşleşti ama düşük weight "
                        f"({entry['weight']} < {ROUTE_MIN_WEIGHT})"
                    ),
                }
            )
        else:
            candidates.append(
                {
                    "class": "candidate",
                    "path": f"{prefix}{entry['path']}",
                    "source": "index",
                    "reason": "surface eşleşmiyor",
                }
            )

    selected.sort(key=lambda entry: (-float(entry["weight"]), str(entry["path"])))
    for entry in selected:
        item = {
            "class": "retrieved",
            "path": f"{prefix}{entry['path']}",
            "source": "index",
            "reason": (
                f"surface {entry['surface']} eşleşti "
                f"(weight {entry['weight']})"
            ),
        }
        if entry.get("section"):
            item["section"] = str(entry["section"])
        add(item)
    candidates.sort(key=lambda item: (item["path"], item["reason"]))
    for item in candidates:
        add(item)
    return list(route.values()), None


def render_route(route: list[dict], fallback: str | None = None) -> str:
    lines: list[str] = []
    if fallback:
        lines.append(f"fallback: {fallback}")
    for item in route:
        lines.append(
            f"{item['class']} {route_target(item)} "
            f"(source: {item['source']}, reason: {item['reason']})"
        )
    return "\n".join(lines) + ("\n" if lines else "")
