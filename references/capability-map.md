# demir-kit yetenek haritası

Sürüm: **1.7.1** (`VERSION`). Journey: `product-lifecycle.md`, handoff: `envision-handoff.md`. Protokol: `demir_kit_version: "1"`.

## Kit bootstrap

| Yetenek | Nerede |
|---------|--------|
| Giriş | `skills/kit/SKILL.md` |
| Repoya bağlama | `kit-setup` + `tools/kit-setup.sh` |
| **Envision (partner discovery)** | `kit-envision` + `envision-stewardship.md` + `discovery-brief.md` |
| ecosystem + klasörler | `kit-init` + `envision-handoff.md` |
| Soru seti | `envision-questionnaire.md`, `envision-questionnaire-brownfield.md` |
| Layout | `kit-bootstrap-layout.md`, `kit.config.yaml` şablonu |

## Commercial & growth

| Yetenek | Nerede |
|---------|--------|
| Positioning / ICP | `product-strategy` + `docs/product/positioning.md` |
| Monetization | `monetization-brief` |
| GTM / ASO lite | `gtm-lite` |
| Mesaj uyumu gate | `commercial-review` + `gates.commercial` |
| Launch checklist | pack `launch-readiness` |
| Baseline epic | `entry.kind: commercial_baseline` |
| Süreklilik | `commercial-stewardship.md` |

## Keşif & kapsam (VB Navigator)

| Yetenek | Nerede |
|---------|--------|
| Ürün bağlamı | `kit-envision` + `discovery-brief` + `docs/product/context.md` |
| Feasibility + triage | `scope-triage` + issue `feasibility`, `scope_triage` |
| MVO (doc disiplini) | `minimum-viable-output.md` |
| Selective skills | `capability-activation.md` + `factory.activated_skills` |
| Kullanıcı tetikleri | `user-intents.md` |
| Haftalık ritim | `orchestration/weekly-adaptive-loop.md` + `learnings` |
| Blocker kuralları | `coordinator-blockers.md` |

## Mimari (solution architect)

| Yetenek | Nerede |
|---------|--------|
| Karar, tier/cost, roadmap | `solution-architect` skill |
| Süreklilik | `architecture-stewardship.md` |
| Artifact şablonları | `references/templates/architecture/` |
| Baseline entry | `entry.kind: architecture_baseline` |
| Output gate | `gates.architect` + `gate-contract.md` |

## Fabrika

| Yetenek | Nerede |
|---------|--------|
| Fikir sınıflandırma | `factory-routing` skill |
| Profiller | `profiles/*.yaml` |
| Platform pack'ler | `references/packs/` + `platform-gate` |
| Issue kaydı | `entry` + `factory` YAML (`factory-schema.yaml`) |
| Ops yüzeyleri | `ecosystem.yaml` → `products.ops` |

## İş paketi

| Yetenek | Nerede |
|---------|--------|
| Keşif → mühür | `work-package` (+ önce `factory-routing`) |
| Canonical kayıt | GitHub issue |
| Referans sözleşmesi | `reference` |
| Test planı | `tests_plan` |
| Scope değişimi | `work-package-amend` |

## Yürütme (Orca)

| Yetenek | Nerede |
|---------|--------|
| Run / Task / worker | `orca-integration.md`, `feature-flow-dag.md` |
| Run öncesi | `health-check` |
| Kuyruk | `automation-precheck-example.sh` |

## Kalite kapıları (core)

Davranış → architect → **commercial** (opsiyonel) → UI → adversarial → platform (incl. **launch-readiness**) → insan.

Detay: `gate-contract.md`, `stop-and-done-policy.md`, `evidence-comment-template.md`.

## Ürün boşlukları

- Ürün-specific agent CLI: `behavior-cli-pattern.md`
- ASC/Play secret'ları: kullanıcı ortamı, repo'da değil
