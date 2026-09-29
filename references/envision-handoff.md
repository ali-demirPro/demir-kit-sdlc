# Envision handoff (brief → repo + issue YAML)

Sürüm: demir-kit **1.7.1**. Runs after **`discovery-approved`**, during **`kit-init`** (agent + `kit-init.sh`).

Canonical journey: `product-lifecycle.md`.

## Terminology (do not invert)

| Brief § Handoff field | Meaning | Issue YAML action |
|----------------------|---------|-------------------|
| `commercial_covered: yes` | Council commercial is enough to **skip** `commercial_baseline` epic | Add `commercial_baseline` to `factory.waived_baselines` |
| `commercial_covered: no` | Run **`commercial_baseline`** epic | Do **not** waive |
| `architecture_covered: yes` | Council + ADR seeds enough to **skip** `architecture_baseline` epic | Add `architecture_baseline` to `factory.waived_baselines` |
| `architecture_covered: no` | Run **`architecture_baseline`** epic | Do **not** waive |

Mirror in brief frontmatter / tracking issue:

```yaml
envision:
  baselines_covered:
    commercial: true   # same as commercial_covered: yes
    architecture: false
```

**Never** set `waived_baselines` when Handoff says `*_covered: no`.

## Materialize matrix

| Source (approved brief) | Output path | Who |
|-------------------------|-------------|-----|
| § Proposed ecosystem (yaml block) | `ecosystem.yaml` | `kit-init.sh` + agent reconcile |
| § Proposed folder layout (`text` tree) | directories under repo root | `kit-init.sh` (safe paths only) + agent |
| § Vision + § Council — positioning | `docs/product/positioning.md` | **Agent** (`kit-init` skill) if missing or Handoff `split_files: positioning` |
| § Council — GTM | `docs/product/gtm-lite.md` | Agent when commercial waived or split promised |
| § Council — revenue sketch | `docs/product/monetization-brief.md` | Agent when monetization in scope |
| § Council — platform (chosen path) | `docs/architecture/overview.md` + `boundaries.md` stubs | Agent when architecture waived **or** always seed stubs before feature CPs |
| § Development bets | (no new file) | `scope-triage` imports table |
| § Handoff `factory_profile_recommended` | `factory-routing` input; optional `kit.config.yaml` `factory.default_profile` | `factory-routing` |

Templates for promoted files: `references/templates/product/*.md`, `references/templates/architecture/*.md`.

Promotion = extract brief sections into template skeletons; **do not** duplicate full brief into repo. Link brief path in each file header.

## `factory-routing` seal fields

On first `greenfield_product` parent (or epic), copy from brief § Handoff:

```yaml
factory:
  profile: <from Handoff>
  waived_baselines: [...]   # only entries with *_covered: yes
  pilot_mode: false         # see below
envision:
  baselines_covered:
    commercial: true
    architecture: false
  tracking_issue: <N>
  brief_path: docs/product/discovery-brief.md
```

## `pilot_mode`

When `factory.pilot_mode: true` on issue:

- May set `waived_baselines: [commercial_baseline, architecture_baseline]` **only** with user `decisions` note + brief or comment rationale.
- Still require **`discovery-approved`** unless explicit envision waive in `decisions`.
- `health-check` treats pilot like waived baselines for labels; MVO files still required before store/marketing CPs.

## Tracking issue sync

Single **Envision** issue (`entry.kind: product_envision`). On brief approve:

1. Commit brief with `envision.status: approved` in **YAML frontmatter** (not body prose).
2. `gh issue edit <N> --add-label discovery-approved --remove-label envision-draft`
3. Update issue body `envision:` block to match frontmatter (`status`, `platform_decision`, `factory_profile_recommended`, `baselines_covered`).

**Source of truth:** committed `discovery-brief.md` frontmatter wins on conflict; issue is index for labels.

## After materialize

1. `scope-triage` — confirm § Development bets
2. `factory-routing` — profile + `waived_baselines` on seal
3. Baseline epics only for non-waived kinds
4. `work-package` → `agent-approved`

See `skills/kit-init/SKILL.md`, `tools/kit-init.sh`.
