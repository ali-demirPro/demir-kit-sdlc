---
name: kit
description: >-
  demir-kit entry — kit-setup, kit-envision, kit-init (envision-handoff), then
  scope-triage → work-package → Orca. Use for kit bootstrap in product repos.
---

# Kit (demir-kit)

Protokol sürümü: `vendor/demir-kit/VERSION` (şu an **1.7.1**). Journey: **`product-lifecycle.md`**, handoff: **`envision-handoff.md`**.

## İlk kez bu ürün repoda

| Adım | Skill / araç | Ne yapar |
|------|----------------|----------|
| 0 | Sen | `vendor/demir-kit` — tüm repoyu klonla veya submodule |
| 1 | **`kit-setup`** | `kit.config.yaml`, Orca kontrolü, `docs/agent/workflow.md` |
| 2 | **`kit-envision`** | Repo analizi, vizyon soruları, council sentezi, `discovery-brief` → **`discovery-approved`** |
| 3 | **`kit-init`** | Onaylı brief’ten `ecosystem.yaml` + klasörler (önceden yazma yok) |

Sonra: `scope-triage` → `factory-routing` → baselines veya `waived_baselines` → `work-package` → Orca.

Detay: `references/product-lifecycle.md`, `references/envision-stewardship.md`.

## Kit kökü

`kit.config.yaml` → `kit.root` (varsayılan `vendor/demir-kit`). Tüm `references/`, `profiles/`, `skills/` bu kökten okunur.

## Skill grupları

| Grup | Skill’ler |
|------|-----------|
| **Kit** | `kit`, `kit-setup`, `kit-envision`, `kit-init` |
| **Keşif** | `kit-envision`, `scope-triage`, `factory-routing` (`discovery-intake` legacy) |
| **Commercial** | `product-strategy`, `monetization-brief`, `gtm-lite`, `commercial-review` |
| **Mimari** | `solution-architect` |
| **Paket** | `work-package`, `work-package-amend`, `test-plan`, `checkpoint-planner` |
| **Gate** | `behavior-gate`, `ui-gate`, `adversarial-review`, `platform-gate`, `health-check` |
| **Diğer** | `design-md`, `prototype`, `ecosystem-bootstrap`, `learnings` |

Eski ad `demir-kit` skill = bu dosyaya yönlendirme; Orca’da `skills/kit` yeterli.

## Shell (opsiyonel)

```bash
export KIT_ROOT="$(pwd)/vendor/demir-kit"
"$KIT_ROOT/tools/kit-setup.sh" --repo owner/name
"$KIT_ROOT/tools/kit-init.sh" --repo owner/name --profile game-flutter
```

## Referans

- `references/kit-bootstrap-layout.md`
- `references/capability-map.md`
- `templates/project/kit.config.yaml`
