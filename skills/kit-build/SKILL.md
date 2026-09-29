---
name: kit-build
description: >-
  Product owner command — seal executable work on a GitHub issue (alias for
  work-package). Runs kit-init automatically when ecosystem.yaml is missing.
---

# kit-build

**Canonical skill:** `${kit.root}/skills/work-package/SKILL.md` (read and follow that file).

Apply `human-communication.md` for all user-facing text.

## When the owner says "kit-build"

1. Follow **work-package** phases in the canonical skill.
2. **Autonomous kit-init (no separate owner command):** If `discovery-approved` / approved brief exists and repo root has no `ecosystem.yaml` (or it is stale vs brief § Proposed ecosystem), run **`kit-init`** before seal:
   - `"$KIT_ROOT/tools/kit-init.sh" --repo <tracker.repo>`
   - Agent materialize step per `envision-handoff.md`
   - Do not ask the owner to type "kit-init" unless init fails or brief is not approved.
3. If scope not confirmed for greenfield/epic: run **kit-feature** (scope-triage) first or confirm CUT items in `out_of_scope`.
4. On seal: issue body with `demir-kit` YAML, label **`agent-approved`**, then **`health-check`** before Orca.

Internal skills (read from `${kit.root}/skills/`, do not register in Orca UI): `factory-routing`, `test-plan`, `checkpoint-planner`, gates, baselines.

## Do not

- Create `docs/work-packages/` or `WP-*.md` in repo.
