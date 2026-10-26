## Summary

Players can claim daily rewards in the Flutter client; marketing landing shows the same promo CTA linking to store.

## Surfaces

- `game.client`
- `marketing.site`

## Human checklist (QA)

- [ ] Claim reward offline shows error
- [ ] Landing CTA opens store listing
- [ ] No change to legal pages in v1

```yaml demir-kit
demir_kit_version: "1"
package_version: 1
mode: extend
entry:
  kind: feature
  summary: Mevcut oyuna günlük ödül ve marketing CTA hizalaması.
factory:
  profile: game-flutter
  product_class: game
  stacks: [flutter]
  quality_tier: standard
  distribution: [app_store_connect, play_console]
  platform_packs: [flutter-multi, game-liveops]
  store_ops_in_scope: false
intent: Daily reward claim in game plus aligned promo on marketing site.
products: [game, marketing]
surfaces: [game.client, marketing.site]
reference:
  kind: mixed
  summary: Flutter client claim flow; marketing hero uses shared i18n promo key.
  paths:
    - apps/game/lib/features/rewards/
    - docs/design/game.md
    - docs/design/web.md
  states:
    - empty claim button
    - claim success
    - second claim same day error
acceptance_criteria:
  - "[game.client] User taps claim once per day and sees updated balance."
  - "[game.client] Second claim same day shows clear message."
  - "[marketing.site] Hero CTA reflects active promo copy from shared i18n."
out_of_scope:
  - Push notifications
  - Privacy policy update
decisions:
  - date: "2026-09-29"
    author: "@you"
    text: "Reward idempotency keyed by UTC date."
    adr_required: false
dependencies: []
tests_plan:
  - checkpoint_id: CP-1
    cases:
      - name: once per day rule
        expectation: eligibility false on second claim same UTC day
        edge: true
  - checkpoint_id: CP-2
    cases:
      - name: claim persists balance
        expectation: balance increases after successful claim
        edge: false
  - checkpoint_id: CP-3
    cases:
      - name: claim button disabled when ineligible
        expectation: UI shows message from domain
        edge: false
checkpoints_preapproved: true
checkpoints:
  - id: CP-1
    title: Reward eligibility rules
    order: 1
    depends_on: []
    surfaces: [game.client]
    gates: { behavior: true, ui: false, adversarial: true }
    acceptance_criteria:
      - Domain once-per-day
  - id: CP-2
    title: Claim persistence
    order: 2
    depends_on: [CP-1]
    surfaces: [game.client]
    gates: { behavior: true, ui: false, adversarial: true }
    acceptance_criteria:
      - Repository or API hook
  - id: CP-3
    title: Claim button UI
    order: 3
    depends_on: [CP-2]
    surfaces: [game.client]
    gates: { behavior: true, ui: true, adversarial: true }
    ui_scope: claim row and primary button only
    acceptance_criteria:
      - Matches design claim states
  - id: CP-4
    title: Marketing hero CTA
    order: 4
    depends_on: [CP-2]
    surfaces: [marketing.site]
    gates: { behavior: true, ui: true, adversarial: true, commercial: true }
    ui_scope: hero section only
    acceptance_criteria:
      - i18n promo key
```
