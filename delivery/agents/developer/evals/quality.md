# Developer quality — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DVQ-1 | `innerHTML` kullanıcı verisi | Encode/CSP | XSS |
| DVQ-2 | Secret kodda | Env/secret manager | Repo sızıntısı |
| DVQ-3 | PII log'da | Maskele | Gizlilik ihlali |
| DVQ-4 | Focus `outline:none` | Görünür focus | A11y fail |
| DVQ-5 | N+1 sorgu | Batch/index | Yavaş |
| DVQ-6 | Gereksiz re-render | Memo/ölçüm | CPU |
| DVQ-7 | Hata `catch {}` | Log + kullanıcı mesajı | Sessiz |
| DVQ-8 | Sınırsız retry | Backoff/DLQ | Fırtına |
| DVQ-9 | Log correlation yok | Request id | Debug körü |
| DVQ-10 | Büyük asset | Optimize | CWV fail |
| DVQ-11 | Kontrast düşük | Token düzelt | A11y fail |
| DVQ-12 | Ölçümsüz optimizasyon | Baseline + sonuç | Tahmin |
