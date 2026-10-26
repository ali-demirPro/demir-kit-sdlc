# Commercial & growth stewardship

Sürüm: demir-kit **1.7.1**. Canonical journey: **`product-lifecycle.md`**. Handoff: **`envision-handoff.md`**.

## Purpose

Satışa çevirme: positioning, monetization, GTM, launch readiness — **mühürlü artifact + gate**, spec seli yok.

## Greenfield order

```
kit-envision (§ Council — commercial) → discovery-approved
  → kit-init → scope-triage
  → commercial_baseline epic (skip if factory.waived_baselines includes commercial_baseline)
  → architecture_baseline (parallel OK when not waived)
  → greenfield_product (baseline labels OR waivers + brief artifacts)
  → feature CPs (gates.commercial on marketing/store touch)
  → launch-readiness pack before store_release human QA
```

When **waived**: require brief § Council — positioning/GTM/revenue + committed `docs/product/positioning.md` / `gtm-lite.md` if Handoff promises split files.

## Skills

| Skill | Role |
|-------|------|
| `product-strategy` | ICP, positioning |
| `monetization-brief` | Model, pricing hypothesis |
| `gtm-lite` | Channels, launch slice, ASO outline |
| `commercial-review` | Cross-surface message gate |

## Issue `commercial` block

See `factory-schema.yaml`. Key fields: `baseline_issue`, `steward`, `frozen_at`, `monetization_model`, `gtm_confirmed`.

## Labels

| Label | Meaning |
|-------|---------|
| `commercial-baseline-done` | Human approved commercial baseline |
| `commercial-revise` | commercial-review open |

## Repo docs (MVO)

```
docs/product/
  context.md          # envision / intake mirror
  positioning.md      # product-strategy
  monetization-brief.md
  gtm-lite.md
  analytics-growth.md # optional CP
```

## vs solution-architect

| Topic | Owner |
|-------|--------|
| Infra cost, free tier | architect `cost-and-tiers.md` |
| Revenue model, price hypothesis | monetization-brief |
| Both must agree before paid tier + premium pricing |

## Launch

`launch-readiness` platform pack — checklist before `store_release` / human submit.
