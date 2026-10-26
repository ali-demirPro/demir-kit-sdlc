# Delivery metrics

Closure raporu altı metriği **zorunlu** kılar
([closure.schema.json](../schemas/closure.schema.json)). Documenter closure
comment'inde doldurur; epic kabulünde insan görür.

| Metrik | Anlam | Nasıl |
|--------|-------|-------|
| `leaf_count` | Kapsamdaki leaf sayısı | `scope_triage.keep` |
| `cp_count` | Yürütülen CP sayısı | Seal'lerdeki `checkpoints` |
| `gate_retries` | Gate tekrar sayısı | Ekstra behavior/review turları |
| `reconcile_issues` | Closure sonrası açılan düzeltme issue | `epic-reconcile` |
| `human_interventions` | İnsan kapısı sayısı | `human-qa` + `ask` kararları |
| `lead_time_hours` | İlk `agent-approved` → son `leaf-done` | Issue zaman damgaları |

## Toplama

- Kaynak: GitHub issue etiket zamanları + evidence comment'leri.
- Sadece closure'da toplanır; ayrı metrik dosyası commit edilmez.
- `leaf_count` ve `cp_count` sıfır olamaz; `ready_for_human_qa: true` yalnız
  `status: pass` ile.

## Aylık retro

1. Son 1–3 epicin metriklerini karşılaştır.
2. Şu soruları yanıtla: hangi gate en çok tekrar etti, hangi path yanlış seçildi,
   hangi insan kapısı otomatikleşebilir?
3. Somut değişiklik → `registry.yaml`, `policies/`, `skills/` veya `doctor.py`.
4. Kayıt: `learning` etiketli issue + `CHANGELOG.md`.
5. Değişiklik sonrası `doctor.sh --strict` yeşil olmalı.

## Örnek closure bloğu

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
  gate_retries: 1
  reconcile_issues: 0
  human_interventions: 0
  lead_time_hours: 2.5
ready_for_human_qa: true
```

## Yorumlama

- `gate_retries` yüksek + `reconcile_issues` düşük → gate çok sıkı veya AC belirsiz.
- `human_interventions` yüksek → risk sınıflandırması veya AC kalitesi gözden geçir.
- `lead_time_hours` artıyor → kuyruk/paralellik veya leaf boyutu sorunu.
