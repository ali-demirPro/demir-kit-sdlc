# Minimum Viable Output (MVO)

Venture-style **doc sprawl** yasak; demir-kit canonical kayıt **GitHub issue YAML** + **ince repo artifact** seti.

## Principles

1. **No duplicate specs** — uzun PRD repo’da yok; `intent` + `acceptance_criteria` + `reference.paths` yeterli.
2. **Selective skills** — `factory.activated_skills` / `skipped_capabilities`; gereksiz council persona üretme.
3. **Triage before seal** — `scope-triage` KEEP/DEFER/CUT onaylı olmadan greenfield `agent-approved` önerilmez (waive → `decisions`).
4. **Architecture thin set** — `docs/architecture/*` şablonları; 40 dosya spec klasörü yok.
5. **Progress on tracker** — % ve blocker GitHub issue/Project; chat’te ASCII Gantt zorunlu değil (opsiyonel comment).

## Allowed repo docs

| Path | Owner skill |
|------|-------------|
| `docs/product/discovery-brief.md` | kit-envision (before ecosystem commit) |
| `docs/product/context.md` | kit-envision |
| `docs/product/positioning.md` | product-strategy |
| `docs/product/monetization-brief.md` | monetization-brief |
| `docs/product/gtm-lite.md` | gtm-lite |
| `docs/product/analytics-growth.md` | gtm-lite / commercial baseline |
| `docs/architecture/*` | solution-architect |
| `docs/design/*.md` | design-md (UI CP only) |
| `docs/agent/learnings.md` | learnings (one-liners + links) |

## Forbidden

- `docs/work-packages/`, `WP-*.md`
- `00_NAVIGATOR/`, `01_SPECS/` dump trees
- Linear/Notion export as canonical (GitHub issue wins)

## When to add a doc

| Need | Action |
|------|--------|
| User journey | `reference` + design-md; not 20-page PRD |
| GTM / pricing | `commercial_baseline` **or** brief promote (`envision-handoff.md`) → `gtm-lite.md` + `monetization-brief.md` |
| Compliance | ADR + pack; THE SHIELD = platform pack + human |

## work-package enforcement

- CP titles: few words
- `tests_plan` every behavior CP
- `out_of_scope` lists CUT items from `scope_triage`

## scope-triage / kit-feature enforcement

- Parent epic: **`scope_triage` (+ optional `feasibility`) only** — see `agent-phase-gates.md`
- **No** `checkpoints` / `tests_plan` on parent during kit-feature
- Child issues: markdown + `intake` until **kit-build** on that child
