#!/usr/bin/env python3
"""demir-kit doctor — delivery contract enforcement.

Kontroller: `--explain <ad>` · etkin gate'ler: `--explain gates`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import approvals as approvals_lib  # noqa: E402
import capabilities as capabilities_lib  # noqa: E402
import context_metrics  # noqa: E402
import delivery_block  # noqa: E402
import doctor_approval  # noqa: E402
import doctor_compat  # noqa: E402
import doctor_local  # noqa: E402
import doctor_mcp  # noqa: E402
import doctor_explain  # noqa: E402
import doctor_skills  # noqa: E402
import doctor_version  # noqa: E402
import epic_worktree  # noqa: E402
import evidence as evidence_lib  # noqa: E402
from schema_lite import validate_schema  # noqa: E402, F401
import process_gate  # noqa: E402
import profiles as profiles_lib  # noqa: E402
import resolver as resolver_lib  # noqa: E402
import rigor as rigor_lib  # noqa: E402
import seal_lint  # noqa: E402
import variants as variants_lib  # noqa: E402
from doctor_skills import (  # noqa: E402, F401  (public re-exports)
    frontmatter_data,
    frontmatter_name,
    has_trigger,
    inline_link_targets,
    lint_skill,
    normalize_link,
    relative_links,
    strip_code_and_comments,
    undefined_references,
)
from doctor_skills import (  # noqa: E402, F401  (public re-exports)
    SKILL_NEGATION_RE,
    SKILL_REF_DEF_RE,
    SKILL_REF_USE_RE,
    SKILL_TRIGGER_RE,
)
from doctor_surfaces import (  # noqa: E402, F401
    surface_gate_errors,
    surface_gate_messages,
    surface_gate_warnings,
)
import routing  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("doctor: PyYAML required (python3 -m pip install pyyaml)")

ROOT = Path(__file__).resolve().parents[2]
DELIVERY = ROOT / "delivery"

ERRORS: list[str] = []
WARNS: list[str] = []
CHECKS = 0

CORE_LABELS = {
    "scope-confirmed",
    "agent-approved",
    "executing",
    "blocked",
    "deferred",
    "leaf-done",
    "human-qa",
    "epic-reconcile",
    "epic-done",
}

REQUIRED_FILES = [
    "VERSION",
    "CHANGELOG.md",
    "README.md",
    "ecosystem.yaml",
    "kit.config.yaml",
    "delivery/CONTRACT.md",
    "delivery/registry.yaml",
    "delivery/rigor.yaml",
    "delivery/templates/github-labels.json",
    "delivery/schemas/leaf.schema.json",
    "delivery/schemas/epic.schema.json",
    "delivery/schemas/evidence.schema.json",
    "delivery/schemas/closure.schema.json",
    "delivery/protocol/execution.md",
    "delivery/protocol/seal.md",
    "delivery/protocol/health-check.md",
    "delivery/protocol/evidence.md",
    "delivery/protocol/orca.md",
    "delivery/policies/quality-gates.md",
    "delivery/policies/escalation.md",
    "delivery/metrics/README.md",
    "delivery/scripts/guard.sh",
    "delivery/scripts/next-leaf.sh",
    "delivery/scripts/vendor_sync.py",
    "delivery/scripts/self_update.py",
    "delivery/scripts/evidence.py",
    "delivery/scripts/process_gate.py",
    "delivery/scripts/transition.py",
    "delivery/scripts/transition.sh",
    "delivery/scripts/capabilities.py",
    "delivery/scripts/risk_filter.py",
    "delivery/scripts/variants.py",
    "delivery/scripts/resolver.py",
    "delivery/scripts/adapt.py",
    "delivery/scripts/eval.py",
    "delivery/scripts/detect.py",
    "delivery/scripts/init.py",
    "delivery/scripts/profiles.py",
    "delivery/scripts/standards.py",
    "delivery/scripts/verify.py",
    "delivery/scripts/adopt.py",
    "delivery/schemas/profile.schema.json",
    "delivery/scripts/approvals.py",
    "delivery/scripts/protect_main.sh",
    "delivery/schemas/agent.schema.json",
    "delivery/capabilities/registry.yaml",
    "delivery/capabilities/role-matrix.yaml",
    "delivery/capabilities/levels.md",
    "delivery/capabilities/README.md",
    "delivery/schemas/capability.schema.json",
    "delivery/schemas/role-matrix.schema.json",
    "delivery/schemas/accept.schema.json",
    ".github/workflows/issue-doctor.yml",
    ".github/pull_request_template.md",
    "delivery/runbooks/pr-flow.md",
    "delivery/runbooks/adaptation.md",
    "delivery/runbooks/update.md",
    "delivery/fleet.yaml",
    "delivery/schemas/learning.schema.json",
    "delivery/scripts/learnings.py",
]

AGENT_FILES = ["ROLE.md", "how.md", "communicates.md", "dependencies.md", "SKILL.md"]
PATH_PREFIXES = (
    "delivery/",
    "schemas/",
    "policies/",
    "protocol/",
    "scripts/",
    "templates/",
    "profiles/",
    "packs/",
    "skills/",
    "archive/",
)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
TICK_RE = re.compile(r"`([A-Za-z0-9_./-]+)`")


def error(msg: str) -> None:
    ERRORS.append(msg)


def warn(msg: str) -> None:
    WARNS.append(msg)


def check(msg: str) -> None:
    global CHECKS
    CHECKS += 1


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        error(f"{rel(path)}: YAML okunamadı — {exc}")
        return None


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        error(f"{rel(path)}: JSON okunamadı — {exc}")
        return None


def skill_dir() -> Path:
    registry = load_yaml(DELIVERY / "registry.yaml") or {}
    skills = registry.get("skills") if isinstance(registry, dict) else {}
    raw = (skills.get("dir") if isinstance(skills, dict) else None) or "skills"
    return ROOT / raw


def check_files() -> None:
    check("required files")
    for name in REQUIRED_FILES:
        if not (ROOT / name).is_file():
            error(f"eksik dosya: {name}")


def check_schemas() -> None:
    check("schemas")
    for path in sorted((DELIVERY / "schemas").glob("*.json")):
        data = load_json(path)
        if data is None:
            continue
        if "$schema" not in data:
            error(f"{rel(path)}: $schema yok")
        if data.get("type") != "object":
            error(f"{rel(path)}: kök tip object değil")
    context_metrics.report_frequency(DELIVERY / "context" / "frequency.yaml", error)


def check_registry() -> None:
    check("registry")
    path = DELIVERY / "registry.yaml"
    reg = load_yaml(path)
    if not isinstance(reg, dict):
        error("registry.yaml: kök mapping değil")
        return

    paths = reg.get("paths") or {}
    if not isinstance(paths, dict) or not paths:
        error("registry.yaml: paths boş")
        return

    for name, spec in paths.items():
        if not isinstance(spec, dict):
            error(f"registry.paths.{name}: obje değil")
            continue
        if "extends" in spec and spec["extends"] not in paths:
            error(f"registry.paths.{name}: extends '{spec['extends']}' tanımsız")
        if not spec.get("agents") and not spec.get("extends"):
            error(f"registry.paths.{name}: agents veya extends yok")

    signals = reg.get("signals") or []
    if not isinstance(signals, list):
        error("registry.yaml: signals liste değil")
        signals = []
    for sig in signals:
        if not isinstance(sig, dict):
            error("registry.signals: obje değil")
            continue
        target = sig.get("default_path")
        if target not in paths:
            error(f"registry.signals.{sig.get('id')}: default_path '{target}' tanımsız")

    profiles = reg.get("profiles") or {}
    profile_default = profiles.get("default") if isinstance(profiles, dict) else None
    if profile_default and not (DELIVERY / "profiles" / f"{profile_default}.yaml").is_file():
        error(f"registry.profiles.default: {profile_default}.yaml yok")

    rigor = reg.get("rigor") or {}
    if not isinstance(rigor, dict):
        error("registry.yaml: rigor mapping değil")
    else:
        for key in ("config", "schema", "resolver"):
            value = rigor.get(key)
            if not isinstance(value, str) or not value.strip():
                error(f"registry.rigor.{key}: yol yok")
            elif not (ROOT / value).is_file():
                error(f"registry.rigor.{key}: dosya yok — {value}")

    # agent directories
    agents: set[str] = set(reg.get("role_order_default") or [])
    for spec in paths.values():
        if not isinstance(spec, dict):
            continue
        for key in ("agents", "on_demand", "agents_add"):
            agents.update(spec.get(key) or [])
    for sig in signals:
        if isinstance(sig, dict):
            for key in ("required", "optional", "on_demand"):
                agents.update((sig.get("agents") or {}).get(key) or [])
    agents.discard("orchestrator")
    for agent in sorted(agents):
        directory = DELIVERY / "agents" / agent
        if not directory.is_dir():
            error(f"registry agent dizini yok: delivery/agents/{agent}")
            continue
        for name in AGENT_FILES:
            if not (directory / name).is_file():
                error(f"delivery/agents/{agent}: {name} eksik")

    ordered = set(reg.get("role_order_default") or [])
    missing_order = agents - ordered
    if missing_order:
        warn(f"registry.role_order_default eksik: {', '.join(sorted(missing_order))}")

    # policy table drift
    policy = DELIVERY / "policies" / "path-routing.md"
    if policy.is_file():
        text = policy.read_text(encoding="utf-8")
        policy_paths = set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", text, re.M))
        registry_paths = set(paths)
        if policy_paths and policy_paths != registry_paths:
            only_reg = registry_paths - policy_paths
            only_pol = policy_paths - registry_paths
            detail = []
            if only_reg:
                detail.append(f"registry'de fazla: {', '.join(sorted(only_reg))}")
            if only_pol:
                detail.append(f"policy'de fazla: {', '.join(sorted(only_pol))}")
            error("path-routing.md ↔ registry paths uyuşmuyor — " + "; ".join(detail))


def check_rigor(config: Path | None = None) -> None:
    check("rigor")
    path = Path(config) if config else DELIVERY / "rigor.yaml"
    messages: list[str] = []
    try:
        messages.extend(rigor_lib.validate_file(path))
    except rigor_lib.RigorError as exc:
        messages.append(str(exc))
    try:
        rigor_lib.load_effective(ROOT, rigor_path=path if config else None)
    except rigor_lib.RigorError as exc:
        messages.append(str(exc))
    for message in dict.fromkeys(messages):
        error(f"rigor: {message}")


def check_labels() -> None:
    check("labels")
    path = DELIVERY / "templates" / "github-labels.json"
    data = load_json(path)
    if not isinstance(data, list):
        return
    names = [item.get("name") for item in data if isinstance(item, dict)]
    if len(names) != len(set(names)):
        error(f"{rel(path)}: yinelenen etiket adı")
    registry = load_yaml(DELIVERY / "registry.yaml") or {}
    labels = registry.get("labels") if isinstance(registry, dict) else {}
    if not isinstance(labels, dict):
        error("registry.yaml: labels mapping değil")
        labels = {}
    reg_labels = set(labels.values())
    missing = reg_labels - set(names)
    if missing:
        error(f"{rel(path)}: registry etiketleri eksik — {', '.join(sorted(missing))}")
    missing_core = CORE_LABELS - set(names)
    if missing_core:
        error(f"{rel(path)}: çekirdek etiketler eksik — {', '.join(sorted(missing_core))}")


def resolve_target(source: Path, target: str) -> Path | None:
    target = target.split("#")[0].strip()
    if not target or target.startswith(("http://", "https://", "mailto:", "/")):
        return None
    if any(char in target for char in "*{}<>$"):
        return None
    candidates = [source.parent / target, DELIVERY / target, ROOT / target]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def _capability_surface_enum(schema: dict) -> list[str] | None:
    """`match.surfaces.items.enum` — registry ile senkron sabit surface listesi."""
    try:
        items = schema["properties"]["capabilities"]["additionalProperties"][
            "properties"
        ]["match"]["properties"]["surfaces"]["items"]
    except (KeyError, TypeError):
        return None
    enum = items.get("enum") if isinstance(items, dict) else None
    return [str(item) for item in enum] if isinstance(enum, list) else None


def check_capabilities() -> None:
    check("capabilities")
    registry = load_yaml(DELIVERY / "capabilities" / "registry.yaml")
    matrix = load_yaml(DELIVERY / "capabilities" / "role-matrix.yaml")
    if not isinstance(registry, dict) or not isinstance(matrix, dict):
        return

    capability_schema = load_json(DELIVERY / "schemas" / "capability.schema.json")
    matrix_schema = load_json(DELIVERY / "schemas" / "role-matrix.schema.json")
    if capability_schema:
        for message in validate_schema(registry, capability_schema, "capability"):
            error(message)
    if matrix_schema:
        for message in validate_schema(matrix, matrix_schema, "role-matrix"):
            error(message)

    # Şema sabit enum taşır; registry yeni bir surface kazanırsa şema da güncellenmeli.
    declared_surfaces = registry.get("surfaces")
    if capability_schema and isinstance(declared_surfaces, dict):
        enum = _capability_surface_enum(capability_schema)
        if enum is not None:
            missing = sorted(set(declared_surfaces) - set(enum))
            extra = sorted(set(enum) - set(declared_surfaces))
            if missing:
                error(
                    "capability.schema.json: match.surfaces enum eksik surface: "
                    + ", ".join(missing)
                )
            if extra:
                error(
                    "capability.schema.json: match.surfaces enum tanımsız surface: "
                    + ", ".join(extra)
                )

    registry_config = load_yaml(DELIVERY / "registry.yaml") or {}
    roles = set(registry_config.get("role_order_default") or []) | {"orchestrator"}
    packs = {
        path.name
        for path in (DELIVERY / "packs").iterdir()
        if path.is_dir()
    }
    for message in capabilities_lib.validate_references(
        registry, matrix, roles, packs, roles
    ):
        error(f"capabilities: {message}")


def check_profiles() -> None:
    check("profiles")
    schema = load_json(DELIVERY / "schemas" / "profile.schema.json")
    capability_config = load_yaml(DELIVERY / "capabilities" / "registry.yaml") or {}
    capabilities = set((capability_config.get("capabilities") or {}).keys())
    pack_names = {
        path.name for path in (DELIVERY / "packs").iterdir() if path.is_dir()
    }
    for path in sorted((DELIVERY / "profiles").glob("*.yaml")):
        data = load_yaml(path)
        if not isinstance(data, dict):
            continue
        if schema:
            for message in validate_schema(data, schema, f"profile.{path.stem}"):
                error(message)
        if data.get("id") != path.stem:
            error(f"{rel(path)}: id '{data.get('id')}' dosya adıyla eşleşmiyor")
        for cap_id in data.get("capabilities") or []:
            if cap_id not in capabilities:
                error(f"{rel(path)}: bilinmeyen capability {cap_id}")
        for pack in data.get("platform_packs") or []:
            if pack not in pack_names:
                error(f"{rel(path)}: bilinmeyen pack {pack}")
        for skill in data.get("required_skills") or []:
            if not (ROOT / "skills" / str(skill) / "SKILL.md").is_file():
                error(f"{rel(path)}: bilinmeyen skill {skill}")
    for message in profiles_lib.validate_project(ROOT, capabilities, pack_names):
        error(f"profiles: {message}")


def check_agent_variants() -> None:
    check("agent variants")
    registry_config = load_yaml(DELIVERY / "registry.yaml") or {}
    variants_config = registry_config.get("agent_variants") or {}
    roles = variants_config.get("roles") or []
    schema = load_json(DELIVERY / "schemas" / "agent.schema.json")
    capability_config = load_yaml(DELIVERY / "capabilities" / "registry.yaml") or {}
    capabilities = capability_config.get("capabilities") or {}
    matrix = load_yaml(DELIVERY / "capabilities" / "role-matrix.yaml") or {}
    known_roles = set(registry_config.get("role_order_default") or []) | {
        "orchestrator"
    }

    for role in roles:
        path = DELIVERY / "agents" / role / "agent.yaml"
        if not path.is_file():
            error(f"agent variant: {role}/agent.yaml yok")
            continue
        agent = load_yaml(path)
        if not isinstance(agent, dict):
            continue
        if schema:
            for message in validate_schema(agent, schema, f"agent.{role}"):
                error(message)
        for message in variants_lib.validate_agent(
            role, agent, capabilities, known_roles, matrix=matrix
        ):
            error(f"agent variant: {message}")

    for directory in (DELIVERY / "agents").iterdir():
        if not directory.is_dir():
            continue
        if (directory / "variants").is_dir() and not (
            directory / "agent.yaml"
        ).is_file():
            error(
                f"agent variant: {directory.name}/variants var ama agent.yaml yok"
            )


def check_links() -> None:
    check("links")
    docs = list(DELIVERY.rglob("*.md"))
    skills = skill_dir()
    if skills.is_dir():
        docs += list(skills.rglob("*.md"))
    for extra in ("README.md", "AGENTS.md"):
        path = ROOT / extra
        if path.is_file():
            docs.append(path)

    for path in docs:
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = resolve_target(path, target)
            if resolved is not None and not resolved.exists():
                error(f"{rel(path)}: kırık link — {target}")

        for match in TICK_RE.finditer(text):
            target = match.group(1)
            if not target.startswith(PATH_PREFIXES):
                continue
            if "." not in target.rsplit("/", 1)[-1]:
                continue
            resolved = resolve_target(path, target)
            if resolved is not None and not resolved.exists():
                error(f"{rel(path)}: kırık yol — `{target}`")


def check_legacy(verbose: bool) -> None:
    check("archive references")
    hits: list[str] = []
    targets: list[Path] = []
    for root in [DELIVERY, skill_dir()]:
        if not root.is_dir():
            continue
        targets += [
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".md", ".yaml", ".yml", ".json"}
        ]
    for extra in ("README.md", "AGENTS.md"):
        path = ROOT / extra
        if path.is_file():
            targets.append(path)

    for path in targets:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = re.search(r"(?<![A-Za-z0-9_])(?:old/|archive/)", line)
            if match is None:
                continue
            prefix = line[max(0, match.start() - 40) : match.start()]
            if not re.search(r"arşiv|archive", prefix, re.I):
                hits.append(f"{rel(path)}:{number}")
    if hits:
        warn(f"{len(hits)} runtime referansı arşive (`archive/v1.7/`) kaldı — dokunulan dosyada yeni yola geçir")
        if verbose:
            for hit in hits:
                print(f"  · {hit}")


def check_model_policy(root: Path = ROOT) -> None:
    check("model policy")
    config = load_yaml(root / "kit.config.yaml") or {}
    orca = config.get("orca") if isinstance(config.get("orca"), dict) else {}
    defaults = orca.get("role_defaults") or {}
    if not isinstance(defaults, dict):
        return
    overrides = [
        str(role)
        for role, value in defaults.items()
        if isinstance(value, dict) and (value.get("model") or value.get("effort"))
    ]
    if overrides and orca.get("allow_model_override") is not True:
        error(
            "kit.config.yaml: role_defaults model/effort (roller: "
            + ", ".join(sorted(overrides))
            + ") için orca.allow_model_override: true gerekli"
        )
    if any(
        isinstance(value, dict) and value.get("effort") for value in defaults.values()
    ):
        warn(
            "kit.config.yaml: opencode2 --effort desteklemiyor; effort yalnız "
            "destekleyen agent'ta kullanılmalı"
        )


def check_unsealed_work(root: Path = ROOT) -> None:
    check("unsealed work")
    errors, warnings = process_gate.unsealed_report(root, bool(os.environ.get("CI")))
    for message in errors: error(message)
    for message in warnings: warn(message)

def check_version() -> None:
    check("version")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^##\s+(\d+\.\d+\.\d+)", changelog, re.M)
    if not match:
        error("CHANGELOG.md: sürüm başlığı bulunamadı")
    elif match.group(1) != version:
        error(f"VERSION ({version}) ≠ CHANGELOG ({match.group(1)})")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if f"**{version}**" not in readme:
        warn(f"README.md sürüm başlığı {version} değil")
    short = ".".join(version.split(".")[:2])
    for name, prefix in (
        ("delivery/FLOW.md", "# Delivery flow — v"),
        ("delivery/CONTRACT.md", "# Delivery contract — v"),
    ):
        path = ROOT / name
        if path.is_file() and prefix + short not in path.read_text(encoding="utf-8"):
            error(f"{name}: sürüm başlığı v{short} değil")
    registry = (ROOT / "delivery" / "registry.yaml").read_text(encoding="utf-8")
    if f"— v{short}" not in registry:
        error(f"delivery/registry.yaml: sürüm başlığı v{short} değil")
    check_version_drift(ROOT, version)


def check_version_drift(root: Path, version: str) -> None:
    """kit.config.yaml ve AGENTS.md başlıkları VERSION ile hizalı olmalı."""
    doctor_version.check_version_drift(root, version, error, warn, load_yaml)


def check_fleet() -> None:
    check("fleet")
    path = DELIVERY / "fleet.yaml"
    data = load_yaml(path)
    if not isinstance(data, dict):
        error("fleet.yaml: kök mapping değil")
        return
    repos = data.get("repos") or []
    if not repos:
        warn("fleet.yaml: repos listesi boş")
        return
    seen: set[str] = set()
    for entry in repos:
        name = entry.get("repo") if isinstance(entry, dict) else None
        if not name or "/" not in str(name):
            error(f"fleet.yaml: geçersiz repo adı — {name}")
            continue
        if name in seen:
            error(f"fleet.yaml: tekrar eden repo — {name}")
        seen.add(name)


def check_ecosystem() -> None:
    check("ecosystem")
    eco = load_yaml(ROOT / "ecosystem.yaml")
    if not isinstance(eco, dict):
        return
    products = eco.get("products") or {}
    if not products:
        error("ecosystem.yaml: products boş")
    for name, product in products.items():
        for surface, spec in (product.get("surfaces") or {}).items():
            raw = (spec or {}).get("path")
            if not raw:
                error(f"ecosystem.{name}.{surface}: path yok")
                continue
            if not (ROOT / raw).exists():
                error(f"ecosystem.{name}.{surface}: path yok — {raw}")
            surface_gate_messages(str(name), str(surface), spec or {}, error, warn)
    tracker = (eco.get("tracker") or {}).get("repo")
    if tracker:
        result = run(["git", "remote", "get-url", "origin"])
        if result and tracker not in result:
            warn(f"ecosystem tracker.repo ({tracker}) origin ile uyuşmuyor")

    config = load_yaml(ROOT / "kit.config.yaml") or {}
    protocol = str((config.get("kit") or {}).get("protocol", ""))
    if protocol != "2":
        error(f"kit.config.yaml: kit.protocol '{protocol}' (beklenen 2)")


def check_skills() -> None:
    check("skill names")
    skills_root = skill_dir()
    roots = [DELIVERY, skills_root]
    seen: dict[str, str] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("SKILL.md"):
            text = path.read_text(encoding="utf-8")
            name = frontmatter_name(text)
            if not name:
                error(f"{rel(path)}: frontmatter name yok")
                continue
            if name in seen:
                error(f"SKILL name tekrarlı: '{name}' — {seen[name]} / {rel(path)}")
            seen[name] = rel(path)

    registry = load_yaml(DELIVERY / "registry.yaml") or {}
    skills = registry.get("skills") if isinstance(registry, dict) else {}
    if not isinstance(skills, dict):
        error("registry.yaml: skills mapping değil")
        skills = {}
    expected = skills.get("runtime") or []
    if not isinstance(expected, list):
        error("registry.yaml: skills.runtime liste değil")
        expected = []
    if not expected:
        warn("registry.skills.runtime boş")
    for name in expected:
        path = skills_root / name / "SKILL.md"
        if not path.is_file():
            error(f"registry.skills.runtime: {rel(path)} yok")
            continue
        text = path.read_text(encoding="utf-8")
        declared = frontmatter_name(text) or ""
        if declared != name:
            error(f"{rel(path)}: frontmatter adı '{declared}' ('{name}' bekleniyor)")

    check("scoped skills")
    scoped = skills.get("scoped")
    if scoped is not None and not isinstance(scoped, dict):
        error("registry.yaml: skills.scoped mapping değil")
        scoped = {}
    seen_scoped: dict[str, str] = {}
    capability_registry = load_yaml(DELIVERY / "capabilities" / "registry.yaml") or {}
    known_caps = set((capability_registry.get("capabilities") or {}).keys())
    for capability, names in (scoped or {}).items():
        if str(capability) not in known_caps:
            error(f"registry.skills.scoped: bilinmeyen capability '{capability}'")
        if not isinstance(names, list):
            error(f"registry.skills.scoped.{capability} liste değil")
            continue
        for name in names:
            name = str(name)
            path = skills_root / name / "SKILL.md"
            if not path.is_file():
                error(f"registry.skills.scoped.{capability}: {rel(path)} yok")
                continue
            declared_name = frontmatter_name(path.read_text(encoding="utf-8")) or ""
            if declared_name != name:
                error(
                    f"{rel(path)}: frontmatter adı '{declared_name}' "
                    f"('{name}' bekleniyor)"
                )
            if name in seen_scoped:
                error(
                    "registry.skills.scoped: "
                    f"'{name}' iki capability'de — {seen_scoped[name]} / {capability}"
                )
            seen_scoped[name] = str(capability)
            if name in expected:
                error(
                    f"registry.skills.scoped: '{name}' hem runtime hem scoped"
                )

    doctor_skills.lint_runtime_skills(skills_root, check, error, warn, rel)


def run(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def check_mcp(root: Path = ROOT) -> None:
    check("mcp")
    for message in doctor_mcp.check_mcp_self(root):
        error(message)


def check_compat() -> None:
    doctor_compat.check_compat(ROOT, error, check)


def lint_runtime_skills(root: Path) -> None:
    doctor_skills.lint_runtime_skills(root, check, error, warn, rel)


def check_role_contracts() -> None:
    check("role contracts")
    registry = load_yaml(DELIVERY / "registry.yaml") or {}
    roles = registry.get("role_order_default") if isinstance(registry, dict) else []
    if not isinstance(roles, list) or not roles:
        error("registry.role_order_default boş")
        return
    for role in roles:
        path = DELIVERY / "agents" / role / "how.md"
        if not path.is_file():
            error(f"{rel(path)}: yok")
        elif "## Contract" not in path.read_text(encoding="utf-8"):
            error(f"{rel(path)}: ## Contract eksik")


def check_issue_body(
    body: str,
    labels: list[str],
    comments: list[str] | None = None,
    checkpoint: str | None = None,
    root: Path = ROOT,
    repo: str | None = None,
    title: str = "",
    evidence_text: str | None = None,
) -> None:
    check("issue seal")
    match = re.search(r"```yaml\s+demir-kit\s*\n(.*?)```", body, re.S)
    if not match:
        error("issue: `yaml demir-kit` bloğu yok")
        return
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        error(f"issue: seal YAML geçersiz — {exc}")
        return
    if not isinstance(data, dict):
        error("issue seal: kök mapping değil")
        return

    schema = load_json(DELIVERY / "schemas" / "leaf.schema.json")
    if schema:
        for message in validate_schema(data, schema):
            error(f"issue seal {message}")

    for item in seal_lint.lint(data):
        message = f"seal lint {item['path']}: {item['message']}"
        if item["severity"] == "error":
            error(message)
        else:
            warn(message)

    package_version = data.get("package_version", 1)
    if not isinstance(package_version, int):
        package_version = 1
    acs = data.get("acceptance_criteria") or []
    ac_ids = [item.get("id") for item in acs if isinstance(item, dict)]
    if len(ac_ids) != len(set(ac_ids)):
        error("issue seal: AC id tekrarlı")

    cps = data.get("checkpoints") or []
    cp_ids = [item.get("id") for item in cps if isinstance(item, dict)]
    entry = data.get("entry") if isinstance(data.get("entry"), dict) else {}
    entry_kind = entry.get("kind")
    if len(cp_ids) != len(set(cp_ids)):
        error("issue seal: CP id tekrarlı")
    if checkpoint and checkpoint != "CP-HEALTH" and checkpoint not in cp_ids:
        error(f"checkpoint '{checkpoint}' bu leaf'in seal'inde yok")

    plans = data.get("tests_plan") or []
    covered: set[str] = set()
    plan_cps: set[str] = set()
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        cp_id = plan.get("checkpoint_id")
        plan_cps.add(cp_id)
        if cp_ids and cp_id not in cp_ids:
            error(f"tests_plan: {cp_id} checkpoints içinde yok")
        for case in plan.get("cases") or []:
            ac = case.get("ac")
            covered.add(ac)
            if ac_ids and ac not in ac_ids:
                error(f"tests_plan: {case.get('id')} → {ac} tanımsız AC")
    missing_ac = set(ac_ids) - covered
    if missing_ac:
        error(f"tests_plan kapsamıyor: {', '.join(sorted(missing_ac))}")
    missing_cp = set(cp_ids) - plan_cps
    if missing_cp:
        error(f"tests_plan eksik CP: {', '.join(sorted(missing_cp))}")

    check_kinds = {"gate", "unit", "snap", "manual", "doc"}
    cp_gates = {
        cp.get("id"): (cp.get("gates") if isinstance(cp.get("gates"), dict) else {})
        for cp in cps
        if isinstance(cp, dict)
    }
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        plan_cp = plan.get("checkpoint_id")
        gates = cp_gates.get(plan_cp, {})
        for case in plan.get("cases") or []:
            if not isinstance(case, dict):
                continue
            kind = case.get("check")
            if kind is None:
                if package_version >= 4:
                    error(
                        f"tests_plan: {case.get('id')} denetim türü (check) yok"
                    )
                continue
            if kind not in check_kinds:
                error(
                    f"tests_plan: {case.get('id')} check '{kind}' geçersiz "
                    f"(gate|unit|snap|manual|doc)"
                )
                continue
            if kind == "snap" and gates.get("ui") is not True:
                error(
                    f"tests_plan: {case.get('id')} snap türü ama {plan_cp} "
                    "gates.ui kapalı"
                )
            if kind == "manual" and gates.get("human") is not True:
                error(
                    f"tests_plan: {case.get('id')} manual türü ama {plan_cp} "
                    "gates.human kapalı"
                )

    for cp in cps:
        if not isinstance(cp, dict):
            continue
        gates = cp.get("gates") or {}
        if gates.get("behavior") is not True:
            error(f"{cp.get('id')}: gates.behavior true olmalı")
        if entry_kind == "refactor" and gates.get("architect") is not True:
            error(f"{cp.get('id')}: refactor leaf'te gates.architect true olmalı")
        for dep in cp.get("depends_on") or []:
            if dep not in cp_ids:
                error(f"{cp.get('id')}: depends_on '{dep}' tanımsız")

    risk = (data.get("risk") or {}).get("level")
    if risk not in {"low", "medium", "high", "critical"}:
        error(f"issue seal: risk '{risk}' geçersiz")

    profile_name = (data.get("factory") or {}).get("profile")
    profile = {}
    if profile_name:
        profile_path = DELIVERY / "profiles" / f"{profile_name}.yaml"
        if profile_path.is_file():
            profile = load_yaml(profile_path) or {}
    try:
        project_profiles = profiles_lib.compose(root)
    except ValueError:
        project_profiles = {}
    profile_extra_gates = set((profile or {}).get("extra_gates") or [])
    if not profile_name:
        profile_extra_gates = set(project_profiles.get("extra_gates") or [])
    needs_platform = bool(
        (profile or {}).get("platform_packs")
        or (profile or {}).get("extra_gates")
        or project_profiles.get("platform_packs")
        or profile_extra_gates
    )

    registry = load_yaml(DELIVERY / "registry.yaml") or {}
    path_id, signal = routing.detect_path(registry, "", body, data)
    path_agents = routing.resolve_agents(registry, path_id, signal)
    allowed_agents = (
        set(path_agents["active"])
        | set(path_agents["on_demand"])
        | set(path_agents["optional"])
    )
    capability_registry = load_yaml(DELIVERY / "capabilities" / "registry.yaml") or {}
    declared_surfaces = capability_registry.get("surfaces")
    if isinstance(declared_surfaces, dict):
        for surface in data.get("surfaces") or []:
            if str(surface) not in declared_surfaces:
                error(
                    f"issue seal: tanımsız surface '{surface}' — "
                    "delivery/capabilities/registry.yaml surfaces altına ekle"
                )
    ecosystem = load_yaml(root / "ecosystem.yaml") or {}
    signals = resolver_lib.scoped_signals(ecosystem, data)
    declared = resolver_lib.load_declared(root)
    # Historical evidence must stay valid after a project-level exclude; the
    # seal's own surfaces decide which roles could have produced it. Risk floor
    # and capability gaps, however, must honour the project's real excludes.
    declared_for_issue = {
        "version": 1,
        "include": declared.get("include") or [],
        "exclude": [],
    }
    resolution_for_evidence = resolver_lib.resolve(
        capability_registry,
        resolver_lib.load_matrix(),
        resolver_lib.load_agent_variants(),
        path_id,
        signals,
        f"{title}\n{data.get('intent', '')}\n{routing.strip_seal(body)}",
        declared=declared_for_issue,
        project=root,
    )
    resolution = resolver_lib.resolve(
        capability_registry,
        resolver_lib.load_matrix(),
        resolver_lib.load_agent_variants(),
        path_id,
        signals,
        f"{title}\n{data.get('intent', '')}\n{routing.strip_seal(body)}",
        declared=declared,
        project=root,
    )
    for capability in resolution_for_evidence["capabilities"]:
        allowed_agents.update(
            ((capability_registry.get("capabilities") or {}).get(capability) or {})
            .get("roles", {})
            .keys()
        )
    risk_floor = resolution.get("risk_floor", "low")
    # An exclude must not silently lower the risk below what the project would
    # otherwise owe; keep the decision visible in doctor output.
    effective_risk = risk_floor
    if resolver_lib.RISK_ORDER.get(risk or "low", 0) > resolver_lib.RISK_ORDER.get(
        risk_floor, 0
    ):
        effective_risk = risk or "low"
    suppressed = sorted(
        set(resolution_for_evidence["capabilities"]) - set(resolution["capabilities"])
    )
    for capability in suppressed:
        spec = (capability_registry.get("capabilities") or {}).get(capability) or {}
        suppressed_floor = spec.get("risk_floor") or "low"
        if resolver_lib.RISK_ORDER.get(suppressed_floor, 0) > resolver_lib.RISK_ORDER.get(
            effective_risk, 0
        ):
            warn(
                f"capability exclude: {capability} proje exclude listesinde; "
                f"risk tabanı '{suppressed_floor}' uygulanmadı (seal: "
                f"'{effective_risk}')"
            )
    if resolver_lib.RISK_ORDER.get(risk_floor, 0) > resolver_lib.RISK_ORDER.get(
        risk or "low", 0
    ):
        error(
            f"issue seal: capability risk_floor '{risk_floor}' seal risk "
            f"'{risk}' üstünde; seal riskini yükselt"
        )
    if package_version >= 4:
        human_caps = [
            capability
            for capability in resolution.get("capabilities") or []
            if "human"
            in (
                (capability_registry.get("capabilities") or {}).get(capability) or {}
            ).get("gates", [])
        ]
        if human_caps and not any(
            (cp.get("gates") or {}).get("human") is True
            for cp in cps
            if isinstance(cp, dict)
        ):
            error(
                "capability insan kapısı istiyor: "
                + ", ".join(human_caps)
                + " — bir checkpoint'te gates.human true olmalı"
            )
    if risk in {"high", "critical"}:
        seen_gaps = set()
        for gap in resolution.get("variant_gaps") or []:
            key = (gap.get("role"), gap.get("capability"))
            if key in seen_gaps:
                continue
            seen_gaps.add(key)
            error(
                f"capability gap: {gap.get('role')} / {gap.get('capability')} — "
                f"{gap.get('reason')}"
            )

    if evidence_text is not None or ("leaf-done" in labels and comments is not None):
        evidence_schema = load_json(DELIVERY / "schemas" / "evidence.schema.json")
        evidence: dict[str, dict] = {}
        blocks = [evidence_text] if evidence_text is not None else (comments or [])
        for comment in blocks:
            block = re.search(r"```yaml\s+demir-kit-evidence\s*\n(.*?)```", comment, re.S)
            if not block:
                continue
            try:
                record = yaml.safe_load(block.group(1)) or {}
            except yaml.YAMLError as exc:
                error(f"evidence: YAML geçersiz — {exc}")
                continue
            if not isinstance(record, dict):
                error("evidence: blok mapping değil")
                continue
            if not record.get("cp_id"):
                error("evidence: cp_id yok")
                continue
            if evidence_text is not None and record["cp_id"] not in cp_ids:
                error(f"evidence: cp_id '{record['cp_id']}' seal'de yok")
            evidence[record["cp_id"]] = record

        if evidence_text is not None:
            if not evidence:
                error("evidence: kayıt bulunamadı")
            elif checkpoint and checkpoint != "CP-HEALTH" and checkpoint not in evidence:
                error(f"evidence: checkpoint {checkpoint} için kayıt yok")

        # Only the latest evidence per CP is authoritative; earlier retries stay
        # in the issue history without blocking the leaf.
        for cp_id, record in evidence.items():
            agent = record.get("agent")
            if not agent:
                warn(f"{cp_id}: evidence agent alanı yok")
            elif agent not in allowed_agents:
                error(f"{cp_id}: agent '{agent}' bu path'te aktif değil ({path_id})")
            if evidence_schema:
                for message in validate_schema(record, evidence_schema, f"{cp_id}.evidence"):
                    error(message)
            if package_version >= 3 and epic_worktree.epic_worktree_enabled(root):
                worktree = record.get("worktree")
                if not isinstance(worktree, dict):
                    error(
                        f"{cp_id}: package_version 3 için worktree bloğu gerekli "
                        "(name, path, branch, epic)"
                    )
                else:
                    for key in ("name", "path", "branch", "epic"):
                        if not str(worktree.get(key) or "").strip():
                            error(f"{cp_id}: worktree.{key} yok")
                has_worker = bool(record.get("worker") or record.get("workers"))
                degrade = record.get("degrade")
                if not has_worker and not isinstance(degrade, dict):
                    error(
                        f"{cp_id}: Orca worker kaydı veya kayıtlı degrade gerekli"
                    )
                if isinstance(degrade, dict):
                    if not str(degrade.get("reason") or "").strip():
                        error(f"{cp_id}: degrade.reason yok")
                    recorded = any(
                        "run degrade:" in (body or "") for body in (comments or [])
                    )
                    if not recorded:
                        error(
                            f"{cp_id}: degrade issue'ya `run degrade:` yorumuyla "
                            "kaydedilmemiş"
                        )
                orca = record.get("orca")
                if isinstance(orca, dict):
                    for key in ("run_id", "task_id", "dispatch_id", "outcome"):
                        if not str(orca.get(key) or "").strip():
                            error(f"{cp_id}: orca.{key} yok")
                elif not isinstance(degrade, dict):
                    error(
                        f"{cp_id}: Orca trace (orca bloğu) yok; degrade modunda "
                        "degrade bloğu yeterli"
                    )
                reviews = record.get("reviews") or {}
                if (
                    risk in {"high", "critical"}
                    and reviews.get("human") == "approved"
                    and not (isinstance(orca, dict) and orca.get("gate_id"))
                ):
                    warn(f"{cp_id}: insan onayı var ama Orca gate_id yok")
            verification = record.get("verification")
            if package_version >= 2 and not verification:
                error(f"{cp_id}: package_version 2+ için verification bloğu gerekli")
            if entry_kind == "refactor" and not (
                isinstance(verification, dict)
                and isinstance(verification.get("refactor"), dict)
            ):
                error(f"{cp_id}: refactor leaf verification.refactor bloğu ister")
            if isinstance(verification, dict):
                block = verification.get("refactor")
                if isinstance(block, dict):
                    if entry_kind != "refactor":
                        error(
                            f"{cp_id}: verification.refactor yalnız refactor "
                            "leaf'te kullanılır"
                        )
                    files = block.get("files_changed")
                    if isinstance(files, int) and 10 < files <= 20:
                        warn(
                            f"{cp_id}: refactor {files} dosya değiştirdi; adımlara böl"
                        )
            if verification:
                for message in evidence_lib.verify(
                    verification,
                    root=root,
                    repo=repo,
                    risk=risk or "low",
                    implementer=agent,
                ):
                    error(f"{cp_id}: verification — {message}")
            findings = record.get("findings") or []
            if not isinstance(findings, list):
                error(f"{cp_id}: findings liste değil")
                findings = []
            for finding in findings:
                if not isinstance(finding, dict):
                    error(f"{cp_id}: findings öğesi mapping değil")
                    continue
                if finding.get("status") == "open":
                    error(f"{cp_id}: açık bulgu varken pass olamaz")

        cp_gates = {
            cp.get("id"): (cp.get("gates") if isinstance(cp.get("gates"), dict) else {})
            for cp in cps
            if isinstance(cp, dict)
        }
        checked = cp_ids if evidence_text is None else [
            cp_id for cp_id in cp_ids if cp_id in evidence
        ]
        for cp_id in checked:
            record = evidence.get(cp_id)
            if not record or record.get("status") != "pass":
                error(f"leaf-done ama {cp_id} evidence yok/pass değil")
                continue
            reviews = record.get("reviews")
            if not isinstance(reviews, dict):
                reviews = {}
            adversarial = reviews.get("adversarial")
            if not isinstance(adversarial, dict):
                adversarial = {}
            if risk in {"high", "critical"}:
                if adversarial.get("reviewer_a") != "approved" or adversarial.get(
                    "reviewer_b"
                ) != "approved":
                    error(f"{cp_id}: risk {risk} için iki adversarial onay gerekli")
                if reviews.get("architect") != "approved":
                    error(f"{cp_id}: risk {risk} için architect onayı gerekli")
            elif adversarial.get("reviewer_a") != "approved":
                error(f"{cp_id}: en az bir reviewer onayı gerekli")
            gates = cp_gates.get(cp_id, {})
            if gates.get("ui") and reviews.get("ui") != "pass":
                error(f"{cp_id}: gates.ui açık ama UI onayı yok")
            if entry_kind == "refactor" and gates.get("ui"):
                verification_value = record.get("verification")
                proof = (
                    verification_value.get("refactor")
                    if isinstance(verification_value, dict)
                    else {}
                )
                if not isinstance(proof, dict) or proof.get("ui_unchanged") is not True:
                    error(f"{cp_id}: refactor UI checkpoint'te ui_unchanged ister")
            if package_version >= 4 and gates.get("human") and reviews.get(
                "human"
            ) != "approved":
                error(f"{cp_id}: gates.human açık ama insan onayı yok")
            if gates.get("architect") and reviews.get("architect") != "approved":
                error(f"{cp_id}: gates.architect açık ama architect onayı yok")
            if "architect" in profile_extra_gates and reviews.get(
                "architect"
            ) != "approved":
                error(f"{cp_id}: profil architect gate'i istiyor")
            if "commercial" in profile_extra_gates and reviews.get(
                "commercial"
            ) != "approved":
                error(f"{cp_id}: profil commercial gate'i istiyor")
            if "human" in profile_extra_gates and reviews.get("human") != "approved":
                error(f"{cp_id}: profil human gate'i istiyor")
            if "platform" in profile_extra_gates and reviews.get(
                "platform"
            ) != "pass":
                error(f"{cp_id}: profil platform gate'i istiyor")
            behavior = record.get("behavior")
            if not isinstance(behavior, dict):
                behavior = {}
            if behavior.get("exit_code") != 0:
                error(f"{cp_id}: behavior exit_code 0 değil")
            tests = record.get("tests") or []
            if not isinstance(tests, list):
                error(f"{cp_id}: tests liste değil")
                tests = []
            for test in tests:
                if not isinstance(test, dict):
                    error(f"{cp_id}: test öğesi mapping değil")
                    continue
                if test.get("result") != "pass":
                    error(f"{cp_id}: test '{test.get('case')}' pass değil")
            if (
                risk in {"high", "critical"}
                and needs_platform
                and reviews.get("platform") != "pass"
            ):
                error(f"{cp_id}: profil platform gate'i istiyor (reviews.platform pass)")
            if risk == "high" and reviews.get("human") != "approved":
                error(f"{cp_id}: risk high için insan onayı gerekli (reviews.human)")
            if risk == "critical":
                if reviews.get("human") != "approved":
                    error(f"{cp_id}: risk critical için insan onayı gerekli (reviews.human)")
                if reviews.get("human_second") != "approved":
                    error(
                        f"{cp_id}: risk critical için ikinci insan onayı gerekli "
                        "(reviews.human_second)"
                    )
            if (risk == "critical" or gates.get("commercial")) and reviews.get(
                "commercial"
            ) != "approved":
                error(
                    f"{cp_id}: commercial gate için onay gerekli (reviews.commercial)"
                )
            if gates.get("ui"):
                if reviews.get("comparison_valid") is not True:
                    error(f"{cp_id}: gates.ui açık ama comparison_valid true değil")
                if reviews.get("ui_visual") != "pass":
                    error(f"{cp_id}: gates.ui açık ama visual reviewer pass değil")
                if reviews.get("ui_interaction") != "pass":
                    error(f"{cp_id}: gates.ui açık ama interaction reviewer pass değil")


def fetch_issue_labels(repo: str, number: int) -> set[str]:
    raw = run(["gh", "api", f"repos/{repo}/issues/{number}"])
    if not raw:
        return set()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    return {item.get("name") for item in data.get("labels", [])}


def fetch_comments(repo: str, number: int, page_size: int = 100) -> list[dict]:
    """Fetch every issue comment; GitHub caps a page at 100."""
    comments: list[dict] = []
    page = 1
    while True:
        raw = run(
            [
                "gh",
                "api",
                f"repos/{repo}/issues/{number}/comments?per_page={page_size}&page={page}",
            ]
        )
        if not raw:
            error(f"issue #{number}: yorumlar okunamadı (sayfa {page})")
            break
        try:
            batch = json.loads(raw)
        except json.JSONDecodeError:
            break
        if not isinstance(batch, list) or not batch:
            break
        comments.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return comments


def normalize_evidence_text(text: str | None) -> str | None:
    """Accept a plain evidence YAML file by wrapping it in a fenced block."""
    if not text or "demir-kit-evidence" in text:
        return text
    return "```yaml\ndemir-kit-evidence\n" + text.rstrip() + "\n```"


def check_issue(
    number: int,
    checkpoint: str | None = None,
    root: Path = ROOT,
    assume_labels: set[str] | None = None,
    drop_labels: set[str] | None = None,
    evidence_file: Path | None = None,
) -> None:
    ecosystem = load_yaml(root / "ecosystem.yaml") or {}
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        error("issue: ecosystem.yaml tracker.repo yok")
        return
    issue_raw = run(["gh", "api", f"repos/{repo}/issues/{number}"])
    if not issue_raw:
        error(f"issue #{number}: gh api ile okunamadı")
        return
    payload = json.loads(issue_raw)
    comments = fetch_comments(repo, number)
    labels = [item.get("name") for item in payload.get("labels", [])]
    actual_labels = set(labels)
    label_set = set(labels)
    if drop_labels:
        label_set -= set(drop_labels)
    if assume_labels:
        label_set |= set(assume_labels)
    labels = sorted(label_set)
    for left, right in (
        ("leaf-done", "executing"),
        ("leaf-done", "blocked"),
        ("epic-done", "epic-reconcile"),
    ):
        if left in label_set and right in label_set:
            error(f"issue #{number}: çelişen etiketler — {left} + {right}")
    bodies = [item.get("body", "") for item in comments]
    body = payload.get("body", "")
    evidence_text = normalize_evidence_text(
        evidence_file.read_text(encoding="utf-8") if evidence_file else None
    )
    for message in doctor_approval.check_issue_extras(number, body, comments, root, evidence_text):
        error(message)
    if re.search(r"```yaml\s+demir-kit\s*\n", body):
        check_issue_body(
            body,
            labels,
            bodies,
            checkpoint,
            root=root,
            repo=repo,
            title=payload.get("title", ""),
            evidence_text=evidence_text,
        )
    elif "agent-approved" in labels or "leaf-done" in labels:
        error(f"issue #{number}: leaf seal (`demir-kit` bloğu) yok")

    child_labels = seal_lint.child_labels_for(
        repo, body, lambda url: run(["gh", "api", url])
    )
    for message in seal_lint.validate_epic_record(body, labels, child_labels):
        error(f"issue #{number}: {message}")
    epic_block = re.search(r"```yaml\s+demir-kit-epic\s*\n(.*?)```", body, re.S)
    if epic_block:
        schema = load_json(DELIVERY / "schemas" / "epic.schema.json")
        try:
            record = yaml.safe_load(epic_block.group(1)) or {}
        except yaml.YAMLError as exc:
            error(f"issue #{number}: epic YAML geçersiz — {exc}")
            record = None
        if schema and isinstance(record, dict):
            for message in validate_schema(record, schema, "epic"):
                error(message)

    timeout_blocks = re.findall(
        r"```yaml\s+demir-kit-accept\s*\n(.*?)```",
        "\n".join([payload.get("body", "")] + bodies),
        re.S,
    )
    for raw in timeout_blocks:
        try:
            record = yaml.safe_load(raw) or {}
        except yaml.YAMLError:
            continue
        if isinstance(record, dict) and record.get("via") == "timeout":
            if not str(record.get("note") or "").strip():
                error(f"issue #{number}: via timeout onayı notesuz")

    closure_blocks = re.findall(
        r"```yaml\s+demir-kit-closure\s*\n(.*?)```",
        "\n".join([payload.get("body", "")] + bodies),
        re.S,
    )
    if "epic-done" in labels and not closure_blocks:
        error(f"issue #{number}: epic-done ama closure bloğu yok")
    if closure_blocks:
        schema = load_json(DELIVERY / "schemas" / "closure.schema.json")
        try:
            record = yaml.safe_load(closure_blocks[-1]) or {}
        except yaml.YAMLError as exc:
            error(f"issue #{number}: closure YAML geçersiz — {exc}")
            record = None
        if not isinstance(record, dict):
            error(f"issue #{number}: closure blok mapping değil")
        else:
            if schema:
                for message in validate_schema(record, schema, "closure"):
                    error(message)
            if "epic-done" in labels and record.get("status") != "pass":
                error(
                    f"issue #{number}: epic-done ama closure status 'pass' değil"
                )
            if "epic-done" in labels and record.get("ready_for_human_qa") is not True:
                error(
                    f"issue #{number}: epic-done ama closure ready_for_human_qa true değil"
                )

    if "epic-done" in actual_labels:
        epic_record = None
        if epic_block:
            try:
                epic_record = yaml.safe_load(epic_block.group(1)) or {}
            except yaml.YAMLError:
                epic_record = None
        children = [
            int(item)
            for item in (epic_record or {}).get("children") or []
            if isinstance(item, int)
        ]
        closure_value = None
        if closure_blocks:
            try:
                closure_value = yaml.safe_load(closure_blocks[-1]) or {}
            except yaml.YAMLError:
                closure_value = None
        metrics = (
            closure_value.get("metrics")
            if isinstance(closure_value, dict)
            else {}
        )
        leaf_count = (metrics or {}).get("leaf_count")
        if children and leaf_count != len(children):
            error(
                f"issue #{number}: closure metrics.leaf_count child sayısıyla "
                f"eşleşmiyor ({leaf_count} != {len(children)})"
            )
        for child in children:
            child_labels = fetch_issue_labels(repo, child)
            if not child_labels & {"leaf-done", "deferred"}:
                error(f"issue #{number}: child #{child} leaf-done/deferred değil")
        acceptance = approvals_lib.human_acceptance(comments, number)
        if not acceptance:
            error(
                f"issue #{number}: epic-done için insan authored "
                "demir-kit-accept comment'i gerekli"
            )

def check_installed_skills(root: Path = ROOT) -> None:
    """`install.sh` kopyaları kaynaktan geride kalırsa uyar."""
    check("installed skills")
    installed = root / ".agents" / "skills"
    source = root / "skills"
    if not installed.is_dir() or not source.is_dir():
        return
    stale: list[str] = []
    for entry in sorted(installed.iterdir()):
        src = source / entry.name / "SKILL.md"
        copy = entry / "SKILL.md"
        if src.is_file() and copy.is_file() and src.read_bytes() != copy.read_bytes():
            stale.append(entry.name)
    if stale:
        warn(
            "kurulu skill kopyası kaynaktan farklı: "
            f"{', '.join(stale)} — './install.sh' ile tazele"
        )


def check_worktree_management(root: Path = ROOT) -> None:
    """Linked worktree Orca'da kayıtlı olmalı; ham `git worktree add` yakalanır."""
    check("worktree")
    if os.environ.get("CI"):
        return
    git_dir = _git_output(root, "rev-parse", "--git-dir")
    common = _git_output(root, "rev-parse", "--git-common-dir")
    if not git_dir or not common:
        return

    def resolve(value: str) -> Path:
        path = Path(value)
        return path.resolve() if path.is_absolute() else (root / path).resolve()

    if resolve(git_dir) == resolve(common):
        return  # ana checkout; worktree kuralı burada uygulanmaz
    if not epic_worktree.orca_available(root):
        return  # Orca yok: kayıtlı degrade mod
    worktree = epic_worktree.current_worktree(root) or {}
    recorded = str((worktree.get("git") or {}).get("path") or "")
    # Orca dışarıdan bulduğu worktree'yi listeler ama createdAt yazmaz; Orca'nın
    # açtığı checkout'ta bu alan vardır.
    managed = bool(worktree.get("createdAt"))
    if not recorded or Path(recorded).resolve() != root.resolve() or not managed:
        error(
            "worktree: bu checkout Orca dışında açılmış — kaynak değişikliği "
            "için 'orca worktree create' kullan, ham 'git worktree add' açma"
        )


def _git_output(path: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def kit_pin_status(root: Path, kit_path: Path) -> tuple[str, str]:
    """Pin durumu: ok / unmerged / unverifiable / absent.

    VERSION eşitliği tek başına yetmez: merge edilmemiş bir branch commit'i de
    aynı sürüm dizesini taşır. Pin, `origin/main`in atası olmalı.
    """
    if not (kit_path / ".git").exists():
        return "absent", ""
    sha = None
    try:
        rel = kit_path.relative_to(root).as_posix()
    except ValueError:
        rel = kit_path.name
    tree = _git_output(root, "ls-tree", "HEAD", "--", rel)
    if tree:
        parts = tree.split()
        if len(parts) >= 3 and parts[0] == "160000":
            sha = parts[2]
    if not sha:
        sha = _git_output(kit_path, "rev-parse", "HEAD")
    if not sha:
        return "unverifiable", "git HEAD okunamadı"
    ref = None
    for candidate in ("origin/main", "main"):
        if _git_output(kit_path, "rev-parse", "--verify", "--quiet", candidate):
            ref = candidate
            break
    if not ref:
        return "unverifiable", "origin/main ref yok"
    try:
        result = subprocess.run(
            ["git", "-C", str(kit_path), "merge-base", "--is-ancestor", sha, ref],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unverifiable", "merge-base çalıştırılamadı"
    if result.returncode == 0:
        return "ok", sha
    if result.returncode == 1:
        return "unmerged", sha
    return "unverifiable", f"{sha[:7]} kit klonunda yok"


def check_product(root: Path) -> None:
    check("product")
    config = load_yaml(root / "kit.config.yaml")
    if not isinstance(config, dict):
        error(f"{root}/kit.config.yaml: eksik veya geçersiz")
        config = {}
    kit = config.get("kit") or {}
    if str(kit.get("protocol")) != "2":
        error("kit.config.yaml: kit.protocol '2' değil")
    kit_root = kit.get("root") or "demir-kit"
    if not (root / kit_root / "delivery" / "scripts" / "doctor.py").is_file():
        error(f"vendored kit bulunamadı: {kit_root}/delivery")
    kit_version_path = root / kit_root / "VERSION"
    configured_version = str(kit.get("version") or "")
    if kit_version_path.is_file():
        actual = kit_version_path.read_text(encoding="utf-8").strip()
        if configured_version and configured_version != actual:
            warn(
                f"kit sürüm drifti: kit.config '{configured_version}' ≠ "
                f"{kit_root}/VERSION '{actual}' — güncelleme: "
                "submodule → 'git submodule update --remote demir-kit'; "
                "vendor → 'vendor_sync.sh --target <proje> --apply'"
            )
    pin_state, pin_detail = kit_pin_status(root, root / kit_root)
    if pin_state == "unmerged":
        error(
            f"kit pin yayınlanmış değil: {kit_root} {pin_detail[:7]} "
            "origin/main'in atası değil — merge edilmemiş commit'e bağlanmak "
            "yerine yayınlanmış kit sürümüne dön"
        )
    elif pin_state == "unverifiable":
        warn(
            f"kit pin doğrulanamadı ({pin_detail}) — "
            f"'git -C {kit_root} fetch origin main' sonrası tekrar çalıştır"
        )

    factory = config.get("factory") or {}
    app_paths = factory.get("app_paths") or ["src", "app", "lib"]
    if not isinstance(app_paths, list) or not app_paths:
        error("kit.config.yaml: factory.app_paths liste değil")
        app_paths = []
    for path in app_paths:
        if not (root / path).exists():
            warn(f"app path yok: {path}")

    risk_path = root / ".kit" / "risk.yaml"
    if risk_path.is_file():
        data = load_yaml(risk_path)
        if not isinstance(data, dict):
            error(f"{risk_path}: kök mapping değil")
        else:
            escalate = data.get("auto_escalate") or {}
            if not isinstance(escalate, dict):
                error(f"{risk_path}: auto_escalate mapping değil")
            else:
                for level in ("high", "critical"):
                    values = escalate.get(level) or []
                    if not isinstance(values, list) or any(
                        not isinstance(item, str) for item in values
                    ):
                        error(f"{risk_path}: auto_escalate.{level} string listesi değil")

    priorities = ((config.get("product") or {}).get("priorities")) or {}
    if priorities:
        design = priorities.get("design_system")
        if design and not (root / str(design)).exists():
            error(f"kit.config.yaml: product.priorities.design_system yok — {design}")
        architecture = priorities.get("architecture") or []
        if not isinstance(architecture, list):
            error("kit.config.yaml: product.priorities.architecture liste değil")
        else:
            for item in architecture:
                if not (root / str(item)).exists():
                    error(f"kit.config.yaml: product.priorities.architecture yok — {item}")

    eco = load_yaml(root / "ecosystem.yaml")
    if not isinstance(eco, dict):
        error("ecosystem.yaml: eksik veya geçersiz")
        eco = {}
    products = eco.get("products") or {}
    if not products:
        error("ecosystem.yaml: products boş")
    for pname, product in products.items():
        for sname, spec in (product.get("surfaces") or {}).items():
            spec = spec or {}
            surface_path = spec.get("path")
            if not surface_path:
                error(f"ecosystem.{pname}.{sname}: path yok")
                continue
            if not (root / surface_path).exists():
                error(f"ecosystem.{pname}.{sname}: path yok — {surface_path}")
            gate = (spec.get("gates") or {}).get("behavior")
            surface_gate_messages(str(pname), str(sname), spec, error, warn)
            if not gate:
                continue
            try:
                first = shlex.split(gate)[0]
            except ValueError:
                first = ""
            if first.startswith(("./", "scripts/")) and not (root / first).is_file():
                error(f"ecosystem.{pname}.{sname}: gate script yok — {first}")

    node_stacks = {
        "node",
        "javascript",
        "typescript",
        "next",
        "react",
        "vue",
        "svelte",
        "sveltekit",
        "vite",
        "astro",
        "web",
        "deno",
        "bun",
    }
    node_surface = False
    for product in products.values():
        for spec in (product.get("surfaces") or {}).values():
            stacks = (spec or {}).get("stacks") or []
            if isinstance(stacks, str):
                stacks = [stacks]
            if any(str(stack).lower() in node_stacks for stack in stacks):
                node_surface = True
    package = root / "package.json"
    if not package.is_file():
        if node_surface:
            warn("package.json yok")
    else:
        data = load_json(package)
        if isinstance(data, dict):
            scripts = data.get("scripts") or {}
            for name in ("typecheck", "lint"):
                if name not in scripts:
                    warn(f"package.json: '{name}' script yok")
    if not (root / "AGENTS.md").is_file():
        warn("AGENTS.md yok")
    else:
        prefix = "" if str(kit_root) in {".", ""} else str(kit_root)
        for message in delivery_block.check(root, prefix):
            warn(f"delivery block: {message}")
        if (config.get("orca") or {}).get("epic_worktree"):
            ignore = root / ".gitignore"
            text = ignore.read_text(encoding="utf-8") if ignore.is_file() else ""
            if ".orchestration/" not in text.splitlines():
                warn(".gitignore: .orchestration/ yok")

    profile_capability_config = load_yaml(DELIVERY / "capabilities" / "registry.yaml") or {}
    profile_capabilities = set((profile_capability_config.get("capabilities") or {}).keys())
    profile_packs = {
        path.name for path in (DELIVERY / "packs").iterdir() if path.is_dir()
    }
    for message in profiles_lib.validate_project(root, profile_capabilities, profile_packs):
        error(f"profiles: {message}")

    declared_path = root / ".kit" / "capabilities.yaml"
    if declared_path.is_file():
        declared = resolver_lib.load_declared(root)
        if declared.get("version") != 1:
            error(".kit/capabilities.yaml: version 1 olmalı")
        available = set(
            (load_yaml(DELIVERY / "capabilities" / "registry.yaml") or {})
            .get("capabilities", {})
            .keys()
        )
        for cap_id in declared.get("include", []) + declared.get("exclude", []):
            if cap_id not in available:
                error(f".kit/capabilities.yaml: bilinmeyen capability — {cap_id}")


def check_local_overrides(root: Path = ROOT, policy_path: Path | None = None) -> None:
    doctor_local.check_local_overrides(
        root, policy_path, error, check, load_yaml, rel
    )


EXPLAIN_CHECKS = doctor_explain.checks(globals())


def main() -> int:
    parser = argparse.ArgumentParser(description="demir-kit delivery doctor")
    parser.add_argument("--strict", action="store_true", help="uyarıları da hata say")
    parser.add_argument("--issue", type=int, help="seal + evidence doğrula")
    parser.add_argument(
        "--evidence", type=Path, help="tek evidence dosyasını issue seal'ine göre doğrula"
    )
    parser.add_argument("--body", type=Path, help="seal YAML içeren dosya")
    parser.add_argument("--checkpoint", help="behavior gate uyumu için (statik)")
    parser.add_argument(
        "--assume-label",
        action="append",
        default=[],
        help="geçiş öncesi hedef etiketi varsay",
    )
    parser.add_argument(
        "--drop-label",
        action="append",
        default=[],
        help="geçiş öncesi kaldırılacak etiketi yok say",
    )
    parser.add_argument("--verbose", action="store_true", help="tüm uyarıları göster")
    parser.add_argument("--explain", metavar="NAME", help="tek kontrolü ve kaynağını açıkla")
    parser.add_argument("--product", action="store_true", help="ürün reposu kontrolleri")
    parser.add_argument("--root", type=Path, help="ürün kökü (--product)")
    args = parser.parse_args()
    if args.explain is not None:
        if args.issue or args.body or args.checkpoint:
            parser.error("--explain --issue/--body/--checkpoint ile kullanılamaz")
        root = (args.root or Path.cwd()).resolve() if args.product else ROOT
        return doctor_explain.explain(args.explain, EXPLAIN_CHECKS, root, args.product)

    product_root = (args.root or Path.cwd()).resolve()
    check_worktree_management(product_root if args.product else ROOT)
    check_installed_skills(product_root if args.product else ROOT)
    check_model_policy(product_root if args.product else ROOT)
    check_unsealed_work(product_root if args.product else ROOT)
    if args.product:
        check_product(product_root)
    else:
        check_files()
        check_schemas()
        check_registry()
        check_rigor()
        check_capabilities()
        check_profiles()
        check_agent_variants()
        check_labels()
        check_links()
        check_legacy(args.verbose)
        check_version()
        check_ecosystem()
        check_fleet()
        check_skills()
        check_role_contracts()
        check_mcp()
        check_compat()
        check_local_overrides(ROOT)

    if args.checkpoint and args.checkpoint != "CP-HEALTH" and not re.match(
        r"^CP-[0-9]+$", args.checkpoint
    ):
        error(f"checkpoint '{args.checkpoint}' geçersiz (CP-n bekleniyor)")

    if args.issue:
        check_issue(
            args.issue,
            args.checkpoint,
            product_root if args.product else ROOT,
            assume_labels=set(args.assume_label),
            drop_labels=set(args.drop_label),
            evidence_file=args.evidence,
        )
    if args.body:
        check_issue_body(args.body.read_text(encoding="utf-8"), [], None, checkpoint=args.checkpoint)

    for item in ERRORS:
        print(f"[fail] {item}")
    for item in WARNS:
        print(f"[warn] {item}")

    failed = bool(ERRORS) or (args.strict and bool(WARNS))
    print(
        f"\n{CHECKS} kontrol · {len(ERRORS)} hata · {len(WARNS)} uyarı"
        + (" · STRICT" if args.strict else "")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
