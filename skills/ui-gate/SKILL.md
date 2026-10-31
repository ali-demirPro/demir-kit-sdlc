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
- captured screenshots, console/network excerpts and artifact links

No repo coding conventions, no "good enough" shortcuts.

## Modes (dispatch twice)

| Mode | Focus |
|------|-------|
| `visual` | Structure, spacing, typography, color vs reference |
| `interaction` | Same actions, same outcomes |

## Capture — Orca typed browser

Orca's browser is worktree-scoped and scriptable. Use the typed commands, not
ad-hoc screenshots:

```bash
orca ports --json                       # dev server URL + port
orca goto --url <url> --json
orca wait --text "<ready text>" --timeout-ms 30000 --json
orca snapshot --json                    # @e1, @e2 refs
orca click --element @e3 --json         # re-snapshot after navigation
orca fill --element @e1 --value "..." --json
orca select --element @e2 --value "..." --json
orca keypress --key Enter --json
orca screenshot --json                  # viewport
orca full-screenshot --json             # full page
orca pdf --json                         # printable evidence
orca console --limit 50 --json
orca network --limit 50 --json
orca set device --name "iPhone 12" --json
orca tab profile list --json            # auth/multi-user state
```

- Snapshot → act → re-snapshot on every state change; refs go stale.
- Capture `console` and `network` on failure states; they are part of the
  interaction evidence.
- Store screenshots/PDF as an artifact: `orca artifacts share <file> --json`
  (publishing is opt-in; if disabled, attach the local path to evidence).
- Mobile: `orca emulator list`, `attach`, `tap`, `type`, `gesture`, `button`,
  `rotate`, `kill`; iOS/Android skill for details.

## Same state, both sides

Use the same state name and viewport on reference and build. `comparison_valid:
false` when the screen/state differs; never pass an invalid comparison.

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

Fixer → re-capture → both modes again (max 2 re-captures, then ask). A fix that
changes the UI invalidates both reviewers; re-run both.

## Evidence

Record in `delivery/protocol/evidence.md`:

- `reviews.ui_visual: pass`, `reviews.ui_interaction: pass`
- `reviews.comparison_valid: true|false`
- `orca.artifact`: screenshot/PDF link
- UI findings as `{ id: UI-1, status: fixed|open }`

Escalate in human language only (`delivery/policies/human-communication.md`).
