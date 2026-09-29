# demir-kit

**Sürüm 1.7.1** — `references/product-lifecycle.md` + `references/envision-handoff.md`. Detay: `CHANGELOG.md`.

**Fabrika:** `kit-envision` → `kit-init` → triage → routing → baselines (veya `waived_baselines`) → mühür → Orca.

- İş paketleri **yalnızca GitHub Issues** (body’de `demir-kit` YAML).
- Repo: kod + `ecosystem.yaml` + ADR/design — WP md yok.
- Yürütme: **Orca** (`orchestration`, `orca-cli`, emulator skills).

## Orca kurulumu (bir kez)

Settings → Experimental: Orchestration + Plugin system (plugin sonra).

```bash
npx skills add https://github.com/stablyai/orca --skill orchestration --global
npx skills add https://github.com/stablyai/orca --skill orca-cli --global
```

**Orca ADE:** Bu repoyu ürün içinde `vendor/demir-kit` olarak klonla; skill’ler `kit.root/skills/` üzerinden yüklenir.

**Başvuru:** `skills/kit/SKILL.md`, `references/orca-integration.md`

## Kit — ilk kurulum (ürün repo)

1. `git clone … vendor/demir-kit` (tüm repo)
2. **`kit-setup`** → `kit.config.yaml`, `AGENTS.md`, `docs/agent/workflow.md`
3. **`kit-envision`** → repo analizi, council, `docs/product/discovery-brief.md` → **`discovery-approved`**
4. **`kit-init`** → onaylı brief’ten `ecosystem.yaml` + klasörler

```bash
vendor/demir-kit/tools/kit-setup.sh --repo owner/name
# envision: Orca chat — skill kit-envision
vendor/demir-kit/tools/kit-init.sh --repo owner/name --profile web-product
```

## Kullanım (fabrika)

1. Keşif sohbeti (`user-intents.md`) veya doğrudan **`kit-envision`**.
2. **`scope-triage`** → **`factory-routing`** (envision sonrası).
3. **`work-package`** — mühür, `agent-approved`.
4. `orca worktree create --issue <N>` + coordinator (`orchestration/README.md`).
5. Human QA → `human-qa` / `done` veya `work-package-amend`.

## Klasörler (kit repoda)

| Yol | İçerik |
|-----|--------|
| `skills/kit*` | Bootstrap (`kit`, `kit-setup`, `kit-envision`, `kit-init`) |
| `tools/` | `kit-setup.sh`, `kit-init.sh` |
| `profiles/` | Fabrika profilleri |
| `references/` | Şemalar, gate-contract, packs |
| `orchestration/` | Coordinator checklist, automation |
| `templates/` | ecosystem.yaml, `kit.config.yaml`, AGENTS.md |

## Dosya ağacı

```
demir-kit/
├── VERSION
├── CHANGELOG.md
├── references/     # capability-map.md, orca-integration.md, …
├── orchestration/  # README, task-spec-template, automation-precheck-example.sh
├── profiles/
├── tools/            # kit-setup.sh, kit-init.sh (+ checkpoint-viewer opsiyonel)
├── skills/           # kit, kit-setup, kit-init, work-package, …
├── templates/
└── examples/
```

## İlkeler

- Ekosistem: `ecosystem.yaml` (oyun + web + legal).
- İş paketi: `reference` + zorunlu `tests_plan` + kısa checkpoint başlıkları.
- Gate: dual UI reviewer, dual adversarial, evidence comment (`gate-contract.md`).
- Behavior: headless CLI yönü — `behavior-cli-pattern.md`.
- Sorular: `human-communication.md`.
- Yetenekler: `references/capability-map.md`.
- Orca: `skills get orchestration --full` — coordinator yazılmaz.
