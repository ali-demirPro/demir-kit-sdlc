#!/usr/bin/env python3
"""demir-kit doctor — delivery contract enforcement.

Checks:
  1. required files and schemas
  2. registry <-> agent directories <-> path policy
  3. canonical labels
  4. broken markdown links / backticked paths
  5. legacy archive references (warn by default, fail with --strict)
  6. VERSION / CHANGELOG / README consistency
  7. ecosystem.yaml and kit.config.yaml (self-host wiring)
  8. SKILL.md name uniqueness
  9. seed issue validation (--issue N or --body FILE)
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import approvals as approvals_lib  # noqa: E402
import capabilities as capabilities_lib  # noqa: E402
import delivery_block  # noqa: E402
import epic_worktree  # noqa: E402
import evidence as evidence_lib  # noqa: E402
import profiles as profiles_lib  # noqa: E402
import resolver as resolver_lib  # noqa: E402
import variants as variants_lib  # noqa: E402
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
    "delivery/scripts/evidence.py",
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
    config_path = root / "kit.config.yaml"
    if config_path.is_file():
        config = load_yaml(config_path)
        config = config if isinstance(config, dict) else {}
        configured = str(((config.get("kit") or {}).get("version")) or "")
        if not configured:
            warn("kit.config.yaml: kit.version yok")
        elif configured != version:
            error(f"kit.config.yaml: kit.version '{configured}' ≠ VERSION ({version})")
    agents = root / "AGENTS.md"
    short = ".".join(version.split(".")[:2])
    if agents.is_file() and f"demir-kit {short}" not in agents.read_text(
        encoding="utf-8"
    ):
        warn(f"AGENTS.md sürüm başlığı 'demir-kit {short}' değil")
    changelog = root / "CHANGELOG.md"
    if changelog.is_file():
        first = re.search(
            r"^## .*?(\d+\.\d+\.\d+)\b", changelog.read_text(encoding="utf-8"), re.M
        )
        if not first:
            warn("CHANGELOG.md: sürüm başlığı bulunamadı")
        elif first.group(1) != version:
            error(
                f"CHANGELOG.md: ilk sürüm başlığı {first.group(1)}"
                f" ≠ VERSION ({version})"
            )


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
            if not (spec.get("gates") or {}).get("behavior"):
                error(f"ecosystem.{name}.{surface}: gates.behavior yok")
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


def run(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def frontmatter_name(text: str) -> str | None:
    block = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not block:
        return None
    match = re.search(r"^name:\s*(.+)$", block.group(1), re.M)
    return match.group(1).strip().strip("\"'") if match else None


def _json_type(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def validate_schema(instance, schema, path: str = "$") -> list[str]:
    """Minimal JSON Schema subset used by the v2 leaf schema."""
    if not isinstance(schema, dict):
        return []
    errors: list[str] = []

    if "type" in schema and not _json_type(instance, schema["type"]):
        return [f"{path}: '{schema['type']}' bekleniyor"]

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: {schema['const']!r} bekleniyor")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} enum dışında")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: en az {schema['minLength']} karakter")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: '{schema['pattern']}' desenine uymuyor")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: en az {schema['minimum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: en az {schema['minItems']} öğe")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: en fazla {schema['maxItems']} öğe")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors += validate_schema(item, schema["items"], f"{path}[{index}]")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}.{key}: eksik")
        properties = schema.get("properties") or {}
        for key, value in instance.items():
            if key in properties:
                errors += validate_schema(value, properties[key], f"{path}.{key}")
                continue
            additional = schema.get("additionalProperties", True)
            if additional is False:
                errors.append(f"{path}.{key}: izin verilmeyen alan")
            elif isinstance(additional, dict):
                errors += validate_schema(value, additional, f"{path}.{key}")

    if "allOf" in schema:
        for sub in schema["allOf"]:
            errors += validate_schema(instance, sub, path)

    if isinstance(schema.get("if"), dict):
        if not validate_schema(instance, schema["if"], path):
            then = schema.get("then")
            if isinstance(then, dict):
                errors += validate_schema(instance, then, path)

    return errors


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

    package_version = data.get("package_version", 1)
    if not isinstance(package_version, int):
        package_version = 1
    acs = data.get("acceptance_criteria") or []
    ac_ids = [item.get("id") for item in acs if isinstance(item, dict)]
    if len(ac_ids) != len(set(ac_ids)):
        error("issue seal: AC id tekrarlı")

    cps = data.get("checkpoints") or []
    cp_ids = [item.get("id") for item in cps if isinstance(item, dict)]
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

    for cp in cps:
        if not isinstance(cp, dict):
            continue
        gates = cp.get("gates") or {}
        if gates.get("behavior") is not True:
            error(f"{cp.get('id')}: gates.behavior true olmalı")
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
    ecosystem = load_yaml(root / "ecosystem.yaml") or {}
    signals = resolver_lib.scoped_signals(ecosystem, data)
    declared = resolver_lib.load_declared(root)
    # Historical evidence must stay valid after a project-level exclude; the
    # seal's own surfaces decide which roles could have produced it.
    declared_for_issue = {
        "version": 1,
        "include": declared.get("include") or [],
        "exclude": [],
    }
    resolution = resolver_lib.resolve(
        capability_registry,
        resolver_lib.load_matrix(),
        resolver_lib.load_agent_variants(),
        path_id,
        signals,
        f"{title}\n{data.get('intent', '')}\n{routing.strip_seal(body)}",
        declared=declared_for_issue,
    )
    for capability in resolution["capabilities"]:
        allowed_agents.update(
            ((capability_registry.get("capabilities") or {}).get(capability) or {})
            .get("roles", {})
            .keys()
        )
    risk_floor = resolution.get("risk_floor", "low")
    if resolver_lib.RISK_ORDER.get(risk_floor, 0) > resolver_lib.RISK_ORDER.get(
        risk or "low", 0
    ):
        error(
            f"issue seal: capability risk_floor '{risk_floor}' seal risk "
            f"'{risk}' üstünde; seal riskini yükselt"
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

    if "leaf-done" in labels and comments is not None:
        evidence_schema = load_json(DELIVERY / "schemas" / "evidence.schema.json")
        evidence: dict[str, dict] = {}
        for comment in comments:
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
            evidence[record["cp_id"]] = record

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
        for cp_id in cp_ids:
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


def check_issue(
    number: int,
    checkpoint: str | None = None,
    root: Path = ROOT,
    assume_labels: set[str] | None = None,
    drop_labels: set[str] | None = None,
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
    if re.search(r"```yaml\s+demir-kit\s*\n", body):
        check_issue_body(
            body,
            labels,
            bodies,
            checkpoint,
            root=root,
            repo=repo,
            title=payload.get("title", ""),
        )
    elif "agent-approved" in labels or "leaf-done" in labels:
        error(f"issue #{number}: leaf seal (`demir-kit` bloğu) yok")

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
            if not gate:
                error(f"ecosystem.{pname}.{sname}: gates.behavior yok")
                continue
            try:
                first = shlex.split(gate)[0]
            except ValueError:
                first = ""
            if first.startswith(("./", "scripts/")) and not (root / first).is_file():
                error(f"ecosystem.{pname}.{sname}: gate script yok — {first}")

    package = root / "package.json"
    if not package.is_file():
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


def main() -> int:
    parser = argparse.ArgumentParser(description="demir-kit delivery doctor")
    parser.add_argument("--strict", action="store_true", help="uyarıları da hata say")
    parser.add_argument("--issue", type=int, help="seal + evidence doğrula")
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
    parser.add_argument("--product", action="store_true", help="ürün reposu kontrolleri")
    parser.add_argument("--root", type=Path, help="ürün kökü (--product)")
    args = parser.parse_args()

    product_root = (args.root or Path.cwd()).resolve()
    if args.product:
        check_product(product_root)
    else:
        check_files()
        check_schemas()
        check_registry()
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
        )
    if args.body:
        check_issue_body(
            args.body.read_text(encoding="utf-8"), [], None, checkpoint=args.checkpoint
        )

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
