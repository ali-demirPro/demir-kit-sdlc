---
name: checkpoint-planner
description: >-
  Validate sealed checkpoints for execution: order, gates, surfaces and test
  coverage. Emit task specs, never a committed work-package file.
---

# checkpoint-planner

Full protocol: `delivery/protocol/execution.md`.

## Input

- Issue body `demir-kit` YAML (`reference`, `tests_plan`, `checkpoints`, `risk`)
- `ecosystem.yaml`

Check every behavior CP has a `tests_plan` entry; every UI CP has `ui_scope`;
`depends_on` is acyclic.

## Output

- One Orca `task-create` per CP, spec from `delivery/protocol/execution.md`.
- Optional ephemeral `.orchestration/checkpoints.json` (gitignored).

## Refine-only (default)

If the seal is valid, verify order, gates and surface commands; do not add a human
plan stop.

## Generate mode

Missing checkpoints → derive from `acceptance_criteria` **before** seal, then ask
one human-language question (`delivery/policies/human-communication.md`). After
seal, adding CPs requires an amend.
