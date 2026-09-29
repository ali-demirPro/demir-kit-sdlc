# Changelog

## 1.7.2 — 2026-09-29

- **`kit-upgrade`** owner skill + `tools/kit-upgrade.sh` — sync vendored kit from `kit.upstream.local` / `git`
- Orca owner set includes `kit-upgrade`; template `scripts/kit-upgrade.sh` wrapper
- Root `install.sh` (+ `templates/project/install.sh`) for Orca owner skills; README 1.7.2

## 1.7.1 — 2026-09-29

- **`envision-handoff.md`** — terminology (`*_covered: yes` ⇒ waive), MVO promote matrix, tracking sync, `pilot_mode`
- `kit-init.sh` — frontmatter `envision.status` check, layout dir materialize, `default_profile` from `kit.config.yaml`
- `kit-init` skill — agent promote step; brownfield questionnaire file
- Hub sync: `ARCHITECTURE.md`, `orca-integration.md`, `feature-flow-dag.md`, `capability-activation`, examples, launch-readiness
- `solution-architect` + commercial skills read approved brief / handoff
- `kit.config.yaml` → `product.envision_required`; discovery-intake marked internal-only

## 1.7.0 — 2026-09-29

- **Canonical lifecycle:** `references/product-lifecycle.md` — single journey, state labels, baseline dedup
- `factory.waived_baselines`, `factory.pilot_mode`, `envision.baselines_covered` in factory-schema
- Stewardship + README + `kit` / `demir-kit` skills aligned to envision → init → triage flow
- `discovery-intake` = sub-step / brownfield only; **`discovery-done` deprecated** → `discovery-approved`
- `kit-init.sh` extracts § Proposed ecosystem YAML from approved brief
- Orca: `orchestration/packaging-run-prompt.md`, updated `automation-prompt.md` (gates, kit.root, envision checks)
- Discovery brief template: competitors, legal, handoff waivers

## 1.6.0 — 2026-09-29

- **`kit-envision`** — repo scan, vision Q&A, council synthesis, `discovery-brief`, `discovery-approved` before `kit-init`
- `references/envision-stewardship.md`, `envision-questionnaire.md`, discovery-brief template
- `entry.kind: product_envision`, issue `envision` block
- Labels: `envision-draft`, `discovery-approved`
- `kit-init` requires approved brief; `kit-init.sh` checks (or `--waive-envision`)

## 1.5.0 — 2026-09-29

- **Kit bootstrap:** `kit`, `kit-setup`, `kit-init` skills
- `kit.config.yaml`, `templates/project/AGENTS.md`, `references/kit-bootstrap-layout.md`
- Shell: `tools/kit-setup.sh`, `tools/kit-init.sh`, `tools/README.md`
- Orca ADE: skill paths from `kit.root` (vendor clone), not per-IDE copies
- `demir-kit` skill → points to `kit` entry

## 1.4.0 — 2026-09-29

- **Commercial / growth layer:** `product-strategy`, `monetization-brief`, `gtm-lite`, `commercial-review` skills
- `entry.kind: commercial_baseline`, issue `commercial` block, `factory.commercial_baseline_required`
- Gate `gates.commercial`, pack `launch-readiness`
- `commercial-stewardship.md`, product doc templates (positioning, monetization, gtm, analytics)
- Profiller: commercial baseline CP şablonları, launch-readiness pack
- Örnek: `examples/commercial-baseline-issue-sample.md`

## 1.3.0 — 2026-09-29

- **VB Navigator katmanı:** `discovery-intake`, `scope-triage` skills
- Issue YAML: `discovery`, `feasibility`, `scope_triage`, `adaptive`
- `factory.activated_skills`, `factory.skipped_capabilities` (selective council)
- `minimum-viable-output.md`, `capability-activation.md`, `coordinator-blockers.md`, `user-intents.md`
- `orchestration/weekly-adaptive-loop.md`, `templates/product/context.md`
- Labels: `discovery-done`, `scope-confirmed`, `feasibility-hold`, …
- Örnek: `examples/greenfield-discovery-sample.md`
- Profiller: discovery/triage in pipeline; game-flutter / apple optional_capabilities

## 1.2.0 — 2026-09-29

- **`solution-architect` skill** — baseline, decision, output-review, refactor-proposal, tier-review
- **`entry.kind: architecture_baseline`** — greenfield öncesi mimari epic
- Issue **`architecture`** bloğu + `factory.architecture_baseline_required`
- Gate **`architect`** (`gates.architect`) — behavior sonrası, ui öncesi
- `architecture-stewardship.md`, `references/templates/architecture/*`
- Profiller: baseline CP şablonları, greenfield CP’lerde `architect: true`
- Örnek: `examples/architecture-baseline-issue-sample.md`

## 1.1.0 — 2026-09-29

- **Fabrika katmanı:** `entry`, `factory` issue alanları, `profiles/`, `factory-routing`, `platform-gate`
- Platform pack referansları (`references/packs/`)
- `ecosystem.yaml` şeması: `ops.store`, `ops.ci` yüzey tipleri
- Örnek profiller: iOS excellence, Flutter, web, game, store release

## 1.0.0 — 2026-09-29

İlk sürüm — iş paketi, kalite kapıları, Orca entegrasyonu, `capability-map.md`.
