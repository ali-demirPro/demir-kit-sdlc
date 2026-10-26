---
name: demir-kit
description: >-
  Alias for kit — use skills/kit/SKILL.md. demir-kit workflow, kit-setup, kit-init,
  work packages, Orca gates.
---

# demir-kit

> **Giriş noktası:** `skills/kit/SKILL.md` — **`kit-setup`** → **`kit-envision`** → **`kit-init`** (`envision-handoff.md`), sonra fabrika. Canonical: `product-lifecycle.md`.

## Stack

| Layer | Tool |
|-------|------|
| Work package | GitHub Issues + `work-package` skill |
| Ecosystem map | `ecosystem.yaml` in repo |
| Execution | **Orca** `orchestration` + `orca-cli` (+ emulator skills for mobile) |
| Human questions | `human-communication.md` + `orchestration ask` |

## Journey

0. Klon `vendor/demir-kit` → **`kit-setup`** → **`kit-envision`** → label **`discovery-approved`** → **`kit-init`**.
1. Discovery chat (free) — `references/user-intents.md`.
2. **`scope-triage`** (reuse brief § Development bets) → **`factory-routing`**.
3. Baselines: `commercial_baseline` / `architecture_baseline` **or** `factory.waived_baselines` when envision brief already covered (Handoff §).
4. **`work-package`** → `agent-approved`.
5. Orca: `orchestration/README.md` + `templates/orchestration/automation-prompt.md`.
6. QA: `human-qa` → `done` or `work-package-amend`.

## Skills (demir-kit)

| Skill | Role |
|-------|------|
| `kit` | Giriş + skill haritası |
| `kit-setup` | `kit.config.yaml`, Orca ADE wiring |
| `kit-envision` | Discovery brief, council, `discovery-approved` |
| `kit-init` | Onaylı brief → `ecosystem.yaml`, klasörler |
| `discovery-intake` | Legacy / brownfield kısa bağlam (`kit-envision` içinde tercih) |
| `scope-triage` | KEEP/DEFER/CUT, ROI, onay döngüsü |
| `factory-routing` | Profil + entry.kind + quality_tier |
| `product-strategy` | ICP, positioning, MVP vaadi |
| `monetization-brief` | Gelir modeli, fiyat hipotezi (canlı fiyat insan) |
| `gtm-lite` | Kanallar, launch slice, ASO outline |
| `commercial-review` | Landing / store / app mesaj uyumu gate |
| `solution-architect` | Mimari kararlar, tier/cost, output-review, refactor yönlendirme |
| `work-package` | Mühür + reference + tests_plan + factory block |
| `platform-gate` | Pack checklist (HIG, a11y, ASC, …) |
| `test-plan` | Zorunlu test planı |
| `health-check` | Run öncesi |
| `design-md` | UI öncesi design doc |
| `behavior-gate` / `ui-gate` / `adversarial-review` | Gates |
| `work-package-amend` | Scope değişimi |

## References

- `references/orca-integration.md`
- `references/human-communication.md`
- `references/feature-flow-dag.md`
- `references/gate-contract.md`
- `references/behavior-cli-pattern.md`
- `references/evidence-comment-template.md`
- `references/stop-and-done-policy.md`
- `references/capability-map.md`
- `references/architecture-stewardship.md`
- `references/commercial-stewardship.md`
- `references/envision-stewardship.md`
- `examples/product-envision-issue-sample.md`
- `references/templates/product/`
- `examples/commercial-baseline-issue-sample.md`
- `references/templates/architecture/`
- `examples/architecture-baseline-issue-sample.md`
- `examples/greenfield-discovery-sample.md`
- `references/minimum-viable-output.md`
- `references/coordinator-blockers.md`
- `references/capability-activation.md`
- `references/user-intents.md`
- `orchestration/weekly-adaptive-loop.md`
- `references/factory-schema.yaml`
- `profiles/README.md`
- `references/packs/README.md`
- `references/tracker-policy.md`
- `examples/issue-body-sample.md`

## Orca skills to install (official, not demir-kit)

```text
npx skills add https://github.com/stablyai/orca --skill orchestration --global
npx skills add https://github.com/stablyai/orca --skill orca-cli --global
```

Mobile UI gates: `orca-emulator`, `orca-emulator-android`.
