---
name: platform-gate
description: >-
  Run a platform pack checklist (apple-hig, apple-a11y, etc.) after core demir-kit
  gates per factory profile. Coordinator passes pack id.
---

# platform-gate

## Input

- `pack` id (e.g. `apple-hig`)
- Issue `factory.platform_packs` and profile `extra_gates`
- Checklist: `references/packs/<pack>/checklist.md`

## When

Profile `extra_gates` defines order (e.g. after `ui`, after `adversarial`).

## Execution

1. Read checklist.
2. Run product command from `ecosystem.yaml` if `gates.platform_<pack>` defined; else reviewer-only.
3. Output JSON pass/fail like `ui-gate`.

## Store packs

`apple-asc`, `google-play`: never auto-submit; document readiness for human QA.

## quality_tier

`platform_excellence`: all profile packs required.
`standard`: only packs listed on issue (may be subset).
