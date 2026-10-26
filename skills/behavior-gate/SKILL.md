---
name: behavior-gate
description: >-
  Red-green TDD for one checkpoint. Run the ecosystem gate command via Orca,
  exit 0 required before worker_done.
---

# behavior-gate

Contract: `delivery/policies/quality-gates.md` (behavior).
Communication: `delivery/policies/human-communication.md`.

## Steps

1. Read the CP acceptance criteria and `tests_plan` cases from the issue seal.
2. Write tests (or doc checks); run the `ecosystem.yaml` gate command with
   `{checkpoint}` replaced — expect fail first.
3. Implement the minimal scope.
4. Re-run the gate — exit `0`.
5. Post evidence (`delivery/protocol/evidence.md`), then `worker_done`.

## Gate command

```bash
./delivery/scripts/doctor.sh --issue <N> --checkpoint CP-1
```

Without `--issue` the command only validates the checkpoint id format (doc-only
leaves); runtime CP membership needs the issue.

## Orca

Prefer `orca terminal create --command "<gate>"` + `terminal wait` over ad-hoc
shell outside the worktree.

## Blockers

Gate limit (3 rounds) or environment failure → `blocked` + one human-language
question. Do not silently pass a failing gate.
