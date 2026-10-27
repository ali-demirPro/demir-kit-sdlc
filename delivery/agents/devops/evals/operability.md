# DevOps operability — eval set

| ID | Senaryo | Beklenen | Fail sinyali |
|----|---------|----------|--------------|
| DO-1 | SLO CPU ile | Kullanıcı göstergesi | Vanity |
| DO-2 | Sahipsiz alarm | Owner + runbook | Gürültü |
| DO-3 | Log'da PII | Maskeleme/retention | Ham log |
| DO-4 | Trace yok | Correlation id + trace | Kör debug |
| DO-5 | Kartinalite patlaması | Label/retention | Sınırsız |
| DO-6 | Auth fail sinyali yok | Anomali alarmı | Fark edilmez |
| DO-7 | Rollback tatbikatı yok | Tatbikat + süre | Plan var |
| DO-8 | Deploy marker yok | Marker + dashboard | Korelasyon yok |
| DO-9 | Maliyet görünmez | Kapasite/maliyet notu | Sürpriz |
| DO-10 | Alarm eşiği rastgele | Burn-rate/eşik gerekçesi | Tahmin |
