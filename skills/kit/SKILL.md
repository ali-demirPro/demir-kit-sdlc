---
name: kit
description: >-
  demir-kit entry — lifecycle and owner commands. Read agent-phase-gates.md before
  any owner skill. kit-feature never implements; kit-build seals one leaf issue.
---

# Kit (demir-kit)

Protokol: **`references/product-lifecycle.md`**, **hard gates: `references/agent-phase-gates.md`**.

## Owner commands (product repo)

| Command | Ends with | Never |
|---------|-----------|--------|
| **kit-feature** | `scope-confirmed`, children `intake` | `src/`, `agent-approved`, checkpoints on parent |
| **kit-build #N** | `agent-approved` on leaf **#N**, health-check | Seal parent epic; skip Orca gates |
| **kit-build-change** | amended YAML on sealed **#N** | First seal |
| **kit-upgrade** | vendor VERSION sync | `src/`, product brief |

Internal (coordinator reads `${kit.root}/skills/`): gates, test-plan, architect, …

## Lifecycle (brownfield)

1. **kit-setup** (+ envision) → `discovery-approved`
2. **kit-feature** → epic + children (F0–F4)
3. **kit-build #3** … per leaf → Orca CPs + gates
4. **kit-init** may run inside **kit-build** if `ecosystem.yaml` missing

## Kit kökü

`kit.config.yaml` → `kit.root`. Guard: `scripts/kit-agent-guard.sh`.

## Skill grupları

| Grup | Skill’ler |
|------|-----------|
| **Owner** | `kit-feature`, `kit-build`, `kit-build-change`, `kit-upgrade` |
| **Kit** | `kit-setup`, `kit-envision`, `kit-init` |
| **Triage** | `scope-triage` (= kit-feature canonical) |
| **Seal** | `work-package`, `work-package-amend`, `test-plan`, `health-check` |
| **Gate** | `behavior-gate`, `ui-gate`, `adversarial-review`, `platform-gate` |

Anti-pattern: `examples/anti-patterns/kit-feature-premature-seal.md`
