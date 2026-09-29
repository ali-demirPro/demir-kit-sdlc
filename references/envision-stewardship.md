# Envision stewardship

Sürüm: demir-kit **1.7.1**. Skill: **`kit-envision`**. Canonical journey: **`product-lifecycle.md`**. Materialize: **`envision-handoff.md`**.

## Purpose

Strateji ve ortak akıl **dosya mühüründen önce**. Council sentezi; mekanik `kit-init` sonra.

## Flow

```
kit-setup
  → kit-envision (draft brief, council, revise)
  → human: discovery-approved (brief frontmatter + tracking issue sync)
  → kit-init (shell + agent promote per envision-handoff.md)
  → scope-triage (confirm § Development bets) → factory-routing → baselines or waived_baselines → work-package → Orca
```

## Artifacts

| File | When |
|------|------|
| `docs/product/context.md` | Phase 2–3 (living summary) |
| `docs/product/discovery-brief.md` | Phase 3–5 (canonical proposal; frontmatter = source of truth) |
| MVO splits | `kit-init` agent step when Handoff / waive |

Brief template: `references/templates/product/discovery-brief.md`.

## Labels

| Label | Meaning |
|-------|---------|
| `envision-draft` | Brief in progress |
| `discovery-approved` | Human locked direction; `kit-init` allowed |
| `discovery-done` | **Deprecated** — use `discovery-approved` only |

## Gates

| Action | Blocked without `discovery-approved` |
|--------|--------------------------------------|
| `kit-init` writing `ecosystem.yaml` | Yes (waive via `decisions` on issue or `--waive-envision`) |
| `agent-approved` greenfield epic | Recommended yes |
| `ecosystem_amend` material yaml change | Recommended yes (brownfield lite envision OK) |
| Orca execute on product CP | No (issue-level) |

## Council rules

- One **discovery-brief**, many sections — not spec dump trees.
- Architect and commercial **may disagree** in brief; synthesis states recommendation + override path.
- User override → revise brief → re-approve.

## vs discovery-intake

`discovery-intake` = internal Q&A only. **`kit-envision`** orchestrates intake + council + brief + approval. Greenfield: **kit-envision** only.

## vs baselines

Handoff `commercial_covered: yes` / `architecture_covered: yes` → `factory.waived_baselines` at seal. See **`envision-handoff.md`** terminology table.
