---
name: adversarial-review
description: >-
  demir-kit adversarial gate — two independent reviewer workers, fixer, both must approve.
  Re-run behavior command and ui-gate if UI-visible changes. Then worker_done.
---

# adversarial-review

## Roles (separate Orca workers)

1. **reviewer-a** — assume code is wrong; numbered findings vs `docs/architecture/` (overview, boundaries, quality-attributes, cost-and-tiers), ADRs, UI guidelines, lint. Do not duplicate open `AR-*` architect findings unless still present in diff.
2. **reviewer-b** — same inputs, **fresh context**; must not see reviewer-a output until both submit (coordinator merges).
3. **fixer** — only items listed by either reviewer.

## Loop

- If either reviewer has open findings → fixer → re-run **both** reviewers.
- Max 5 rounds; then coordinator `ask` (human language).

## Approval

Both reviewers return `{ "approved": true, "findings": [] }`.

## Regression

1. Run behavior gate command for this CP.
2. If diff touches UI files (coordinator rule): dispatch `ui-gate` visual + interaction again.

## Evidence

Coordinator fills `evidence-comment-template.md` on issue.

## Complete

`worker_done` with `outcome succeeded` only after above.
