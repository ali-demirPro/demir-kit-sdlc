# Epic closure (ponytail önleme)

Tüm leaf'ler bitince **zorunlu**. Bu rapor `status: pass` olmadan epic
**`epic-done` olmaz**. Şema: [closure.schema.json](../schemas/closure.schema.json).

## Kim

| Adım | Roller |
|------|--------|
| Kapsam mutabakatı | analist + orchestrator |
| Teknik gap | architect + tester |
| Yanlış / gereksiz iş | adversarial mantığı (tester veya review CP) |
| Rapor + metrik | documenter |
| İnsan | epic kabulü → `epic-done` |

## 1 — Kapsam mutabakatı (analist)

- [ ] Epic KEEP listesi ↔ tüm child issue'lar
- [ ] Her child: `leaf-done` **veya** `deferred` + defer issue linki
- [ ] Orphan: kapanmış iş scope'ta yok mu?
- [ ] Zombie: `intake` / açık leaf unutulmuş mu?

Fail → `epic-reconcile` issue aç veya eksik child'ları listele.

## 2 — Gap analizi (architect + tester)

- [ ] Her leaf: `doctor.sh --issue N` 0 hata + evidence `pass`
- [ ] `depends_on` ihlali yok
- [ ] Epic amacı dışı dosya/PR kapsamı

## 3 — Gereksiz iş

- [ ] Duplicate iş
- [ ] Path routing dışı agent çalışmış mı?
- [ ] Revert / temizlik önerisi

## 4 — Rapor

Epic comment'ine `demir-kit-closure` bloğu post et:

````markdown
```yaml
demir-kit-closure
demir_kit_version: "2"
epic: 1
status: pass
gaps: []
unnecessary: []
deferred: []
metrics:
  leaf_count: 5
  cp_count: 5
  gate_retries: 0
  reconcile_issues: 0
  human_interventions: 0
  lead_time_hours: 2.5
ready_for_human_qa: true
```
````

- `status: fail` → `epic-reconcile` + yeni issue; **epic-done yasak**.
- Metrik tanımları ve retro: [metrics/README.md](../metrics/README.md).
- Doğrulama: `doctor.sh --issue <epic>` closure bloğunu (issue body veya comment)
  şemaya göre denetler. `epic-done` öncesi çalıştır.

## 5 — İnsan kabulü

[policies/human-qa-done.md](../policies/human-qa-done.md) epic bölümü → label
**`epic-done`**.

## Kurallar

- Agent "epic bitti" demez; yalnızca closure `pass`/`fail`.
- Closure atlanamaz; insan sorma yalnız kabul adımında.
