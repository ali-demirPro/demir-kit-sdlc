---
name: test-plan
description: >-
  Required before seal — populate tests_plan in issue YAML per checkpoint.
  Integration-style cases from reference; edge cases beyond happy path.
---

# test-plan

## When (mandatory)

- During **`work-package` phase 5**, before seal.
- Coordinator may refine at Run start; must not delete cases without user amend.

## Input

- `reference` block (paths, running app, prototype)
- `acceptance_criteria` and checkpoint list

## Output

Issue YAML `tests_plan[]`:

```yaml
tests_plan:
  - checkpoint_id: CP-1
    cases:
      - name: once per day claim
        expectation: second claim same day rejected
        edge: true
```

Also mirror as issue comment `## Test plan` checklist for human skim.

## Style

- User-perspective integration tests where possible.
- Map every CP with `gates.behavior: true` to at least one case.

## Storage

Never `docs/work-packages/`; only GitHub issue body/comment.
