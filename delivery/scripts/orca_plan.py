#!/usr/bin/env python3
"""Turn a sealed demir-kit leaf into Orca task specs.

Usage:
  python3 delivery/scripts/orca_plan.py 17
  python3 delivery/scripts/orca_plan.py 17 --json
  python3 delivery/scripts/orca_plan.py 17 --write /tmp/orca-plan
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
import profiles as profiles_mod  # noqa: E402
import routing  # noqa: E402


def gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"orca_plan: gh failed — {result.stderr.strip()}")
    return result.stdout


def repo_name() -> str:
    project = routing.project_root(ROOT)
    ecosystem = yaml.safe_load((project / "ecosystem.yaml").read_text(encoding="utf-8")) or {}
    repo = (ecosystem.get("tracker") or {}).get("repo")
    if not repo:
        sys.exit("orca_plan: ecosystem.yaml tracker.repo yok")
    return repo


def project_ecosystem() -> dict:
    project = routing.project_root(ROOT)
    try:
        data = yaml.safe_load((project / "ecosystem.yaml").read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def required_reviewers(gates: dict, risk: str, resolution: dict) -> list[str]:
    caps = set(resolution.get("capabilities") or [])
    reviewers = {"tester"}
    if gates.get("ui"):
        reviewers.add("designer")
    if gates.get("architect") or risk in {"high", "critical"}:
        reviewers.add("architect")
    if risk in {"high", "critical"} or caps & {
        "domain.auth",
        "domain.payments",
        "quality.security",
        "quality.privacy",
    }:
        reviewers.add("security")
    if gates.get("commercial") or risk == "critical":
        reviewers.update({"marketing/stores", "release"})
    if caps & {"distribution.app_store", "distribution.play"}:
        reviewers.update({"marketing/stores", "release"})
    if "distribution.web" in caps:
        reviewers.update({"marketing/landing", "release"})
    if "quality.a11y" in caps:
        reviewers.add("designer")
    return sorted(reviewers)


def build_plan(
    registry: dict,
    issue: int,
    title: str,
    body: str,
    labels: set[str],
    prefix: str = "",
    ecosystem: dict | None = None,
) -> dict:
    seal = routing.seal_body(body)
    if not seal:
        raise ValueError("issue seal (`demir-kit` bloğu) yok")
    if "agent-approved" not in labels:
        raise ValueError("leaf agent-approved değil")
    path_id, signal = routing.detect_path(registry, title, body, seal)
    agents = routing.resolve_agents(registry, path_id, signal)
    surfaces = ", ".join(seal.get("surfaces") or []) or "n/a"
    epic = seal.get("epic")
    risk = (seal.get("risk") or {}).get("level", "n/a")
    project = routing.project_root(ROOT)
    seal_profile = str((seal.get("factory") or {}).get("profile") or "")
    if seal_profile:
        profile_data = profiles_mod.load_profile(seal_profile)
    else:
        try:
            profile_data = profiles_mod.compose(project)
        except ValueError:
            profile_data = {}
    profile_gates = {
        str(gate): True for gate in profile_data.get("extra_gates") or []
    }
    profile_docs = [
        f"{prefix}skills/{skill}/SKILL.md"
        for skill in profile_data.get("required_skills") or []
    ]
    profile_docs += [
        f"{prefix}delivery/packs/{pack}/checklist.md"
        for pack in profile_data.get("platform_packs") or []
    ]
    ecosystem = ecosystem if ecosystem is not None else project_ecosystem()
    signals = resolver.scoped_signals(ecosystem, seal)
    resolution = resolver.resolve(
        resolver.load_capabilities(),
        resolver.load_matrix(),
        resolver.load_agent_variants(),
        path_id,
        signals,
        f"{title}\n{seal.get('intent', '')}\n{routing.strip_seal(body)}",
        declared=resolver.load_declared(project),
    )
    capabilities = resolution["capabilities"]
    active_variants = resolution["active_variants"]
    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    effective_risk = max(
        (risk if risk in risk_order else "low"),
        resolution["risk_floor"],
        key=lambda value: risk_order.get(value, 0),
    )
    reviewers = required_reviewers(
        {"ui": False, "architect": False, "commercial": False, **profile_gates},
        effective_risk,
        resolution,
    )

    tasks = []
    for cp in seal.get("checkpoints") or []:
        if not isinstance(cp, dict):
            continue
        cp_id = cp.get("id")
        gates = cp.get("gates") or {}
        role = "designer" if gates.get("ui") else "developer"
        docs_list = routing.role_docs(role, prefix)
        for doc in profile_docs:
            if doc not in docs_list:
                docs_list.append(doc)
        for item in active_variants:
            if item["role"] == role:
                doc = f"{prefix}delivery/agents/{role}/{item['doc']}"
                if doc not in docs_list:
                    docs_list.append(doc)
        docs = "\n".join(f"- {item}" for item in docs_list)
        effective_gates = {**gates, **profile_gates}
        cp_reviewers = required_reviewers(effective_gates, effective_risk, resolution)
        reviewers = sorted(set(reviewers) | set(cp_reviewers))
        deps = [f"task:{item}" for item in cp.get("depends_on") or []]
        spec = (
            f"demir-kit #{issue} {cp_id}: {cp.get('title', '')}\n"
            f"Target: issue #{issue}, epic #{epic}, surfaces: {surfaces}\n"
            f"Role: {role}\n"
            f"Capabilities: {', '.join(capabilities) or '-'}\n"
            f"Required reviewers: {', '.join(cp_reviewers)}\n"
            f"Read:\n{docs}\n"
            f"- {prefix}delivery/CONTRACT.md\n"
            f"- {prefix}delivery/policies/quality-gates.md\n"
            f"Change: implement only {cp_id} for this sealed leaf.\n"
            f"Ownership: edit only files required by {cp_id}; never touch other CPs, "
            f"the contract, CI or another agent's files. Surfaces: {surfaces}.\n"
            f"Constraints: no work outside issue #{issue}; do not self-approve; "
            f"do not touch other CPs; risk is {effective_risk} (seal {risk}).\n"
            f"Acceptance: `./{prefix}delivery/scripts/doctor.sh"
            + (" --product --root ." if prefix else "")
            + f" --issue {issue} --checkpoint {cp_id}` exit 0, then post evidence with agent: {role}.\n"
        )
        tasks.append(
            {
                "id": cp_id,
                "role": role,
                "deps": deps,
                "reviewers": cp_reviewers,
                "capabilities": capabilities,
                "spec": spec,
            }
        )

    return {
        "issue": issue,
        "title": title,
        "epic": epic,
        "path_id": path_id,
        "signal": signal.get("id") if signal else None,
        "risk": risk,
        "effective_risk": effective_risk,
        "active_agents": agents["active"],
        "capability_agents": resolution["active_roles"],
        "capabilities": capabilities,
        "active_variants": active_variants,
        "variant_gaps": resolution["variant_gaps"],
        "risk_floor": resolution["risk_floor"],
        "reviewers": reviewers,
        "tasks": tasks,
    }


def write_plan(plan: dict, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = [directory / "plan.json"]
    written[0].write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    for task in plan["tasks"]:
        path = directory / f"{task['id']}.md"
        path.write_text(task["spec"], encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="sealed leaf -> Orca task specs")
    parser.add_argument("issue", type=int)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()

    repo = repo_name()
    payload = json.loads(gh(["api", f"repos/{repo}/issues/{args.issue}"]))
    labels = {item.get("name") for item in payload.get("labels", [])}
    try:
        plan = build_plan(
            routing.load_registry(ROOT),
            args.issue,
            payload.get("title", ""),
            payload.get("body", "") or "",
            labels,
            routing.kit_prefix(ROOT),
        )
    except ValueError as exc:
        sys.exit(f"orca_plan: {exc}")

    if args.write:
        for path in write_plan(plan, args.write):
            print(path)
    elif args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(f"#{plan['issue']} {plan['title']}")
        print(f"path: {plan['path_id']} · risk: {plan['risk']} · tasks: {len(plan['tasks'])}")
        for task in plan["tasks"]:
            print(f"  - {task['id']} → {task['role']} (deps: {', '.join(task['deps']) or '-'})")
            for line in task["spec"].splitlines():
                print(f"      {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
