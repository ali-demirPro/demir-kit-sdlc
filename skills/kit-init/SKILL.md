---
name: kit-init
description: >-
  After discovery-approved — materialize ecosystem.yaml, folders, and MVO stubs
  from discovery-brief per envision-handoff.md. Run kit-init.sh then agent promote.
---

# kit-init

**Önkoşul:**

1. **`kit-setup`** done (`kit.config.yaml`).
2. **`kit-envision`** done: `docs/product/discovery-brief.md` frontmatter `envision.status: approved` and label **`discovery-approved`** (or envision waive in `decisions` + `ask`).

**Playbook:** `${kit.root}/references/envision-handoff.md`.

Apply `human-communication.md`.

## Step 1 — Shell scaffold

```bash
export KIT_ROOT=vendor/demir-kit
"$KIT_ROOT/tools/kit-init.sh" --repo owner/name
# profile optional; defaults to kit.config.yaml factory.default_profile
```

Script: ecosystem from § Proposed ecosystem, dirs from § Proposed folder layout (safe paths), standard `docs/*` tree, `gate-behavior.sh`.

## Step 2 — Agent materialize (required)

From **approved** brief only:

| Brief section | Output | Condition |
|---------------|--------|-----------|
| § Council — positioning | `docs/product/positioning.md` | Handoff `split_files` includes positioning **or** `commercial_covered: yes` |
| § Council — GTM | `docs/product/gtm-lite.md` | split or commercial waived |
| § Council — revenue | `docs/product/monetization-brief.md` | monetization in scope |
| § Council — platform (chosen option) | `docs/architecture/overview.md`, `boundaries.md` | `architecture_covered: yes` or always seed stubs before feature seal |
| § Vision | `docs/product/context.md` | update if stale |

Use templates under `references/templates/product/` and `references/templates/architecture/`. Header: link to `discovery-brief.md`.

Do not copy entire brief into repo.

## Step 3 — Reconcile

- `ecosystem.yaml` paths vs repo; `gates.behavior` command — ask user if missing.
- Profile: brief § Handoff `factory_profile_recommended` overrides CLI hint; persist to `kit.config.yaml` `factory.default_profile` if user agrees.

## ecosystem.yaml rules

- Surfaces map to existing or CP-1 paths.
- Validate against `references/ecosystem.schema.yaml`.

## Do not

- Work package markdown / `agent-approved` seal.
- Change brief frontmatter after user approved (amend via new envision revision).

## Next

`scope-triage` → `factory-routing` (copy `waived_baselines` from Handoff) → baselines or skip → `work-package`.

## Complete

`ecosystem.yaml` + layout dirs + MVO files per Handoff committed; `gate-behavior.sh` smoke attempted or waived.
