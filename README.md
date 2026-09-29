# demir-kit

**Sürüm 1.7.2** — `references/product-lifecycle.md` + `references/envision-handoff.md`. Detay: `CHANGELOG.md`.

**Fabrika:** `kit-envision` → `kit-init` → triage → routing → baselines (veya `waived_baselines`) → mühür → Orca.

- İş paketleri **yalnızca GitHub Issues** (body’de `demir-kit` YAML).
- Repo: kod + `ecosystem.yaml` + ADR/design — WP md yok.
- Yürütme: **Orca** (`orchestration`, `orca-cli`).

## Orca kurulumu

Settings → Experimental: Orchestration + Plugin system (plugin sonra).

### Platform (bir kez, makine geneli)

```bash
./install.sh --with-platform
# veya elle:
npx skills add https://github.com/stablyai/orca --skill orchestration --global
npx skills add https://github.com/stablyai/orca --skill orca-cli --global
```

### Owner komutları (ürün sahibi)

Ürün repoda vendored kit (`demir-kit/` veya `vendor/demir-kit/`):

```bash
./install.sh
```

Sadece kit repoda çalışıyorsan (bu repo):

```bash
./install.sh
```

Kurulan owner skill’ler: **kit-feature**, **kit-build**, **kit-build-change**, **kit-upgrade**.  
Internal gate/architect skill’leri Orca’ya **kurma** — coordinator `${kit.root}/skills/<ad>/SKILL.md` okur.

Doğrula: `orca skills installed`

**Başvuru:** `skills/kit/SKILL.md`, `references/orca-integration.md`

## Kit — ürün repoya bağlama

1. Kit’i ürün içine koy: `demir-kit/` (veya `vendor/demir-kit/`) — clone veya `kit-upgrade`.
2. **`kit-setup`** → `kit.config.yaml`, `AGENTS.md`, `docs/agent/workflow.md`, envision (brownfield).
3. **`kit-init`** → onaylı brief’ten `ecosystem.yaml` (genelde ilk **kit-build** ile otomatik).

```bash
demir-kit/tools/kit-setup.sh --repo owner/name
# Owner: kit-envision / kit-setup Phase 2 → discovery-approved
# kit-init: agent on first kit-build unless manual
```

`kit.config.yaml` örneği: `templates/project/kit.config.yaml` (`kit.upstream` + `kit-upgrade`).

## Owner komutları (günlük)

| Komut | Açıklama |
|-------|----------|
| **kit-feature** | Scope KEEP / DEFER / CUT → `scope-triage` |
| **kit-build** | Issue mühür → `work-package` (+ otomatik `kit-init` gerekirse) |
| **kit-build-change** | Mühürlü paket amend |
| **kit-upgrade** | Vendored kit sync → `tools/kit-upgrade.sh` |

## Kullanım (fabrika)

1. **`scope-triage`** / **kit-feature** → **`factory-routing`**.
2. **`work-package`** / **kit-build** — mühür, `agent-approved`.
3. `orca worktree create --issue <N>` + coordinator (`orchestration/README.md`).
4. Human QA → `human-qa` / `done` veya `work-package-amend`.

## Klasörler

| Yol | İçerik |
|-----|--------|
| `install.sh` | Orca owner skill kurulumu (kit checkout) |
| `skills/kit*` | Bootstrap, owner alias’lar, gates (internal) |
| `tools/` | `kit-setup.sh`, `kit-init.sh`, `kit-upgrade.sh` |
| `profiles/` | Fabrika profilleri |
| `references/` | Şemalar, gate-contract, packs |
| `orchestration/` | Coordinator checklist, automation |
| `templates/project/` | `kit.config.yaml`, `install.sh`, `scripts/` |

## Dosya ağacı (özet)

```
demir-kit/
├── VERSION
├── install.sh
├── CHANGELOG.md
├── references/
├── orchestration/
├── profiles/
├── tools/
├── skills/
├── templates/
└── examples/
```

## İlkeler

- Ekosistem: `ecosystem.yaml`.
- İş paketi: `reference` + `tests_plan` + checkpoint başlıkları.
- Gate: dual UI, adversarial, evidence comment (`gate-contract.md`).
- Sorular: `human-communication.md`.
- Orca: `skills get orchestration --full` — coordinator yazılmaz.
