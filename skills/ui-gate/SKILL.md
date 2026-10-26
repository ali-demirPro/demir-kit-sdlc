---
name: ui-gate
description: >-
  Scoped screenshot compare with INVALID state handling and two independent
  reviewers (visual + interaction). Reviewers must not read implementation skills.
---

# ui-gate

When `gates.ui: true`. Read `checkpoints[].ui_scope` from the issue seal.

## Reviewer isolation

Workers see only:

- `reference` block from the issue
- prototype artifact / design paths
- captured screenshots

No repo coding conventions, no "good enough" shortcuts.

## Modes (dispatch twice)

| Mode | Focus |
|------|-------|
| `visual` | Structure, spacing, typography, color vs reference |
| `interaction` | Same actions, same outcomes |

## Capture

- Web: Orca browser `goto`, `set device`, `screenshot`
- Mobile: `orca-emulator` / `orca-emulator-android`
- Same named state on both sides (`reference.states`)

## Output (required JSON)

```json
{
  "pass": false,
  "comparison_valid": true,
  "findings": [
    { "severity": "blocker|minor", "location": "hero title", "description": "…" }
  ]
}
```

- `comparison_valid: false` → INVALID: wrong screen/state. Never pass; re-capture.
- Fixable visual differences are blockers by default.
- Scope: if `ui_scope` names a region, ignore the rest of the screenshot.

## Loop

Fixer → re-capture → both modes again (max 2 re-captures, then ask).

## Evidence

Record in `delivery/protocol/evidence.md`:
- `reviews.ui: pass`
- `reviews.comparison_valid: true|false`
- UI findings as `{ id: UI-1, status: fixed|open }`

Escalate in human language only (`delivery/policies/human-communication.md`).
