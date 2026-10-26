---
name: test-plan
description: >-
  Required before seal: fill tests_plan per checkpoint and map every AC to at
  least one case. Enforced by doctor.
---

# test-plan

## When

During seal (mandatory), before `agent-approved`. A later amend may add cases but
must not delete coverage without a decision record.

## Input

- `reference` block (paths, running app, prototype)
- `acceptance_criteria` (`AC-n`) and `checkpoints` (`CP-n`)

## Output

Issue YAML `tests_plan[]` in the v2 shape:

```yaml
tests_plan:
  - checkpoint_id: CP-1
    cases:
      - { id: T-1, ac: AC-1, text: "second claim same day rejected" }
      - { id: T-2, ac: AC-2, text: "happy path returns 200" }
```

- Every `AC-n` is covered by at least one case.
- Every CP with `gates.behavior: true` has at least one case.
- Validate with `./delivery/scripts/doctor.sh --body FILE`.

## Style

- User-perspective integration checks where possible.
- Edge cases beyond the happy path.
- Doc-only leaves may use a deterministic check (e.g. `doctor.sh`).

## Storage

Only the GitHub issue body/comment. Never commit a test-plan file.
