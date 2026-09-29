---
name: scope-triage
description: >-
  Feature triage KEEP/DEFER/CUT. Ends at scope-confirmed — never seals checkpoints or
  writes app code. See agent-phase-gates.md.
---

# scope-triage

Apply `human-communication.md`. **Hard gates:** `${kit.root}/references/agent-phase-gates.md`.

Owner alias: **kit-feature** — same phases F0–F4.

## When

- After envision / brief approved (brownfield: may run before `ecosystem.yaml` exists — **do not** block triage on kit-init)
- Before **kit-build** on greenfield bootstrap **or** before opening epic children
- Re-run after `work-package-amend` scope change

## When NOT (use other skills)

| Situation | Skill |
|-----------|--------|
| Seal checkpoints, `agent-approved` | **kit-build** / work-package |
| Change vendored kit | **kit-upgrade** |
| Implement `src/` | **kit-build** + Orca only |

## Process

0. Import `docs/product/discovery-brief.md` § Development bets if present; confirm overrides only.
1. List candidates; score technical / value / `effort_hours`.
2. Decision: **keep** | **defer** | **cut** per item.
3. **F1:** Human-language table; owner confirm.
4. **F2:** Issue plan in chat; wait for “issue aç”.
5. **F3:** Create issues per `agent-phase-gates.md` (parent minimal YAML; children markdown + `intake`).
6. **F4:** `scope-confirmed`; roadmap deferrals; run **kit-agent-guard** (no app diff).

## Issue block `scope_triage`

(Same YAML structure as before — on **parent/epic only**.)

## Parent YAML — allowed vs forbidden

**Allowed:** `demir_kit_version`, `scope_triage`, `feasibility`, `envision` (pointer), `decisions`  
**Forbidden:** `checkpoints`, `tests_plan`, `checkpoints_preapproved`, full `factory`, `mode: bootstrap`, `greenfield_product` for brownfield UI epics

## Repo sync

- **defer** → `docs/architecture/evolution-roadmap.md`
- **cut** → `out_of_scope` when issue is later sealed on a **child** via kit-build

## Minimum output

MVO: triage table + roadmap — **not** full PRD or work-package (`minimum-viable-output.md`).

## Labels

`scope-confirmed` when `scope_triage.confirmed: true` on epic/parent — **not** `agent-approved`.

## Next (not in this skill)

`kit-build` on **each leaf** → `factory-routing` → mühür → health-check → Orca.
