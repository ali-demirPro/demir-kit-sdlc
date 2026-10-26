---
name: discovery-intake
description: >-
  Internal context capture — invoked inside kit-envision or brownfield quick pass.
  Do not use standalone on greenfield; use kit-envision instead.
---

# discovery-intake

**Feasibility first:** analiz ve bağlam, spec/CP mühüründen önce.

Apply `human-communication.md`. Kullanıcıya “Navigator” veya “VB” deme.

## When

- Sub-step inside **`kit-envision`** (preferred for new products)
- Legacy / quick context only without full envision
- Existing repo augment when `discovery-brief` already approved

Greenfield without brief: run **`kit-envision`** first, not standalone intake.

## Questions (batch in 1–2 messages, options where possible)

1. **Proje türü:** mobile app, web/SaaS, e-commerce, marketplace, API/platform, game, other
2. **Kitle:** B2C, B2B, B2B2C
3. **Platform:** iOS, Android, both, web-only, multi-surface
4. **Takım:** solo, duo, small (3–5), agency (5+)
5. **MVP timeline:** weeks or target date
6. **Bütçe bandı:** bootstrapped (&lt;$10k), angel, seed, series_a_plus
7. **Must-have (3–5):** short phrases
8. **Teknik seviye:** non_technical, junior, mid, senior
9. **Gelir beklentisi (1 cümle):** free, freemium, subscription, B2B, unsure
10. **İlk kanal hipotezi:** ASO, web, sosyal, B2B satış, … (product-strategy / gtm-lite besler)

## Repo output

Copy from `references/templates/product/context.md` → `docs/product/context.md` (PR).

## Issue YAML (`discovery` + `feasibility` seeds)

Pass to `scope-triage` then `factory-routing` / `work-package`:

```yaml
discovery:
  product_type: mobile_app
  audience: b2c
  platforms: [ios, android]
  team_size: solo
  timeline_weeks: 12
  budget_band: bootstrapped
  tech_level: mid
  must_have_features:
    - User auth
    - Core loop X
feasibility:
  score: null  # scope-triage + architect may refine
  go: null
  strengths: []
  risks: []
```

## Labels

After user confirms context accurate: use parent **`discovery-approved`** from `kit-envision` — do not add `discovery-done`.

## Do not

- Generate 8 spec folders or Linear CSV (tracker stays GitHub).
- Seal `agent-approved` work package in this skill — only context + optional discovery issue.

## Next

1. **`scope-triage`** — KEEP/DEFER/CUT on must-haves and inferred features
2. **`factory-routing`**
3. **`architecture_baseline`** when profile requires
