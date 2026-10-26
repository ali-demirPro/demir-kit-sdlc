---
name: monetization-brief
description: >-
  Revenue model, pricing hypothesis, unit economics sketch, experiments. Complements
  solution-architect cost-and-tiers (cost) with revenue side. Human pricing approval.
---

# monetization-brief

VB **THE ECONOMIST** (MVO). Does not set live prices in stores — prepares brief + decisions.

Apply `human-communication.md`.

## When

- Skip if `docs/product/monetization-brief.md` promoted at `kit-init` (`envision-handoff.md`)
- `commercial_baseline` monetization CP
- IAP/subscription/freemium before store CPs
- `scope-triage` flagged monetization complexity

## Cover

1. **Model** — free, freemium, subscription, IAP, ads, hybrid, B2B seat
2. **Pricing hypothesis** — tiers, anchor, trial (if any)
3. **Unit economics sketch** — CAC assumption band, LTV drivers (qualitative OK for MVP)
4. **Experiments** — 2–3 tests (price, paywall placement, trial length)
5. **Alignment** — `docs/architecture/cost-and-tiers.md` (margin / infra vs price)

## Outputs

- `docs/product/monetization-brief.md` (template)
- `decisions[]` entry with `adr_required: true` if pricing model is binding
- Issue `commercial.monetization_model` enum in YAML

## Human gate

Live price, store IAP products, Stripe prices → **always human** (`gate-contract.md`).

## Complete

Brief in repo + human acknowledged monetization approach on issue comment or label step.
