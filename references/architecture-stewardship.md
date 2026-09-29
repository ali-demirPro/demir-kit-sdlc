# Mimari sürdürülebilirlik (stewardship)

Sürüm: demir-kit **1.7.1**. Canonical journey: **`references/product-lifecycle.md`**. Handoff: **`envision-handoff.md`**. Skill: `solution-architect`.

## Roller

| Rol | Kim | Ne yapar |
|-----|-----|----------|
| Steward | `architecture.steward` (`agent` \| `human`) | Drift, tier, ADR güncellemesi |
| Baseline | `architecture_baseline` epic | İlk sistem haritası + economics |
| Reviewer | `output-review` worker | PR/CP çıktısı — approve / revise |

Architect **varsayılan olarak feature kodu yazmaz**; yönlendirme ve gate kararı üretir.

## Greenfield sırası

```
kit-setup → kit-envision → discovery-approved
  → kit-init (brief § Proposed ecosystem)
  → scope-triage (scope-confirmed; merge brief § Development bets)
  → factory-routing
  → architecture_baseline (skip if factory.waived_baselines includes architecture_baseline AND brief § Handoff documents coverage)
  → work-package greenfield_product (architecture.baseline_issue or waive)
  → feature CP'ler (gates.architect: true önerilir)
```

Envision brief’te mimari council yeterliyse: Handoff’ta **`architecture_covered: yes`** → seal’de `factory.waived_baselines: [architecture_baseline]`. Yine de `docs/architecture/overview.md` + `boundaries.md` — `kit-init` promote veya kısa architect CP (`envision-handoff.md`).

Feature mühürü **baseline tamamlanmadan** `agent-approved` olmamalı (`health-check` + waived_baselines).

## Issue `architecture` bloğu

Şema: `factory-schema.yaml` → `architecture`.

| Alan | Açıklama |
|------|----------|
| `baseline_issue` | Tamamlanan baseline epic/issue numarası |
| `baseline_commit` | Repo SHA when baseline frozen (optional) |
| `steward` | `agent` \| `human` |
| `frozen_at` | ISO date when baseline human-approved |
| `review_policy.output_review` | `required` \| `boundary_only` \| `off` |
| `review_policy.tier_review_cadence` | `weekly` \| `monthly` \| `on_amend` |
| `review_mode` | Orca worker mode override |

### `output_review` levels

- **required** — her CP with `gates.architect: true` (default for greenfield children)
- **boundary_only** — architect review only if diff touches paths in `boundaries.md` “sensitive” list
- **off** — only adversarial + platform (use sparingly; document in ADR)

## Tetikleyiciler

| Olay | Architect mode |
|------|----------------|
| Yeni `ecosystem_amend` | `baseline` delta + `decision` ADRs |
| `compliance_pass` | `output-review` sample + `tier-review` |
| Quota yellow/red (automation) | `tier-review` |
| Adversarial finds boundary mismatch | `refactor-proposal` |
| `work-package-amend` + `adr_required` | `decision` |

## Repo artifact'ları (canonical)

```
docs/architecture/
  overview.md
  boundaries.md
  quality-attributes.md
  cost-and-tiers.md
  evolution-roadmap.md
  decision-matrix.md
  decisions/ADR-NNN-*.md
```

Adversarial reviewers **must** read these paths when present (`adversarial-review` skill).

## Drift

Coordinator veya automation:

1. Diff last N days vs `overview.md` / `boundaries.md`
2. Open drift issue or run `refactor-proposal`
3. Never silent overwrite of ADR — amend or supersede ADR

## Free tier exit

Documented only in `cost-and-tiers.md` + linked issues. Architect plans:

1. Trigger (MAU, feature need, compliance)
2. Ordered migration steps
3. Rollback / dual-run period
4. Cost delta estimate

Human approves billing changes; architect supplies plan.

## Labels

| Label | Meaning |
|-------|---------|
| `architecture-baseline-done` | Baseline human-approved |
| `architect-revise` | Output review failed; worker must address findings |
