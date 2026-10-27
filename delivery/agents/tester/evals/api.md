# Tester API/CLI — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| TA-API-1 | Şema breaking change | Contract fail + sürüm | Sessiz geçiş |
| TA-API-2 | Retry duplicate yaratıyor | Idempotency fail | Çift kayıt |
| TA-API-3 | Başka tenant kaydı | Authz/IDOR fail | Veri sızıntısı |
| TA-API-4 | 500 dönmesi gereken 200 | Hata modeli fail | Sessiz hata |
| TA-API-5 | Rate limit yok | Limit fail | Brute force |
| TA-API-6 | Pagination sonsuz | Limit/süre fail | Kaynak tükenmesi |
| TA-API-7 | CLI yanlış çıkış kodu | Sözleşme fail | Script kırılır |
| TA-API-8 | CLI stdout'a log | Ayrım fail | Parse kırılır |
| TA-API-9 | Log'da token | Güvenlik fail | Sızıntı |
| TA-API-10 | Migration rollback yok | Smoke fail | Veri kaybı |
