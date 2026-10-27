# Tester domain/risk — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| TDR-1 | Başka tenant kaydı | IDOR fail | Veri sızıntısı |
| TDR-2 | Logout sonrası token | Geçersiz | Oturum kalır |
| TDR-3 | MFA bypass | Fail | Güvenlik açığı |
| TDR-4 | Ödeme retry duplicate | Idempotency fail | Çift çekim |
| TDR-5 | Webhook imzasız | Fail | Sahte ödeme |
| TDR-6 | Çift iade | Fail | Para kaybı |
| TDR-7 | Migration rollback | Veri kaybı yok | Bozuk |
| TDR-8 | Backfill iki kez | Duplicate yok | Şişme |
| TDR-9 | Offline replay | Tek etki | Duplicate |
| TDR-10 | Process death | State korunur | Kayıp |
| TDR-11 | CVE kritik | Upgrade/waive | Açık |
| TDR-12 | Consent reddi | Ölçüm durur | İhlal |
