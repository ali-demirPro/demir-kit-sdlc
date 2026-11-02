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
| `worker_count` | Run'daki worker dispatch sayısı | `usage.py --run <id>` |
| `tokens_in` | Worker oturumlarının yeni input token'ı | `usage.py --run <id>` |
| `tokens_out` | Worker output token'ı | `usage.py --run <id>` |
| `cache_read` | Cache'ten okunan token | `usage.py --run <id>` |
| `context_peak` | En büyük bağlam (cache read üst sınırı) | `usage.py --run <id>` |
| `cost_usd` | Worker maliyeti (sağlayıcı para birimi) | `usage.py --run <id>` |
| `coordinator_tokens_in` | Koordinatör oturum deltası (input) | `closure.py` (claim snapshot) |
| `coordinator_tokens_out` | Koordinatör oturum deltası (output) | `closure.py` |
| `coordinator_cache_read` | Koordinatör cache okuması | `closure.py` |
| `coordinator_cost_usd` | Koordinatör maliyeti | `closure.py` |

Token alanları opsiyoneldir; ölçülemezse yazılmaz. Worker sayıları
`usage.py --run <run_id>` çıktısından, koordinatör sayıları claim
snapshot'larından `closure.py --issue <epic>` ile **olduğu gibi** alınır; elle
tahmin edilmez.

## Toplama

- Kaynak: GitHub issue etiket zamanları + evidence comment'leri.
- Worker sayıları: `python3 delivery/scripts/usage.py --run <run_id> --json`
  (dispatch → OpenCode çalışması eşlemesi; bulunamazsa `unavailable`). Aynı
  worktree'de paralel dispatch'ler başlangıç sırasına göre monoton eşleştirilir;
  tamamlanmış dispatch'te bitişe en yakın `updated`, aktif dispatch'te oluşma
  sırası kullanılır. 1 saniyeden kısa arayla başlayan veya tek `--dispatch`
  belirsiz olduğunda `unavailable` döner; yanlış maliyet yazılmaz. Çıktıdaki
  `totals.worker_count`, `totals.tokens_in`, `totals.tokens_out`,
  `totals.cache_read`, `totals.context_peak`, `totals.cost_usd` doğrudan
  closure metriklerine yazılır.
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

Federasyon: filo repolarındaki `learning` kayıtları
`./delivery/scripts/learnings.py --all` ile toplanır; 2+ projede tekrar eden
ders genel kural adayı olur. Beyaz listedeki ekleme sınıfı otomatik uygulanır
(`delivery/CONTRACT.md` → Self-improvement lane).

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
  worker_count: 6
  tokens_in: 920000
  tokens_out: 41000
  cache_read: 18400000
  context_peak: 121000
  cost_usd: 0.82
  coordinator_tokens_in: 210000
  coordinator_tokens_out: 12000
  coordinator_cache_read: 4200000
  coordinator_cost_usd: 0.31
ready_for_human_qa: true
```

## Yorumlama

- `gate_retries` yüksek + `reconcile_issues` düşük → gate çok sıkı veya AC belirsiz.
- `human_interventions` yüksek → risk sınıflandırması veya AC kalitesi gözden geçir.
- `lead_time_hours` artıyor → kuyruk/paralellik veya leaf boyutu sorunu.
- `context_peak` yükseliyor → `policies/context-budget.md` ihlali; oturum
  sınırında sıfırla.
- `worker_count` yüksek + `tokens_in` düşük → iş çok parçalanmış veya reviewer
  fazlası var.
