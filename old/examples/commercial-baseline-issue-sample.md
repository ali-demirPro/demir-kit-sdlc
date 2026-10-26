## Summary

Commercial baseline — positioning, monetization, GTM, analytics before build.

## Human checklist

- [ ] ICP and MVP promise resonate
- [ ] Pricing approach acceptable (live prices still human later)
- [ ] Launch channels realistic for timeline

```yaml demir-kit
demir_kit_version: "1"
package_version: 1
mode: bootstrap
entry:
  kind: commercial_baseline
  summary: Growth ve satış hattı mühürü — kod CP yok.
factory:
  profile: game-flutter
  product_class: game
  stacks: [flutter]
  quality_tier: standard
  distribution: [app_store_connect, play_console]
  platform_packs: [flutter-multi, game-liveops, launch-readiness]
  store_ops_in_scope: false
  architecture_baseline_required: true
  commercial_baseline_required: false
  activated_skills:
    - product-strategy
    - monetization-brief
    - gtm-lite
    - commercial-review
commercial:
  steward: agent
  strategy_summary: Casual players who want daily rewards without grind.
  monetization_model: freemium
  gtm_confirmed: false
  review_policy:
    commercial_review: required
discovery:
  product_type: game
  audience: b2c
  platforms: [ios, android]
  team_size: solo
  timeline_weeks: 12
  budget_band: bootstrapped
  tech_level: mid
  must_have_features:
    - Daily rewards
    - Marketing promo CTA
scope_triage:
  confirmed: true
  confirmed_at: "2026-09-29"
  items:
    - name: Paid ads campaign
      decision: defer
      reasoning: Organic + ASO first
      phase: phase-2
intent: Seal commercial artifacts for game + marketing surfaces.
products: [game, marketing]
surfaces: [game.client, marketing.site]
reference:
  kind: design_docs
  summary: Product commercial docs under docs/product/.
  paths:
    - docs/product/positioning.md
    - docs/product/monetization-brief.md
    - docs/product/gtm-lite.md
    - docs/product/analytics-growth.md
acceptance_criteria:
  - All four product docs merged
  - gtm-lite alignment table filled for marketing.site vs app
out_of_scope:
  - Paid user acquisition
decisions: []
dependencies: []
tests_plan:
  - checkpoint_id: CP-COM-1
    cases:
      - name: positioning doc
        expectation: positioning.md has ICP and MVP promise one-liner
        edge: false
  - checkpoint_id: CP-COM-2
    cases:
      - name: monetization brief
        expectation: monetization-brief.md lists model freemium and experiments table
        edge: false
  - checkpoint_id: CP-COM-3
    cases:
      - name: gtm lite
        expectation: gtm-lite.md has max 3 MVP channels
        edge: false
  - checkpoint_id: CP-COM-4
    cases:
      - name: north star
        expectation: analytics-growth.md defines north star metric and 3 funnel events
        edge: false
  - checkpoint_id: CP-COM-5
    cases:
      - name: commercial baseline label
        expectation: label commercial-baseline-done after human confirms
        edge: false
checkpoints_preapproved: true
checkpoints:
  - id: CP-COM-1
    title: Positioning
    order: 1
    depends_on: []
    surfaces: [marketing.site]
    gates: { behavior: false, ui: false, adversarial: false, architect: false, commercial: false, human: false }
    acceptance_criteria:
      - product-strategy output
  - id: CP-COM-2
    title: Monetization brief
    order: 2
    depends_on: [CP-COM-1]
    surfaces: [game.client]
    gates: { behavior: false, ui: false, adversarial: false, architect: false, commercial: false, human: false }
    acceptance_criteria:
      - monetization-brief skill
  - id: CP-COM-3
    title: GTM lite
    order: 3
    depends_on: [CP-COM-2]
    surfaces: [marketing.site]
    gates: { behavior: false, ui: false, adversarial: false, architect: false, commercial: false, human: false }
    acceptance_criteria:
      - gtm-lite skill
  - id: CP-COM-4
    title: Analytics growth
    order: 4
    depends_on: [CP-COM-3]
    surfaces: [game.client]
    gates: { behavior: false, ui: false, adversarial: false, architect: false, commercial: false, human: false }
    acceptance_criteria:
      - analytics-growth.md
  - id: CP-COM-5
    title: Commercial sign-off
    order: 5
    depends_on: [CP-COM-4]
    surfaces: [marketing.site]
    gates: { behavior: false, ui: false, adversarial: false, architect: false, commercial: false, human: true }
    acceptance_criteria:
      - commercial-baseline-done
```
