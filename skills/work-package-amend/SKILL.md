---
name: work-package-amend
description: >-
  Update a sealed GitHub issue work package (package_version++, audit comment).
  Use for post-seal scope changes or human QA feedback. No repo WP files.
---

# work-package-amend

**Hard gates:** `${kit.root}/references/agent-phase-gates.md` — issue must already be **`agent-approved`**. Owner entry: **kit-build-change**.

- **`human-communication.md`** for user-facing text.
- `gh issue view <N> --json body` → parse `demir-kit` YAML.
- Increment `package_version`; audit comment in plain language.
- Update body via `gh issue edit`.
- Reset labels: `agent-approved` when ready for Orca re-run.
- ADR reminder if `adr_required` decisions added → dispatch **`solution-architect`** mode `decision` or `refactor-proposal` before re-seal when scope crosses boundaries or tiers.
- Material feature add/remove → re-run **`scope-triage`**; bump `scope_triage.confirmed_at`; sync `evolution-roadmap.md`.
