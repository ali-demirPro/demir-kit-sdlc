---
name: kit-feature
description: >-
  Product owner command — scope KEEP/DEFER/CUT (alias for scope-triage). Use when
  prioritizing backlog, MVP cuts, or confirming brief § Development bets.
---

# kit-feature

**Canonical skill:** `${kit.root}/skills/scope-triage/SKILL.md` (read and follow that file).

Apply `human-communication.md` for all user messages.

## When the owner says "kit-feature"

- Run **scope-triage** logic from the canonical skill.
- Input: `docs/product/discovery-brief.md` § Development bets (if present), session notes, deep analysis P0/P1 lists.
- Output: confirmed `scope_triage` on issue YAML + label **`scope-confirmed`** when done.

## Do not

- Re-run full kit-envision council Q&A if brief is already approved.
- Seal issues (`agent-approved`) — use **kit-build** instead.
