# demir-kit

**2.26.1** — Delivery-first agent system. Runtime `delivery/`; v1 arşivi `archive/v1.7/`.

## Yapı

| Klasör | Açıklama |
|--------|----------|
| `delivery/` | Sözleşme, protokol, roller, şemalar, scriptler |
| `skills/` | v2 yürütme skill'leri |
| `discovery/` | Sonraki faz agent’ı (`growth/plan`); kurulmaz/satılmaz |
| v1 arşivi: `archive/v1.7/` | Legacy 1.x — runtime referansı üretilmez |

## Delivery (özet)

1. Epic + children → **scope triage** (`scope-confirmed`).
2. **Orchestrator** path seçer (`delivery/registry.yaml`).
3. Leaf **seal** → `agent-approved` → health-check → Orca.
4. Her CP: behavior + review + **evidence**.
5. `low`/`medium` leaf otomatik; `high`/`critical` insan QA.
6. Tüm leaf'ler → **closure** → epic kabulü → `epic-done`.

Closure metrikleri: `delivery/metrics/README.md`.

## Komutlar

```bash
./delivery/scripts/doctor.sh             # sözleşme denetimi
./delivery/scripts/doctor.sh --issue 12  # seal + evidence
./delivery/scripts/next-leaf.sh --claim  # sıradaki leaf
./delivery/scripts/guard.sh --issue 12   # kaynak kapısı + risk
```

## Başlangıç

- Sözleşme: `delivery/CONTRACT.md`
- Akış: `delivery/FLOW.md`
- Yürütme: `delivery/protocol/execution.md`

## Kurulum

```bash
./install.sh --with-platform   # Orca skill'leri + v2 skills/
./install.sh --legacy          # geçiş: v1 arşivinden kur
```
