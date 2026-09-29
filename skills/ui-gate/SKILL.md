---
name: ui-gate
description: >-
  demir-kit UI gate — scoped screenshot compare, INVALID state, dual reviewers
  (visual + interaction). Use orca-cli browser or emulator skills. Reviewers must
  not read project implementation skills.
---

# ui-gate

When `gates.ui: true`. Read `checkpoints[].ui_scope` from issue YAML.

## Reviewer isolation

Workers run with instructions limited to:

- `reference` block from issue
- Prototype artifact / `design-md` paths
- Captured screenshots only

**Do not** use generic repo coding shortcuts or “good enough” project norms.

## Modes (coordinator dispatches twice)

| Mode | Focus |
|------|--------|
| `visual` | Structure, spacing, typography, color vs reference/prototype |
| `interaction` | Same user actions; same outcomes |

## Capture

- Web: `orca-cli` `goto`, `set device`, `screenshot`
- Mobile: `orca-emulator` / `orca-emulator-android`
- **Same named state** on reference and implementation (`reference.states`)

## Comparison output (required JSON)

```json
{
  "pass": false,
  "comparison_valid": true,
  "findings": [
    { "severity": "blocker|minor", "location": "hero title", "description": "..." }
  ]
}
```

- `comparison_valid: false` → **INVALID** (wrong screen/state/section). Do not pass. Coordinator re-captures matching state.
- Default: visual differences fixable in code are **blockers**.

## Scoped compare

If `ui_scope` is `"navigation bar and title only"`, ignore rest of reference screenshot.

## Fix loop

Fixer worker → re-capture → both modes again.

## User

Escalate to coordinator `ask` in human language only (`human-communication.md`).
