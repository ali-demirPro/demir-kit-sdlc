---
name: checkpoint-planner
description: >-
  Refine GitHub issue checkpoints for Orca task-create specs. Output task list or
  ephemeral .orchestration/ artifact — never commit WP to repo.
---

# checkpoint-planner

## Input

- `gh issue view` body → `demir-kit` YAML (`reference`, `tests_plan`, `checkpoints`)
- `ecosystem.yaml`

Validate every behavior CP has `tests_plan` entry; every UI CP has `ui_scope`.

## Output

- Orca: one `task-create` per CP with spec from `orchestration/task-spec-template.md`
- Optional: `.orchestration/checkpoints.json` (gitignored) for coordinator script

## Refine-only (default)

`checkpoints_preapproved: true` → verify order, gates, surface commands; **no** extra human plan stop.

## Generate mode

Missing checkpoints → derive from acceptance_criteria; coordinator **`ask`** user in plain language (`human-communication.md`).
