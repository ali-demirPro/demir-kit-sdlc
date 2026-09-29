---
name: commercial-review
description: >-
  Gate — message and offer alignment across app, marketing.site, store copy drafts.
  Approve or revise_required (CR-*). Does not implement; guides workers.
---

# commercial-review

Parallel to `solution-architect` `output-review` for **commercial** fit.

## When

- `gates.commercial: true` on checkpoint
- Touches `marketing.site`, store listing paths, paywall copy, shared i18n promo keys
- Before or after `ui` when only copy alignment (coordinator choice); default **after behavior, before ui** if UI shows pricing/promo

## Reads

- `docs/product/positioning.md`, `gtm-lite.md`, `monetization-brief.md`
- `docs/product/analytics-growth.md` if analytics events in diff
- Issue `acceptance_criteria` with `[marketing.site]` tags
- Diff / PR

## Verdict

```yaml
verdict: approved | revise_required
findings:
  - id: CR-1
    severity: blocker | major | minor
    category: positioning | pricing_messaging | channel | aso | analytics | consistency
    location: path or surface
    guidance: imperative fix for implementation worker
```

Max **3** rounds per CP; then coordinator `ask`.

Label `commercial-revise` while open.

## Does not

- Approve final store submit or live ad spend (human).
- Replace `platform-gate` ASC/Play checklists.

## Complete

`worker_done` when `verdict: approved` or user waives minors.
