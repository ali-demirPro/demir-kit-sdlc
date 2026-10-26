---
name: kit-envision
description: >-
  Deep discovery before kit-init — repo analysis, vision Q&A, council synthesis
  (architect, commercial, strategy), platform alternatives, discovery-brief for
  human approval. No ecosystem commit until discovery-approved.
---

# kit-envision

**Partner mode:** analiz + tartışma + öneri → onay → sonra `kit-init` dosya yazır.

Apply `human-communication.md` for all user messages. Do not dump YAML jargon in questions.

**Önkoşul:** `kit-setup` done. **Sonraki:** user label `discovery-approved` → **`kit-init`** (approved snapshot only).

**Brownfield:** same skill, shorter Phase 2 (lite questionnaire), still produce brief + `discovery-approved` before ecosystem changes. Full waive only via issue `decisions` + coordinator `ask` (not `kit-init.sh --waive-envision` by default).

Orca packaging: `orchestration/packaging-run-prompt.md`.

## Phase 1 — Repo analysis (automatic)

Read without asking permission (product repo root):

| Signal | Where |
|--------|--------|
| Stack | `package.json`, `pubspec.yaml`, `Package.swift`, `Cargo.toml`, … |
| App shape | `src/`, `app/`, `lib/`, routes, main features from README/docs |
| Existing docs | `docs/*`, `DESIGN.md`, `PRODUCT.md`, `blueprint.md` |
| Hosting / BaaS | `firebase.json`, `apphosting.yaml`, `vercel.json`, `.env.example` |
| Tests / CI | `scripts/`, `.github/workflows`, test scripts |
| Git | recent focus (optional `git log -5 --oneline` if allowed) |

Write **§ Repo snapshot** into draft brief (bullet facts, no fluff).

## Phase 2 — Vision questions (human)

Batch 1 (max 2 messages, options where possible). Greenfield: `references/envision-questionnaire.md`. Brownfield: `references/envision-questionnaire-brownfield.md`.

Minimum before synthesis:

- Amaç / 12 ay başarı
- Kim için (ICP)
- Platform niyeti (web, mobil, ikisi, emin değilim)
- Nasıl pazarlanacak (kanal hipotezi)
- Bu mimaride devam mı, büyük değişiklik toleransı
- Zaman + bütçe bandı + solo/takım

User answers → update `docs/product/context.md` sections + brief § Vision.

## Phase 3 — Council (parallel analysis, one author)

Produce **debate sections** in the brief (not separate 40-page docs). Invoke logic of:

| Layer | Skill reference | Brief section |
|-------|-----------------|---------------|
| Strategy | `product-strategy` | § Positioning & MVP promise |
| Architect | `solution-architect` `decision` | § Platform & architecture options |
| Commercial | `gtm-lite` + `monetization-brief` | § Go-to-market & revenue sketch |
| Feasibility | `scope-triage` preview | § Risks & feasibility (score 1–10) |
| Privacy / legal | (checklist) | § Legal / compliance hooks |

**Architect must** compare at least **two** paths (e.g. stay Next.js web vs React Native/Flutter mobile vs PWA). State recommendation **and** dissent (“mobile better for X because…; cost…”). User may override in Phase 5.

**Commercial must** challenge platform if channels favor app store or SEO web.

Do **not** commit `ecosystem.yaml` in this phase — only **§ Proposed ecosystem** (YAML block inside brief).

## Phase 4 — Shaping

- **§ Proposed folder layout** (tree or deltas from current repo)
- **§ Development bets** — 2–4 phased ideas (name, value, effort band, phase)
- **§ Recommended factory profile** (`web-product`, `flutter-platform`, …)
- **§ Competitors / alternatives** and **§ Legal / compliance hooks** (required)
- **§ Handoff to SDLC** — `commercial_covered` / `architecture_covered` (`yes` ⇒ waive epic); see `envision-handoff.md`
- Seed `scope_triage` via § Development bets — confirm in Phase 5 (scope-triage reuses, does not duplicate)

## Phase 5 — Present & revise

Post summary in **human language** + link to `docs/product/discovery-brief.md`.

Ask: *“Bu yönde onaylıyor musun, yoksa platform / faz / kapsam değişsin mi?”*

Revise brief until user confirms.

On confirm:

1. Set brief frontmatter `envision.status: approved`, `envision.approved_at`, `envision.baselines_covered` matching Handoff.
2. Commit brief (frontmatter is source of truth).
3. GitHub tracking issue (`entry.kind: product_envision`): sync body `envision:` block to frontmatter; label **`discovery-approved`**; remove **`envision-draft`**.

## Phase 6 — Handoff

Tell user: run **`kit-init`** (`kit-init.sh` + agent steps in `envision-handoff.md`).

Then: `scope-triage` (confirm bets) → `factory-routing` → baselines or waived → `work-package`.

## Do not

- `agent-approved` on envision issue (not executable work package).
- Write `ecosystem.yaml` to repo root before `discovery-approved`.
- Skip platform alternative when user said “emin değilim”.

## Tracking issue (optional YAML)

```yaml
envision:
  status: approved
  brief_path: docs/product/discovery-brief.md
  platform_decision: web_continue | mobile_pivot | hybrid | unchanged
  factory_profile_recommended: web-product
```

## Complete

`discovery-approved` + approved brief committed. Ready for `kit-init`.
