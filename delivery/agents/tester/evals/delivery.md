# Tester delivery — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| TD-1 | Preview smoke yok | Fail | Doğrudan prod |
| TD-2 | Deploy marker yok | Fail | Korelasyon |
| TD-3 | Cache stale | Purge fail | Eski içerik |
| TD-4 | Flag kill switch yok | Fail | Geri dönüşsüz |
| TD-5 | Migration code uyumsuz | Fail | Kesinti |
| TD-6 | Rollback çalışmıyor | Fail | Kilitli |
| TD-7 | Post-deploy error artışı | Fail | Kör |
| TD-8 | CWV düşüşü | Fail | Ölçümsüz |
| TD-9 | Kritik akış smoke yok | Fail | Risk |
| TD-10 | Deploy logu yok | Fail | İz yok |
