---
name: work-package
description: >-
  Seal a GitHub work package (demir-kit YAML in issue). Mandatory reference,
  tests_plan, short CP titles. Never WP markdown in repo.
---

# work-package

Apply **`human-communication.md`** to all user-facing text.

## Non-negotiables

- No `docs/work-packages/` or `WP-*.md` in repo.
- Issue body: summary + ` ```yaml demir-kit ` with **reference**, **tests_plan**, **checkpoints** (short titles).
- **`minimum-viable-output.md`** — no spec dump trees.

## Protocol phases

### −1 — Envision, ecosystem, scope

**Envision:** If no `discovery-approved` / approved brief — run **`kit-envision`** (or complete **kit-setup** Phase 2 on brownfield). Owner does not run envision as a separate habit after bootstrap.

**kit-init (autonomous):** Before seal, if brief is approved and `ecosystem.yaml` is missing or stale vs brief § Proposed ecosystem — run **`kit-init`** (`kit-init.sh` + agent per `envision-handoff.md`). **Do not** ask the owner to invoke kit-init; only escalate on failure or missing approval. **kit-build** alias documents the same rule.

If `greenfield_product` / bootstrap epic and no `scope_triage.confirmed`:

1. **`scope-triage`** or owner **kit-feature** (may reuse brief § Development bets) → `scope-confirmed`
2. If `feasibility.go: false` or score &lt; 6 → `ask` before seal

`out_of_scope` must include all **cut** items from triage.

### 0 — Factory routing

If `entry` / `factory` not set: run **`factory-routing`** first (human language).

Load `profiles/<factory.profile>.yaml`; merge `platform_packs`, `tests_plan_seeds`, suggest `checkpoints` from `checkpoint_templates[entry.kind]`.

If `entry.kind: architecture_baseline` → require `solution-architect` baseline CPs; `tests_plan` may use doc-only expectations.

If `greenfield_product` or `feature` and `factory.architecture_baseline_required` and `architecture_baseline` ∉ `factory.waived_baselines` → require `architecture.baseline_issue` and label `architecture-baseline-done` (or user `ask` waive).

If `factory.commercial_baseline_required` and `commercial_baseline` ∉ `factory.waived_baselines` → require `commercial.baseline_issue` and `commercial-baseline-done`. Waived path: brief § Handoff + `envision-handoff.md` MVO files on disk.

If `factory.pilot_mode: true` → treat as dual baseline waive only when `decisions` documents pilot; still enforce MVO for marketing/store CPs.

Set `commercial.review_policy.commercial_review` default `required` when `marketing.site` or store surfaces in scope.

`entry.kind: commercial_baseline` → CP-COM-* map to `product-strategy`, `monetization-brief`, `gtm-lite`; no feature behavior until docs done.

Default `architecture.review_policy.output_review: required` for new greenfield children; set `gates.architect: true` on implementation CPs unless waived in ADR.

Fill `factory.activated_skills` / `skipped_capabilities` per **`capability-activation.md`**.

Epic issues: optional `adaptive` block for weekly loop.

### 1 — Intent & ecosystem

Map `products` / `surfaces`; read `ecosystem.yaml`.

### 2 — Reference (spec)

Fill `reference` block (`work-package-issue-body.schema.yaml`):

- `kind`: github_paths | running_app | prototype_url | design_docs | product_issue | mixed
- `summary`: plain language
- `paths` / `states` as needed

**Referans sözleşmesi** — uzun anlatım spec yerine koda, tasarıma veya prototype’a işaret et.

### 3 — Users & acceptance

`acceptance_criteria` testable; surface tags optional.

### 4 — Boundaries & decisions

`out_of_scope`; `decisions` with `adr_required` when needed.

### 5 — Checkpoints

- **Titles: few words** — one-glance review on GitHub.
- `depends_on`, `gates`, `surfaces`, `ui_scope` when `gates.ui: true`.
- Invoke **`test-plan`** skill → complete `tests_plan` before seal.

### 6 — Review & seal

Plain summary. adjust / seal / abort.

On **seal**:

1. Issue body with full YAML (`demir_kit_version: "1"`).
2. `gh issue create` / `edit` (`tracker.repo`).
3. Labels: `agent-approved`.
4. Next steps: `health-check` then Orca (`orchestration/README.md`), `orca worktree create --issue N`.

## Modes

`extend` | `bootstrap` (epic + children) | use `work-package-amend` for amend.

## See

`examples/issue-body-sample.md`
