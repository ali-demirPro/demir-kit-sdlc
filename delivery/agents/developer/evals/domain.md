# Developer domain — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DVD-1 | Refresh token yarışı | Tek uçuş/queue | Çift refresh |
| DVD-2 | Ödeme webhook imzasız | İmza + replay | Sahte ödeme |
| DVD-3 | Migration rollback yok | Geri plan | Veri kaybı |
| DVD-4 | Offline conflict | Politika + test | Last-write-wins |
| DVD-5 | i18n hardcoded metin | Locale kaynağı | String gömme |
| DVD-6 | Analytics PII | Kaldır/minimize | Email event |
| DVD-7 | Logout her yerde değil | Token/cache temizle | Kalıntı oturum |
| DVD-8 | Backfill idempotent değil | Batch + tekrar | Duplicate |
| DVD-9 | RTL/long text taşması | Layout testi | Kırpılma |
| DVD-10 | Store IAP + kendi ödeme | Tek akış | Çift ödeme |
| DVD-11 | Tenant izolasyonu yok | Sorgu filtresi | Veri sızıntısı |
| DVD-12 | Rollback denenmemiş | Dry-run | Plan var |
