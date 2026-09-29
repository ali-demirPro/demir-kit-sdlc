---
name: ecosystem-bootstrap
description: >-
  Add or update ecosystem.yaml for multi-surface repos. Work tracking stays on
  GitHub via work-package — not in this skill.
---

# ecosystem-bootstrap

Prefer **`kit-init`** after **`discovery-approved`**. Use this skill for **`ecosystem_amend`** (new surface/path). Material yaml changes on brownfield: lite **`kit-envision`** + `discovery-approved` recommended (`envision-stewardship.md`).

- Output: `ecosystem.yaml` PR + optional `docs/agent/workflow.md` from templates.
- Set `tracker.provider: github` and `tracker.repo: owner/name`.
- Validate against `references/ecosystem.schema.yaml`.
- Gate commands must work with `orca terminal create` in Orca worktrees.
