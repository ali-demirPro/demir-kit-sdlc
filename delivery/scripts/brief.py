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


def gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"brief: gh failed — {result.stderr.strip()}")
    return result.stdout


def repo_name() -> str:
    project = routing.project_root(ROOT)
    ecosystem = yaml.safe_load((project / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        sys.exit("brief: ecosystem.yaml tracker.repo yok")
    return repo


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


def build_brief(
    registry: dict,
    number: int,
    title: str,
    body: str,
    labels: set[str],
    prefix: str = "",
    ecosystem: dict | None = None,
    priorities: dict | None = None,
) -> dict:
    seal = routing.seal_body(body)
    epic = routing.is_epic(body) or ("scope-confirmed" in labels and not seal)
    path_id, signal = routing.detect_path(registry, title, body, seal)
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

    return {
        "issue": number,
        "title": title,
        "state": "epic" if epic else "leaf",
        "path_id": path_id,
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
    }


def cp_role(gates: dict) -> str:
    return "designer" if gates.get("ui") else "developer"


def cp_evidence_reviewers(gates: dict, risk: str) -> list[str]:
    roles = ["adversarial-a"]
    if risk in {"high", "critical"} or gates.get("architect"):
        roles.append("architect")
    if risk == "critical" or gates.get("commercial"):
        roles.append("commercial")
    if gates.get("ui"):
        roles += ["ui_visual", "ui_interaction"]
    if risk in {"high", "critical"}:
        roles.append("human")
    if risk == "critical":
        roles.append("human_second")
    return roles


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


def render_cp_brief(
    data: dict,
    seal: dict,
    cp_id: str,
    prefix: str = "",
    reviewers: list[str] | None = None,
) -> str:
    """Compact per-checkpoint brief: scope, AC, tests, evidence skeleton."""
    cp, cases = cp_selection(seal, cp_id)
    gates = cp.get("gates") or {}
    risk = str((seal.get("risk") or {}).get("level") or data.get("risk") or "n/a")
    role = cp_role(gates)
    reviewers = reviewers or cp_evidence_reviewers(gates, risk)
    ac_ids = {str(case.get("ac")) for case in cases if case.get("ac")}
    criteria = seal.get("acceptance_criteria") or []
    selected = [
        item
        for item in criteria
        if not ac_ids or str(item.get("id")) in ac_ids
    ]
    reference = (seal.get("reference") or {}).get("paths") or []
    surfaces = ", ".join(str(item) for item in seal.get("surfaces") or []) or "n/a"
    gate_command = (
        f"./{prefix}delivery/scripts/doctor.sh --issue {data['issue']}"
        + (" --product --root ." if prefix else "")
        + f" --checkpoint {cp_id}"
    )
    active = [item for item in ("ui", "architect", "commercial", "human") if gates.get(item)]
    gate_text = "behavior" + (", " + ", ".join(active) if active else "")

    lines = [
        f"## CP brief — {cp_id} · {cp.get('title', '')}",
        f"Epic: {seal.get('epic')} · Risk: {risk} · Rol: {role}",
        f"Yüzey: {surfaces} · Gate: {gate_text}",
        f"Kapsam: {seal.get('intent', '')}",
    ]
    if selected:
        lines.append("AC (bu CP):")
        for item in selected:
            lines.append(f"- {item.get('id')}: {item.get('text', '')}")
    if cases:
        lines.append("Testler:")
        for case in cases:
            lines.append(
                f"- {case.get('id')} ({case.get('ac')}, {case.get('check', 'gate')}): "
                f"{case.get('text', '')}"
            )
    if reference:
        lines.append("Yollar:")
        lines += [f"- {prefix}{path}" if prefix else f"- {path}" for path in reference]

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
        "  adversarial: {reviewer_a: approved}",
        f"  risk: {risk}",
        "tests:",
    ]
    for case in cases or [{"id": "T-1"}]:
        lines.append(f"  - {{case: {case.get('id')}, result: pass}}")
    lines += [
        "findings: []",
        "status: pass",
        "```",
        f"Komut: `{gate_command}`",
        "Okuma: bu brief yeterli; ek dosyayı yalnız ilgili satır için aç "
        "(`rg -n`), CONTRACT.md ve quality-gates.md tamamını okuma.",
        "Kurallar: yalnız bu CP; başka CP/contract/CI dosyasına dokunma; tam dosya "
        "dökme; bağlam 120k'da dur ve kısa özet yaz.",
    ]
    return "\n".join(lines) + "\n"


def render(data: dict) -> str:
    lines = [
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
    parser.add_argument("--write", type=Path, help="write the CP brief to this directory")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--post", action="store_true")
    args = parser.parse_args()

    repo = repo_name()
    issue = json.loads(gh(["api", f"repos/{repo}/issues/{args.issue}"]))
    labels = {item.get("name") for item in issue.get("labels", [])}
    body = issue.get("body", "") or ""
    data = build_brief(
        routing.load_registry(ROOT),
        args.issue,
        issue.get("title", ""),
        body,
        labels,
        routing.kit_prefix(ROOT),
        project_ecosystem(),
        project_priorities(),
    )

    if args.cp:
        seal = routing.seal_body(body)
        if not seal:
            sys.exit("brief: issue seal (`demir-kit` bloğu) yok")
        try:
            text = render_cp_brief(
                data, seal, args.cp, routing.kit_prefix(ROOT)
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
                        "role": cp_role(
                            (cp_selection(seal, args.cp)[0].get("gates") or {})
                        ),
                        "chars": len(text),
                        "brief": text,
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
