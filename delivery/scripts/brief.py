#!/usr/bin/env python3
"""Show how a leaf maps to delivery agents.

Usage:
  python3 delivery/scripts/brief.py 13
  python3 delivery/scripts/brief.py 13 --json
  python3 delivery/scripts/brief.py 13 --post
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import resolver  # noqa: E402
import routing  # noqa: E402
import profiles  # noqa: E402


def gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"brief: gh failed — {result.stderr.strip()}")
    return result.stdout


def repo_name() -> str:
    project = routing.project_root(ROOT)
    try:
        ecosystem = yaml.safe_load(
            (project / "ecosystem.yaml").read_text(encoding="utf-8")
        ) or {}
    except (OSError, yaml.YAMLError):
        ecosystem = {}
    repo = (ecosystem.get("tracker") or {}).get("repo") if isinstance(ecosystem, dict) else None
    # gh api expands these placeholders from the current repository; a missing
    # ecosystem must not stop the brief before its banner is printed.
    return str(repo) if repo else "{owner}/{repo}"


def project_ecosystem() -> dict:
    project = routing.project_root(ROOT)
    try:
        data = yaml.safe_load((project / "ecosystem.yaml").read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def project_priorities() -> dict:
    """kit.config.yaml product.priorities — agent'lara her brief'te görünür."""
    project = routing.project_root(ROOT)
    try:
        data = yaml.safe_load((project / "kit.config.yaml").read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    priorities = ((data.get("product") or {}).get("priorities")) or {}
    return priorities if isinstance(priorities, dict) else {}


def _unique(items) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


READ_CLASSES = ("sink", "window", "retrieved")
READ_TAGS = {
    "sink": "[sink]",
    "window": "[window]",
    "retrieved": "[retrieved]",
}
READ_UNKNOWN = "[unknown]"
SINK_LIMIT = 4
WINDOW_LIMIT = 3
RETRIEVED_LIMIT = 5
WINDOW_DOC_ORDER = ("ROLE.md", "how.md", "SKILL.md", "communicates.md", "dependencies.md")


def read_tag(value) -> str:
    """Tag for one reading class; an unrecognised class is ``[unknown]``."""
    text = str(value or "").strip()
    return READ_TAGS.get(text, READ_UNKNOWN)


def reading_items(
    sink: list[str] | None = None,
    window: list[str] | None = None,
    route: list[dict] | None = None,
) -> list[dict]:
    """Classify paths for a CP brief: sink > window > retrieved > unknown.

    Every path keeps one class. Route candidates are already explained by
    ``--route`` and are not re-listed; a route item without a known reading
    class stays visible as ``unknown`` instead of joining ``retrieved``.
    """
    items: list[dict] = []
    seen: set[str] = set()

    def add(kind: str, path) -> None:
        text = str(path or "")
        if not text or text in seen:
            return
        seen.add(text)
        items.append({"class": kind, "path": text})

    for path in sink or []:
        add("sink", path)
    for path in window or []:
        add("window", path)
    for item in route or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("class") or "").strip()
        if kind == "candidate":
            continue
        add(kind if kind in READ_CLASSES else "unknown", item.get("path"))
    return items


def window_docs(docs: list[str] | None, role: str) -> list[str]:
    """Active CP role documents, at most ``WINDOW_LIMIT``, core files first."""
    selected = [
        str(doc)
        for doc in docs or []
        if f"/agents/{role}/" in f"/{doc}"
    ]
    selected.sort(
        key=lambda doc: (
            WINDOW_DOC_ORDER.index(Path(doc).name)
            if Path(doc).name in WINDOW_DOC_ORDER
            else len(WINDOW_DOC_ORDER),
            doc,
        )
    )
    return selected[:WINDOW_LIMIT]


def cp_route_items(route: list[dict] | None) -> list[dict]:
    """Route items the CP brief lists: sink/retrieved/unknown, capped budget.

    Window paths come from :func:`window_docs`; candidates stay in ``--route``
    output so the CP brief does not re-list them as reading material.
    """
    items: list[dict] = []
    retrieved = 0
    for item in route or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("class") or "").strip()
        if kind in ("window", "candidate"):
            continue
        if kind == "retrieved":
            retrieved += 1
            if retrieved > RETRIEVED_LIMIT:
                continue
        items.append(item)
    return items


def render_reading_items(items: list[dict]) -> list[str]:
    return [f"- {read_tag(item['class'])} {item['path']}" for item in items]


def control_fields(
    path_id: str,
    path_source: str,
    fallbacks: list[str] | None = None,
    route_requested: bool = False,
    route_count: int = 0,
    index_version: str = "yok",
    cp_id: str | None = None,
    cp_applied: bool = False,
) -> dict:
    """armed/indexing/unarmed banner fields for one brief invocation.

    ``armed`` only claims a selection that actually happened (signal/keyword
    path, checkpoint lookup, route consumption); ``indexing`` is written only
    when ``--route`` really consumed the index. Every missing piece becomes an
    ``unarmed`` reason instead of a silent absence.
    """
    armed: list[str] = []
    reasons: list[str] = []
    if path_source in ("signal", "keyword", "entry"):
        armed.append(f"path {path_id}")
    else:
        reasons.append("path default")
    if cp_applied and cp_id:
        armed.append(f"cp {cp_id}")
    indexing = None
    if route_requested:
        if not index_version or index_version == "yok":
            reasons.append("index yok")
        else:
            indexing = f"v{index_version}"
            armed.append(f"route {route_count}")
    else:
        reasons.append("route tuketilmedi")
    return {
        "armed": armed,
        "indexing": indexing,
        "unarmed": reasons,
        "fallbacks": _unique(fallbacks or []),
    }


def header_lines(data: dict) -> list[str]:
    """config/armed/indexing/unarmed/fallback lines prepended to every output."""
    lines = routing.render_config(data.get("config"))
    armed = data.get("armed") or []
    if armed:
        lines.append("armed: " + ", ".join(armed))
    if data.get("indexing"):
        lines.append(f"indexing: {data['indexing']}")
    reasons = data.get("unarmed") or []
    if reasons:
        lines.append("unarmed: " + "; ".join(reasons))
    for reason in data.get("fallbacks") or []:
        lines.append(f"fallback: {reason}")
    return lines


def build_brief(
    registry: dict,
    number: int,
    title: str,
    body: str,
    labels: set[str],
    prefix: str = "",
    ecosystem: dict | None = None,
    priorities: dict | None = None,
    fallbacks: list[str] | None = None,
) -> dict:
    resolver.reset_fallbacks()
    seal = routing.seal_body(body)
    epic = routing.is_epic(body) or ("scope-confirmed" in labels and not seal)
    path_id, signal, path_source = routing.detect_path_detail(
        registry, title, body, seal
    )
    agents = routing.resolve_agents(registry, path_id, signal)
    risk = (seal.get("risk") or {}).get("level", "n/a")
    signals = (
        resolver.scoped_signals(ecosystem, seal)
        if seal
        else resolver.project_signals(ecosystem or {})
    )
    text = f"{title}\n{seal.get('intent', '')}\n{routing.strip_seal(body)}"
    resolution = resolver.resolve(
        resolver.load_capabilities(),
        resolver.load_matrix(),
        resolver.load_agent_variants(),
        path_id,
        signals,
        text,
        declared=resolver.load_declared(routing.project_root(ROOT)),
    )
    docs = [f"{prefix}{doc}" for doc in resolution["docs"]]
    config = routing.config_snapshot(
        ROOT, registry, path_id, path_source, index_file()
    )
    reasons = list(fallbacks or [])
    if path_source == "default":
        reasons.append("path default")
    version_fallback = routing.route_index_version_fallback(index_file())
    if version_fallback:
        reasons.append(version_fallback)
    reasons += resolver.fallbacks()
    reasons = _unique(reasons)

    data = {
        "issue": number,
        "title": title,
        "state": "epic" if epic else "leaf",
        "path_id": path_id,
        "path_source": path_source,
        "signal": signal.get("id") if signal else None,
        "agents": agents,
        "active_roles": resolution["active_roles"],
        "on_demand_roles": resolution["on_demand_roles"],
        "inactive": [
            {
                "id": role,
                "reason": routing.INACTIVE_REASONS.get(
                    role, "bu path'te aktif değil"
                ),
            }
            for role in resolution["inactive_roles"]
        ],
        "capabilities": resolution["capabilities"],
        "active_variants": resolution["active_variants"],
        "inactive_variants": resolution["inactive_variants"],
        "variant_gaps": resolution["variant_gaps"],
        "risk": risk,
        "risk_floor": resolution["risk_floor"],
        "priorities": priorities or {},
        "next_action": routing.next_action(labels, epic),
        "human_gates": routing.human_gates(risk, epic),
        "docs": docs,
        "config": config,
    }
    data.update(
        control_fields(path_id, path_source, fallbacks=reasons)
    )
    return data


def index_file() -> Path:
    """Route index shipped with the kit; patched in tests."""
    return routing.route_index_path(ROOT)


def cp_role(gates: dict) -> str:
    return "designer" if gates.get("ui") else "developer"


def cp_selection(seal: dict, cp_id: str) -> tuple[dict, list[dict]]:
    checkpoints = seal.get("checkpoints") or []
    cp = next(
        (item for item in checkpoints if str(item.get("id")) == cp_id),
        None,
    )
    if not isinstance(cp, dict):
        raise ValueError(f"{cp_id}: seal'de checkpoint yok")
    cases: list[dict] = []
    for plan in seal.get("tests_plan") or []:
        if not isinstance(plan, dict) or str(plan.get("checkpoint_id")) != cp_id:
            continue
        for case in plan.get("cases") or []:
            if isinstance(case, dict):
                cases.append(case)
    return cp, cases


def evidence_skeleton(reviewers: list[str], risk: str) -> list[str]:
    """Evidence lines derived from the same reviewer set doctor enforces."""
    if "adversarial-b" in reviewers:
        lines = ["  adversarial: {reviewer_a: approved, reviewer_b: approved}"]
    else:
        lines = ["  adversarial: {reviewer_a: approved}"]
    for role in ("architect", "commercial", "human", "human_second"):
        if role in reviewers:
            lines.append(f"  {role}: approved")
    if "platform" in reviewers:
        lines.append("  platform: pass")
    if "ui" in reviewers:
        lines.append("  ui: pass")
    if "ui_visual" in reviewers:
        lines += [
            "  ui_visual: pass",
            "  ui_interaction: pass",
            "  comparison_valid: true",
        ]
    lines.append(f"  risk: {risk}")
    return lines


def render_cp_brief(
    data: dict,
    seal: dict,
    cp_id: str,
    prefix: str = "",
    gates: dict | None = None,
    risk: str | None = None,
    profile_gates: dict | None = None,
    include_evidence: bool = True,
    control: dict | None = None,
    docs: list[str] | None = None,
    route: list[dict] | None = None,
) -> str:
    """Compact per-checkpoint brief: scope, AC, tests, evidence skeleton."""
    cp, cases = cp_selection(seal, cp_id)
    effective_gates = gates if gates is not None else (cp.get("gates") or {})
    effective_risk = str(
        risk
        or (seal.get("risk") or {}).get("level")
        or data.get("risk")
        or "n/a"
    )
    role = cp_role(cp.get("gates") or {})
    reviewers = routing.evidence_reviewers(
        effective_gates, effective_risk, profile_gates
    )
    ac_ids = {str(case.get("ac")) for case in cases if case.get("ac")}
    criteria = seal.get("acceptance_criteria") or []
    selected = [
        item for item in criteria if str(item.get("id")) in ac_ids
    ]
    reference = (seal.get("reference") or {}).get("paths") or []
    surfaces = ", ".join(str(item) for item in seal.get("surfaces") or []) or "n/a"
    gate_command = (
        f"./{prefix}delivery/scripts/gate.sh --issue {data['issue']}"
        + f" --checkpoint {cp_id}"
    )
    gate_source = {**effective_gates, **(profile_gates or {})}
    active = [
        item
        for item in ("ui", "architect", "commercial", "platform", "human")
        if gate_source.get(item)
    ]
    gate_text = "behavior" + (", " + ", ".join(active) if active else "")

    lines = header_lines(control or {})
    lines += [
        f"## CP brief — {cp_id} · {cp.get('title', '')}",
        f"Epic: {seal.get('epic')} · Risk: {effective_risk} · Rol: {role}",
        f"Yüzey: {surfaces} · Gate: {gate_text}",
        f"Kapsam: {seal.get('intent', '')}",
    ]
    if selected:
        lines.append("AC (bu CP):")
        for item in selected:
            lines.append(f"- {item.get('id')}: {item.get('text', '')}")
    else:
        lines.append("AC (bu CP): seal'de bu CP'ye bağlı case yok — seal'i düzelt.")
    if cases:
        lines.append("Testler:")
        for case in cases:
            lines.append(
                f"- {case.get('id')} ({case.get('ac')}, {case.get('check', 'gate')}): "
                f"{case.get('text', '')}"
            )
    else:
        lines.append("Testler: seal'de bu CP için case yok — seal'i düzelt.")
    sink_paths = [f"{prefix}{path}" for path in reference[:SINK_LIMIT]]
    overflow = [f"{prefix}{path}" for path in reference[SINK_LIMIT:]]
    reading = reading_items(
        sink=sink_paths,
        window=window_docs(docs, role),
        route=cp_route_items(route),
    )
    if sink_paths:
        lines.append("Yollar:")
        lines += [
            f"- {READ_TAGS['sink']} {path}" for path in sink_paths
        ]
    if overflow:
        lines.append("Sink limiti aşan referanslar:")
        lines += [
            f"- {READ_UNKNOWN} (sink limiti) {path}" for path in overflow
        ]
    overflow_set = set(overflow)
    extra = [
        item
        for item in reading
        if item["class"] != "sink" and item["path"] not in overflow_set
    ]
    if extra:
        lines.append("Okuma sınıfları:")
        lines += render_reading_items(extra)

    if include_evidence and cases:
        lines += [
            f"Kanıt (agent: {role}, reviewer: {', '.join(reviewers)}):",
            "```yaml",
            "demir-kit-evidence",
            'demir_kit_version: "2"',
            f"cp_id: {cp_id}",
            f"issue: {data['issue']}",
            f"agent: {role}",
            "commit: <sha>",
            f'behavior: {{command: "{gate_command}", exit_code: 0, checkpoint: {cp_id}}}',
            "reviews:",
        ]
        lines += evidence_skeleton(reviewers, effective_risk)
        lines.append("tests:")
        for case in cases:
            lines.append(f"  - {{case: {case.get('id')}, result: pass}}")
        lines += [
            "findings: []",
            "status: pass",
            "```",
        ]
    elif include_evidence:
        lines.append(
            "Kanıt: case olmadığı için evidence iskeleti üretilmedi; "
            "önce seal'i düzelt."
        )
    lines += [
        "Makine: `resources.py --report` yalnız bilgi içindir; hiçbir komutu durdurmaz.",
        f"Komut: `{gate_command}`",
        "Okuma: bu brief yeterli; ek dosyayı yalnız ilgili satır için aç "
        "(`rg -n`), CONTRACT.md ve quality-gates.md tamamını okuma.",
        "Kurallar: yalnız bu CP; başka CP/contract/CI dosyasına dokunma; tam dosya "
        "dökme; bağlam 120k'da uyar, 200k'da dur ve kısa özet yaz.",
    ]
    return "\n".join(lines) + "\n"


def render(data: dict) -> str:
    lines = header_lines(data)
    lines += [
        f"#{data['issue']} {data['title']}",
        f"state: {data['state']}",
        f"path: {data['path_id']}"
        + (f" (signal: {data['signal']})" if data["signal"] else ""),
        "capabilities: " + (", ".join(data["capabilities"]) or "-"),
        "active: " + ", ".join(data["active_roles"]),
        "on_demand: " + (", ".join(data["on_demand_roles"]) or "-"),
        "optional: " + (", ".join(data["agents"]["optional"]) or "-"),
        "active variants:",
    ]
    for item in data["active_variants"]:
        lines.append(
            f"  - {item['role']} / {item['capability']} -> {item['doc']} "
            f"({item['min_level']})"
        )
    lines.append("inactive:")
    for item in data["inactive"]:
        lines.append(f"  - {item['id']}: {item['reason']}")
    lines.append("inactive variants:")
    for item in data["inactive_variants"]:
        lines.append(f"  - {item['role']} / {item['capability']}: {item['reason']}")
    lines.append("variant gaps:")
    for item in data["variant_gaps"]:
        lines.append(f"  - {item['role']} / {item['capability']}: {item['reason']}")
    lines += [
        f"risk floor: {data['risk_floor']}",
        f"next: {data['next_action']}",
        "human gates:",
    ]
    lines += [f"  - {gate}" for gate in data["human_gates"]]
    lines.append("docs:")
    lines += [f"  - {doc}" for doc in data["docs"]]
    priorities = data.get("priorities") or {}
    if priorities:
        lines.append("project priorities (binding):")
        if priorities.get("design_system"):
            lines.append(f"  - design system: {priorities['design_system']}")
        for item in priorities.get("architecture") or []:
            lines.append(f"  - architecture: {item}")
        if priorities.get("quality_floor"):
            lines.append(f"  - quality floor: {priorities['quality_floor']}")
        lines.append("  - rules: delivery/policies/project-priorities.md")
    return "\n".join(lines)


def comment_body(data: dict) -> str:
    payload = {
        "delivery_path": {
            "path_id": data["path_id"],
            "signal": data["signal"],
            "capabilities": data["capabilities"],
            "active_agents": data["active_roles"],
            "optional_agents": data["agents"]["optional"],
            "on_demand": data["on_demand_roles"],
            "inactive": data["inactive"],
            "active_variants": data["active_variants"],
            "inactive_variants": data["inactive_variants"],
            "variant_gaps": data["variant_gaps"],
            "risk_floor": data["risk_floor"],
            "next_action": data["next_action"],
            "human_gates": data["human_gates"],
            "priorities": data.get("priorities") or {},
        }
    }
    return (
        "## delivery_path\n\n"
        f"```yaml\n{yaml.safe_dump(payload, sort_keys=False)}```\n"
    )


def has_delivery_path(comments: list[dict]) -> bool:
    return any("## delivery_path" in (item.get("body") or "") for item in comments)


def existing_delivery_path(repo: str, issue: int, fetch=None) -> bool:
    fetch = fetch or gh
    page = 1
    while True:
        data = json.loads(
            fetch(
                [
                    "api",
                    f"repos/{repo}/issues/{issue}/comments?per_page=100&page={page}",
                ]
            )
        )
        if has_delivery_path(data):
            return True
        if len(data) < 100:
            return False
        page += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="delivery agent brief")
    parser.add_argument("issue", type=int)
    parser.add_argument("--cp", help="compact brief for one checkpoint (CP-1)")
    parser.add_argument(
        "--route",
        action="store_true",
        help="sink/window/retrieved doküman seçimini kaynak ve gerekçeyle yaz",
    )
    parser.add_argument("--write", type=Path, help="write the CP brief to this directory")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--post", action="store_true")
    args = parser.parse_args()

    repo = repo_name()
    issue = json.loads(gh(["api", f"repos/{repo}/issues/{args.issue}"]))
    labels = {item.get("name") for item in issue.get("labels", [])}
    body = issue.get("body", "") or ""
    ecosystem = project_ecosystem()
    priorities = project_priorities()
    initial_fallbacks: list[str] = []
    if not ecosystem:
        initial_fallbacks.append("ecosystem yok")
    if not priorities:
        initial_fallbacks.append("priorities yok")
    data = build_brief(
        routing.load_registry(ROOT),
        args.issue,
        issue.get("title", ""),
        body,
        labels,
        routing.kit_prefix(ROOT),
        ecosystem,
        priorities,
        fallbacks=initial_fallbacks,
    )

    if args.route:
        seal = routing.seal_body(body)
        if args.cp:
            try:
                cp_selection(seal, args.cp)
            except ValueError as exc:
                sys.exit(f"brief: {exc}")
        try:
            index = routing.load_route_index(index_file(), ROOT)
        except routing.RouteIndexError as exc:
            print(f"brief: {exc}", file=sys.stderr)
            return 2
        route, fallback = routing.build_route(
            seal, data["docs"], index, routing.kit_prefix(ROOT)
        )
        version = str(index["version"]) if index else "yok"
        fallbacks = list(data["fallbacks"])
        if fallback:
            fallbacks.append(fallback)
        route_data = {
            **data,
            **control_fields(
                data["path_id"],
                data["path_source"],
                fallbacks=fallbacks,
                route_requested=True,
                route_count=len(route),
                index_version=version,
                cp_id=args.cp,
                cp_applied=bool(args.cp),
            ),
        }
        if args.json:
            print(
                json.dumps(
                    {
                        "issue": data["issue"],
                        "route": route,
                        "fallback": fallback,
                        "config": route_data["config"],
                        "armed": route_data["armed"],
                        "indexing": route_data["indexing"],
                        "unarmed": route_data["unarmed"],
                        "fallbacks": route_data["fallbacks"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            lines = header_lines(route_data)
            output = (
                "\n".join(lines) + ("\n" if lines else "")
                + routing.render_route(route, None)
            )
            if args.cp:
                cp, _ = cp_selection(seal, args.cp)
                role = cp_role(cp.get("gates") or {})
                reading = reading_items(
                    sink=[
                        str(item["path"])
                        for item in route
                        if item.get("class") == "sink"
                    ],
                    window=window_docs(
                        [
                            str(item["path"])
                            for item in route
                            if item.get("class") == "window"
                        ],
                        role,
                    ),
                    route=cp_route_items(
                        [
                            item
                            for item in route
                            if item.get("class") not in ("sink", "window", "candidate")
                        ]
                    ),
                )
                if reading:
                    output += "Okuma sınıfları:\n"
                    output += "\n".join(render_reading_items(reading)) + "\n"
            sys.stdout.write(output)
        return 0

    if args.cp:
        seal = routing.seal_body(body)
        if not seal:
            sys.exit("brief: issue seal (`demir-kit` bloğu) yok")
        try:
            cp, _ = cp_selection(seal, args.cp)
            project = routing.project_root(ROOT)
            seal_profile = str((seal.get("factory") or {}).get("profile") or "")
            profile_gates = profiles.gates_for(project, seal_profile)
            effective = routing.effective_risk(
                str((seal.get("risk") or {}).get("level") or "low"),
                str(data.get("risk_floor") or "low"),
            )
            cp_control = {
                **data,
                **control_fields(
                    data["path_id"],
                    data["path_source"],
                    fallbacks=list(data["fallbacks"]),
                    cp_id=args.cp,
                    cp_applied=True,
                ),
            }
            cp_route: list[dict] = []
            try:
                index = routing.load_route_index(index_file(), ROOT)
            except routing.RouteIndexError:
                index = None
            if index is not None:
                cp_route, _ = routing.build_route(
                    seal, data["docs"], index, routing.kit_prefix(ROOT)
                )
            text = render_cp_brief(
                {"issue": data["issue"], "risk": effective},
                seal,
                args.cp,
                routing.kit_prefix(ROOT),
                gates=cp.get("gates") or {},
                risk=effective,
                profile_gates=profile_gates,
                control=cp_control,
                docs=data["docs"],
                route=cp_route,
            )
        except ValueError as exc:
            sys.exit(f"brief: {exc}")
        if args.write:
            args.write.mkdir(parents=True, exist_ok=True)
            path = args.write / f"{args.cp}.md"
            path.write_text(text, encoding="utf-8")
            print(path)
        elif args.json:
            print(
                json.dumps(
                    {
                        "issue": data["issue"],
                        "cp_id": args.cp,
                        "role": cp_role(cp.get("gates") or {}),
                        "chars": len(text),
                        "brief": text,
                        "config": cp_control["config"],
                        "armed": cp_control["armed"],
                        "indexing": cp_control["indexing"],
                        "unarmed": cp_control["unarmed"],
                        "fallbacks": cp_control["fallbacks"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(text)
        return 0

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render(data))

    if args.post:
        if existing_delivery_path(repo, args.issue):
            print("brief: delivery_path comment already exists", file=sys.stderr)
        else:
            body = comment_body(data)
            subprocess.run(
                [
                    "gh",
                    "api",
                    "-X",
                    "POST",
                    f"repos/{repo}/issues/{args.issue}/comments",
                    "--input",
                    "-",
                ],
                input=json.dumps({"body": body}),
                text=True,
                check=True,
                capture_output=True,
            )
            print("brief: delivery_path comment posted", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
