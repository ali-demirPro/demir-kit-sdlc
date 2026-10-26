---
name: kit-build
description: >-
  Product owner command — seal ONE leaf GitHub issue (work-package). Requires scope-confirmed.
  Enables app implementation only for that issue after agent-approved and health-check.
---

# kit-build

**Canonical skill:** `${kit.root}/skills/work-package/SKILL.md`  
**Hard gates:** `${kit.root}/references/agent-phase-gates.md`

Apply `human-communication.md`.

## STOP — read first

| Required before seal | Block |
|------------------------|--------|
| Owner names issue **#N** (leaf, not scope-only parent) | Sealing parent epic with CPs while children are `intake` |
| Epic/parent has **`scope-confirmed`** or issue has `scope_triage.confirmed` | kit-feature scope skipped |
| Full YAML + **`agent-approved`** on **#N** only | `agent-approved` on parent without leaf work |
| **health-check** `ready: true` before Orca | Orca before seal |
| App `src/` changes only for **#N** after seal | Batch P0 across #3–#8 in one session |

Run `scripts/kit-agent-guard.sh --issue N` before committing app changes.

## When the owner says "kit-build" or "kit-build #N"

1. If **#N** omitted → ask which **leaf** issue (not parent scope epic).
2. If parent has full checkpoints but children are `intake` → **move seal to child #N**; strip parent to `scope_triage` only (offer amend).
3. Follow **work-package** phases B0–B6 in canonical skill.
4. **Autonomous kit-init** if approved brief and no `ecosystem.yaml` (see work-package §−1).
5. Brownfield feature: `entry.kind: **feature**` default — not `greenfield_product` unless new repo bootstrap.
6. On seal: `agent-approved` on **#N** only → **health-check** → Orca / worktree for **#N**.

## Implementation (B7)

- Allowed **only after** step 6 on **#N**.
- Gates (behavior, ui, adversarial, …) run in **Orca** per checkpoint — not skipped because “P0 is urgent”.
- Do not implement sibling issues in same pass unless owner explicitly waives in `decisions` (document in issue).

## Do not

- Run kit-build during **kit-feature** session without owner switching command.
- Create `docs/work-packages/` or `WP-*.md`.

## Complete

Issue **#N** has `agent-approved`, health-check passed, Orca objective `demir-kit #N` (or owner defers Orca with documented reason).
