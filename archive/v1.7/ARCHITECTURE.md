# demir-kit mimarisi

Sürüm: **1.7.1** (`VERSION`). Canonical journey: `references/product-lifecycle.md`.

## Katmanlar

```
GitHub Issues (canonical iş paketi, demir-kit YAML in body)
        ↑ work-package skill (gh)
demir-kit skills (protokol, gate worker talimatları)
        ↑ task specs
Orca orchestration (Run, Task, worker-start, ask, gate-create, worker_done)
        ↑ worktree --issue, terminal, browser, emulator
Repo: ecosystem.yaml, docs/product|architecture, code
```

## Yaşam döngüsü

| Aşama | Nerede |
|-------|--------|
| Kit wire | `kit-setup` → `kit.config.yaml` |
| Envision | `kit-envision` → `discovery-brief` → `discovery-approved` |
| Scaffold | `kit-init` + `envision-handoff.md` |
| Scope & factory | `scope-triage` → `factory-routing` → baselines or `waived_baselines` |
| Mühür | `work-package` → `agent-approved` |
| Yürütme | Orca (`orca-integration.md`, `feature-flow-dag.md`) |
| İnsan QA | `gate-create` / `ask` + `human-qa` |

Plan onayı mühürde; ayrı repo WP dosyası yok.

## İletişim

`references/human-communication.md` — tüm kullanıcı ve `ask` metinleri.

## Protokol

Issue `demir_kit_version: "1"`. Şemalar: `references/factory-schema.yaml`, `work-package-issue-body.schema.yaml`.

## Fabrika

```
Fikir → kit-envision → kit-init → scope-triage → factory-routing → work-package → Orca (+ platform-gate packs)
```

`profiles/` + `references/packs/` — ürün adı bağımsız.

## Yetenekler

`references/capability-map.md` — protokol özeti.

## Plugin

Phase 2: Orca marketplace skill plugin; v1 = `vendor/demir-kit` clone + `kit.root` paths.
