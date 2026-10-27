# Architect design — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| AD-1 | Web'de auth + SEO aynı sayfada | Rendering/boundary tradeoff + ADR | "SSR yaparız" |
| AD-2 | API'de breaking change | Sürüm/deprecation planı | Sessiz breaking |
| AD-3 | Ödeme retry'ında duplicate | Idempotency tasarımı | "Retry ekleriz" |
| AD-4 | Migration geri dönüşsüz | İleri/geri plan + dry-run | Tek yön |
| AD-5 | Offline çakışma | Kaynak-of-truth + politika | Son-yazan-kazanır |
| AD-6 | Mobil lifecycle state kaybı | Restore/background tasarımı | "OS halleder" |
| AD-7 | NFR ölçüsüz | Ölçülebilir hedef + plan | "Hızlı olur" |
| AD-8 | CLI çıkış kodu belirsiz | Sözleşme + test | Rastgele kod |
| AD-9 | Tek alternatifli ADR | En az iki alternatif | Karar gerekçesiz |
| AD-10 | Cache invalidation yok | Strateji + hata modu | "TTL yeter" |
| AD-11 | Tenant izolasyonu belirsiz | Authz/boundary netliği | UI kontrolü |
| AD-12 | CP DAG risk sırası yanlış | Bağımlılık + risk sırası | Paralel kırılma |
