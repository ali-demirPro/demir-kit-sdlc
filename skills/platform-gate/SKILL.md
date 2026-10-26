---
name: platform-gate
description: >-
  Run a platform pack checklist (apple-hig, apple-a11y, web-ux, …) after the core
  gates, as ordered by the factory profile.
---

# platform-gate

## Input

- `pack` id (e.g. `apple-hig`)
- Profile `platform_packs` and `extra_gates` (issue `factory.profile` selects it)
- Checklist: `delivery/packs/<pack>/checklist.md`

## When

The profile's `extra_gates` defines the order (e.g. after `ui` or `adversarial`).

## Execution

1. Read the checklist.
2. Run the profile `extra_gates` command from `ecosystem.yaml` if defined;
   otherwise review-only.
3. Return JSON pass/fail like `ui-gate`; record `reviews.platform` in evidence.

## Store packs

`apple-asc`, `google-play`: never auto-submit. Document readiness for human QA.

## Quality tier

- `platform_excellence`: all profile packs required.
- `standard`: packs selected by the profile (or issue scope); a subset is allowed.
