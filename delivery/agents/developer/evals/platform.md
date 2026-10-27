# Developer platform — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DVP-1 | Test sonra yazılmış | Kırmızı→yeşil kanıtı | Test yok |
| DVP-2 | Web'de state eksik | Loading/error/empty ekle | Yalnız happy path |
| DVP-3 | iOS secret UserDefaults | Keychain'e taşı | Düz metin |
| DVP-4 | Android process death | Restore ekle | State kaybı |
| DVP-5 | API retry duplicate | Idempotency key | Çift kayıt |
| DVP-6 | CLI çıkış kodu yanlış | Sözleşme + test | Rastgele kod |
| DVP-7 | Diff kapsam dışı | Ayır + issue | Scope creep |
| DVP-8 | Console error | Düzelt | Yok sayılır |
| DVP-9 | Form çift submit | Guard + test | Çift istek |
| DVP-10 | Migration geri uyumsuz | Ayrı adım | Aynı deploy |
| DVP-11 | Authz client'ta | Server kontrolü | UI gizleme |
| DVP-12 | Kanıt komutu yok | Komut + çıktı | Sözlü kanıt |
