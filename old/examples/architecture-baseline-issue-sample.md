## Summary

New product architecture baseline — decisions, boundaries, cost/tier policy before any feature code.

## Human checklist (baseline sign-off)

- [ ] Platform and module choices match product goals
- [ ] Free tier policy acceptable for MVP
- [ ] Evolution roadmap phases realistic

```yaml demir-kit
demir_kit_version: "1"
package_version: 1
mode: bootstrap
entry:
  kind: architecture_baseline
  summary: İlk mimari mühür — kod CP yok, docs + ecosystem.
factory:
  profile: game-flutter
  product_class: game
  stacks: [flutter]
  quality_tier: standard
  distribution: [app_store_connect, play_console]
  platform_packs: [flutter-multi, game-liveops]
  store_ops_in_scope: false
  architecture_baseline_required: false
architecture:
  steward: agent
  review_policy:
    output_review: off
    tier_review_cadence: monthly
intent: Establish system map, ADRs, cost guardrails, and ecosystem.yaml for a Flutter game plus marketing.
products: [game, marketing]
surfaces: [game.client, marketing.site, legal.pages]
reference:
  kind: design_docs
  summary: Templates under references/templates/architecture/ in demir-kit.
  paths:
    - docs/architecture/
    - ecosystem.yaml
acceptance_criteria:
  - overview.md and boundaries.md merged
  - At least three ADRs (platform, data, cost/tier)
  - cost-and-tiers.md lists every external service with zone policy
  - evolution-roadmap.md has phase 0 and refactor backlog section
out_of_scope:
  - Feature implementation
  - Store submission
decisions: []
dependencies: []
tests_plan:
  - checkpoint_id: CP-ARCH-1
    cases:
      - name: decision matrix exists
        expectation: decision-matrix.md lists alternatives and selected option
        edge: false
  - checkpoint_id: CP-ARCH-2
    cases:
      - name: adr seed set
        expectation: docs/architecture/decisions contains at least 3 ADR files
        edge: false
  - checkpoint_id: CP-ARCH-3
    cases:
      - name: ecosystem validates
        expectation: ecosystem.yaml present and paths consistent with boundaries.md
        edge: false
  - checkpoint_id: CP-ARCH-4
    cases:
      - name: tier policy complete
        expectation: cost-and-tiers.md has green/yellow/red rules and exit triggers table
        edge: false
  - checkpoint_id: CP-ARCH-5
    cases:
      - name: human baseline label
        expectation: issue label architecture-baseline-done after user confirms
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
      - Matrix and overview draft
  - id: CP-ARCH-2
    title: ADR seed PR
    order: 2
    depends_on: [CP-ARCH-1]
    surfaces: [game.client]
    gates: { behavior: false, ui: false, adversarial: false, architect: true, human: false }
    acceptance_criteria:
      - ADRs in repo
  - id: CP-ARCH-3
    title: Ecosystem and boundaries
    order: 3
    depends_on: [CP-ARCH-2]
    surfaces: [game.client, marketing.site]
    gates: { behavior: false, ui: false, adversarial: false, architect: true, human: false }
    acceptance_criteria:
      - boundaries.md + yaml
  - id: CP-ARCH-4
    title: Cost and roadmap
    order: 4
    depends_on: [CP-ARCH-3]
    surfaces: [game.client]
    gates: { behavior: false, ui: false, adversarial: false, architect: true, human: false }
    acceptance_criteria:
      - cost-and-tiers + evolution
  - id: CP-ARCH-5
    title: Baseline sign-off
    order: 5
    depends_on: [CP-ARCH-4]
    surfaces: [game.client]
    gates: { behavior: false, ui: false, adversarial: false, architect: false, human: true }
    acceptance_criteria:
      - architecture-baseline-done
```
