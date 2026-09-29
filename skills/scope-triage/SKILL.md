---
name: scope-triage
description: >-
  Feature triage KEEP/DEFER/CUT with effort, value, ROI reasoning. User confirmation
  loop; sync defer list to evolution-roadmap. Before work-package seal on greenfield.
---

# scope-triage

VB **Feature Triager** karşılığı — çıktı issue YAML + roadmap, yüzlerce otomatik issue yok.

Apply `human-communication.md`.

## When

- After **`kit-init`** (envision complete), before mühür on `greenfield_product` / epic bootstrap
- User requests “scope sık”, “adjust scope”, re-run after `work-package-amend`

## Process

0. If `docs/product/discovery-brief.md` has § **Development bets**: import rows as draft `scope_triage.items`; only ask confirm/override — do not re-run full feasibility Q&A.
1. List candidate features (from brief bets + `discovery.must_have_features` + session notes). Include **launch/commercial** items (ASO, landing, paywall, analytics) as triage rows when relevant.
2. For each item score (1–5 stars or 1–5 int):
   - **technical** — complexity / unknowns
   - **value** — MVP criticality
   - **effort_hours** — realistic estimate (solo-adjusted)
3. Compute **decision:**
   - **keep** — MVP core (`roi` note: value/effort)
   - **defer** — Phase 2+ (`phase` label e.g. `phase-2`)
   - **cut** — out of product (`reasoning` required)
4. Present summary table in **human language**; ask confirm or override per item.
5. On **override to KEEP** a deferred item: state **impact** (extra hours, timeline slip risk) — VB pattern.

## Issue block `scope_triage`

```yaml
scope_triage:
  confirmed: true
  confirmed_at: "2026-09-29"
  items:
    - name: Daily rewards
      decision: keep
      technical: 4
      value: 5
      effort_hours: 24
      roi_note: high
      reasoning: Core retention loop
      phase: mvp
    - name: AI coach
      decision: cut
      technical: 2
      value: 1
      effort_hours: 80
      roi_note: low
      reasoning: Unproven; defer until MAU threshold
  overrides:
    - name: Web dashboard
      from: defer
      to: keep
      impact_hours: 40
      user_acknowledged: true
```

## Repo sync

- **keep** → `acceptance_criteria` / future child issues
- **defer** → `docs/architecture/evolution-roadmap.md` **Deferred** section (create from template if missing)
- **cut** → issue `out_of_scope` + roadmap “never v1”

## Feasibility coupling

Update `feasibility` on same issue:

```yaml
feasibility:
  score: 7.5
  go: true
  strengths: ["..."]
  risks:
    - text: Two-sided marketplace cold start
      mitigation: Seed one side first
```

If `score < 6` or `go: false` → coordinator `ask`: pivot, shrink scope, or waive (document in `decisions`).

## Labels

`scope-confirmed` when `scope_triage.confirmed: true`.

## Minimum output

Do not write full PRDs — MVO per `references/minimum-viable-output.md`. Triage table + roadmap bullets enough.

## Next

`factory-routing` → `architecture_baseline` (if required) → `work-package`.
