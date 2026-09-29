## Summary

Greenfield epic — after **`kit-envision`** + **`kit-init`** + **`scope-triage`**. Ready for architecture baseline (or waived per brief Handoff — `envision-handoff.md`).

## Human checklist

- [ ] Context matches product vision
- [ ] CUT items accepted
- [ ] Feasibility score acceptable

```yaml demir-kit
demir_kit_version: "1"
package_version: 1
mode: bootstrap
entry:
  kind: architecture_baseline
  summary: Mimari baseline follows confirmed discovery and scope.
factory:
  profile: game-flutter
  product_class: game
  stacks: [flutter]
  quality_tier: standard
  distribution: [app_store_connect, play_console]
  platform_packs: [flutter-multi, game-liveops]
  store_ops_in_scope: false
  architecture_baseline_required: false
  activated_skills:
    - kit-envision
    - scope-triage
    - solution-architect
    - design-md
    - platform-gate
  skipped_capabilities:
    - id: gtm-lite
      reason: Launch marketing Phase 2
    - id: help-center-pack
      reason: MVP self-serve only
discovery:
  product_type: game
  audience: b2c
  platforms: [ios, android]
  team_size: solo
  timeline_weeks: 12
  budget_band: bootstrapped
  tech_level: mid
  must_have_features:
    - Daily reward loop
    - Account login
    - Promo on marketing site
  context_doc_path: docs/product/context.md
feasibility:
  score: 7
  go: true
  strengths:
    - Proven freemium game patterns
    - Flutter single codebase
  risks:
    - text: Store discovery hard
      mitigation: Influencer test week 8
    - text: Liveops backend cost
      mitigation: Free tier caps in cost-and-tiers.md
scope_triage:
  confirmed: true
  confirmed_at: "2026-09-29"
  items:
    - name: Daily reward loop
      decision: keep
      technical: 3
      value: 5
      effort_hours: 32
      roi_note: high
      reasoning: Core loop
      phase: mvp
    - name: AI opponent
      decision: cut
      technical: 2
      value: 1
      effort_hours: 120
      roi_note: low
      reasoning: Cost and unproven
      phase: never
    - name: Web admin dashboard
      decision: defer
      technical: 4
      value: 3
      effort_hours: 40
      roi_note: medium
      reasoning: Manual ops OK for MVP
      phase: phase-2
adaptive:
  cadence: weekly
  velocity_warning_threshold: 0.7
  consecutive_slow_weeks: 0
architecture:
  steward: agent
  review_policy:
    output_review: off
    tier_review_cadence: monthly
intent: Lock product context and MVP scope before architecture artifacts.
products: [game, marketing]
surfaces: [game.client, marketing.site]
reference:
  kind: design_docs
  summary: docs/product/context.md and evolution-roadmap defer list.
  paths:
    - docs/product/context.md
    - docs/architecture/evolution-roadmap.md
acceptance_criteria:
  - scope_triage.confirmed true
  - feasibility.go true
out_of_scope:
  - AI opponent
decisions:
  - date: "2026-09-29"
    author: "@you"
    text: Web admin deferred to phase-2 per triage.
    adr_required: false
dependencies: []
tests_plan:
  - checkpoint_id: CP-ARCH-1
    cases:
      - name: context doc exists
        expectation: docs/product/context.md matches discovery block
        edge: false
checkpoints_preapproved: true
checkpoints:
  - id: CP-ARCH-1
    title: Discovery and matrix
    order: 1
    depends_on: []
    surfaces: [game.client]
    gates: { behavior: false, ui: false, adversarial: false, architect: true, human: false }
    acceptance_criteria:
      - Context + triage synced
```
