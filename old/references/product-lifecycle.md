# Product lifecycle (canonical)

Sürüm: demir-kit **1.7.3**. **Tek referans** — stewardship dosyaları buraya uyumlu olmalı. Handoff: **`envision-handoff.md`**. Agent hard blocks: **`agent-phase-gates.md`**.

Issue protokol: `demir_kit_version: "1"`. Kit sürümü: `vendor/demir-kit/VERSION`.

## State (single source)

| State | Where | Label / marker |
|-------|--------|----------------|
| Kit wired | `kit.config.yaml` | — |
| Envision draft | `docs/product/discovery-brief.md` `envision.status: draft` | `envision-draft` |
| Direction locked | brief frontmatter `envision.status: approved` | **`discovery-approved`** |
| Ecosystem live | `ecosystem.yaml` | after `kit-init` |
| Scope locked | issue `scope_triage.confirmed` | `scope-confirmed` |
| Executable work | issue YAML sealed | **`agent-approved`** |

**Deprecated:** `discovery-done` → use `discovery-approved` only.

Tracking issue (recommended): one **product_envision** or **Envision** issue linking brief; optional `envision` YAML on issue mirrors brief frontmatter.

## Phase map

```
PHASE 0  kit-setup
PHASE 1  kit-envision  → discovery-approved
PHASE 2  kit-init      → ecosystem.yaml + folders (from brief § Proposed ecosystem)
PHASE 3  scope-triage  → scope-confirmed (merge brief § Development bets; skip duplicate Q&A)
PHASE 4  factory-routing
PHASE 5  baselines     → optional / waived (see below)
PHASE 6  work-package  → agent-approved
PHASE 7  Orca CP+gates → human-qa → done
```

### Brownfield (existing repo)

Skip full envision only with `decisions` + user `ask` waive. Default: **`kit-envision` brownfield mode** (short questionnaire + lite brief). Still use `discovery-approved` before changing `ecosystem.yaml`.

### Pilot / thin path

`factory.pilot_mode: true` on issue → may set `waived_baselines` for both commercial and architecture with `decisions` rationale; still require **`discovery-approved`** unless explicit envision waive. See `envision-handoff.md`.

### Greenfield envision gate

Default: required. Opt-out only via issue `decisions` + coordinator `ask`, or `kit-init.sh --waive-envision` (emergency). Optional `kit.config.yaml` → `product.envision_required: false` for brownfield-only repos (document why).

## Envision vs baselines (dedup)

If **`discovery-brief`** already contains council sections (positioning, GTM, monetization sketch, architecture options, proposed ecosystem):

Set on greenfield parent at seal (from brief § Handoff — **`commercial_covered: yes`** ⇒ waive):

```yaml
factory:
  waived_baselines:
    - commercial_baseline
envision:
  baselines_covered:
    commercial: true
    architecture: false
```

Terminology table: `envision-handoff.md`.

`health-check` / `work-package`: if `waived_baselines` includes `commercial_baseline`, do **not** require `commercial-baseline-done` or duplicate epic; require brief § Council — commercial + `docs/product/positioning.md` if split files promised in handoff.

If architecture **not** waived: run `architecture_baseline` epic after `kit-init` (docs under `docs/architecture/`).

## Skills by phase

| Phase | Skills |
|-------|--------|
| 0 | `kit-setup` |
| 1 | `kit-envision` (includes intake logic; **do not** standalone `discovery-intake` on greenfield) |
| 2 | `kit-init` (`materialize` from brief) |
| 3 | `scope-triage` |
| 4 | `factory-routing` |
| 5 | `solution-architect` baseline, `product-strategy`/`gtm-lite` only if baseline **not** waived |
| 6 | `work-package`, `test-plan` |
| 7 | `health-check`, gates, `learnings` |

## Orca run types

| Objective | When |
|-----------|------|
| `kit-envision <repo>` | Phase 1 — packaging, no `agent-approved` |
| `demir-kit issue #N` | Phase 7 — `agent-approved` only |

See `orchestration/packaging-run-prompt.md`, `templates/orchestration/automation-prompt.md`.

## Waive policy

| Waive | How |
|-------|-----|
| Envision | `decisions` on issue + coordinator `ask`; or `kit-init.sh --waive-envision` (emergency only) |
| Baseline epic | `factory.waived_baselines` + brief § Handoff |
| health-check blocker | user `ask` only |

## Research minimum (envision)

Brief must include § **Competitors / alternatives** (≥2 named or category) and § **Legal / compliance hooks** (even if “none identified”).
