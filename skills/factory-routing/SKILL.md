---
name: factory-routing
description: >-
  Classify an idea into factory profile, entry kind, quality tier, and distribution.
  Use before or at start of work-package sealing. Human language only.
---

# factory-routing

Fabrika girişi: fikir → **hangi profil**, **hangi entry**, **hangi çıktılar**.

## When

- New idea (greenfield, store, compliance, new surface)
- Before `work-package` phase 1 if classification unclear

## Greenfield pipeline (order)

1. **`kit-envision`** — `discovery-brief` + `discovery-approved` (new products)
2. **`kit-init`** — ecosystem from approved brief
3. **`scope-triage`** — KEEP/DEFER/CUT + `feasibility`; label `scope-confirmed`
4. **This skill** — profile, entry, distribution
5. Read approved brief § Handoff (`commercial_covered` / `architecture_covered` per `envision-handoff.md`) → set `factory.waived_baselines` on parent/greenfield issue.
6. If `factory.pilot_mode: true` in `decisions` → may waive both baselines with documented rationale (still need MVO files per handoff).
7. Profile default: `kit.config.yaml` `factory.default_profile` when brief Handoff silent.
8. **`commercial_baseline`** if `commercial_baseline_required` and `commercial_baseline` not in `waived_baselines` → `commercial-baseline-done`
9. **`architecture_baseline`** if required and not waived → `architecture-baseline-done`
10. **`work-package`** mühür (`commercial.baseline_issue` + `architecture.baseline_issue` when applicable)

Brownfield feature: **`kit-envision` lite** or `context.md`; waive envision only via `decisions` + coordinator `ask` (see `product-lifecycle.md`).

## Ask user (human-communication.md)

1. Ne üretiyoruz? (oyun, web app, native iOS, Flutter, birleşim)
2. Dağıtım? (App Store, Play, web-only, TestFlight, …)
3. Kalite hedefi? (`standard` vs platform excellence — Awards seviyesi)
4. Mağaza yönetimi (ASC/Play) bu işin parçası mı?

## Map to profile

| Sinyal | Profile |
|--------|---------|
| Native iOS excellence | `apple-native-excellence` |
| Flutter app | `flutter-platform` |
| Game | `game-flutter` |
| Web + marketing | `web-product` |
| Sadece store/metadata | `store-release` |

Read `profiles/<id>.yaml` for packs and suggested surfaces.

## Map entry.kind

| Durum | kind |
|-------|------|
| Ürün yönü / envision (opsiyonel issue) | `product_envision` |
| Yeni ürün — commercial baseline | `commercial_baseline` |
| Yeni ürün — mimari baseline | `architecture_baseline` |
| Yeni ürün / repo (kod) | `greenfield_product` |
| Mevcut repoya özellik | `feature` |
| Yayın / listing | `store_release` |
| Sadece uyumluluk turu | `compliance_pass` |
| Yeni surface (macOS, legal, …) | `ecosystem_amend` |

## Output for work-package

Pass to `work-package`:

```yaml
entry:
  kind: feature
  summary: "..."
factory:
  profile: apple-native-excellence
  product_class: native-ios
  stacks: [swiftui, ios]
  quality_tier: platform_excellence
  distribution: [app_store_connect]
  platform_packs: [...]  # from profile
  store_ops_in_scope: true|false
  architecture_baseline_required: true|false  # from profile when greenfield
```

When sealing greenfield feature work, also pass:

```yaml
architecture:
  steward: agent
  baseline_issue: <number after baseline epic done>
  review_policy:
    output_review: required
    tier_review_cadence: monthly
```

Merge `tests_plan_seeds` from profile into issue `tests_plan` (dedupe by checkpoint_id).

Inject `extra_gates` from profile into coordinator notes (issue comment `## Factory gates`).

Merge **`capability-activation.md`**: `factory.activated_skills`, `factory.skipped_capabilities` from profile + issue signals.

## Architecture baseline

If **new product** or repo without `docs/architecture/overview.md`:

1. Respect brief Handoff: `architecture_covered: yes` → waive epic; ensure `kit-init` promoted architecture stubs.
2. Else set `factory.architecture_baseline_required: true` on downstream issues.
3. Epic `entry.kind: architecture_baseline` → **`solution-architect`** (`baseline`); after `architecture-baseline-done`, seal `greenfield_product` with `architecture.baseline_issue`.

## Ecosystem

`greenfield_product`: prefer post-**`kit-init`** `ecosystem.yaml`. **`ecosystem-bootstrap`** for `ecosystem_amend` only (brownfield surface add); still requires `discovery-approved` if yaml shape changes materially (`envision-stewardship.md`).
