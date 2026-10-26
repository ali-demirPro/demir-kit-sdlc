---
name: behavior-gate
description: >-
  Red-green TDD for one Orca task checkpoint. Run ecosystem gate command via
  orca terminal create/wait; exit 0 required before worker_done.
---

# behavior-gate

See `gate-contract.md`. Coordinator dispatches this skill in a **supervised** worker (`worker-start`).

## Steps

1. Read CP acceptance criteria from issue YAML.
2. Write tests; run gate command from `ecosystem.yaml` (`{checkpoint}` substituted) — expect fail.
3. Implement minimal scope.
4. Re-run gate — exit 0.
5. `orca orchestration send --type worker_done --outcome succeeded` (IDs from dispatch preamble).

## Orca

Prefer `orca terminal create --command "<gate>"` + `terminal wait` over ad-hoc local shell outside worktree.

## Communication

Blockers → `orchestration ask` coordinator with **human-language** question (`human-communication.md`).
